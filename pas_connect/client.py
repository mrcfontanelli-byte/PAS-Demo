"""Client HTTP resiliente per le API GPExe.

Il modulo non dipende da Streamlit ed è quindi riutilizzabile e testabile.
Gestisce autenticazione, rinnovo token su 401, timeout, rate limit e risposte
asincrone 202 Accepted tramite retry/polling controllato.
"""
from __future__ import annotations

import json
import socket
import ssl
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .auth import authorization_header, build_token_payload, extract_auth_tokens
from .config import GPExeConfig, normalize_gpexe_base_url
from .endpoints import AUTH_TOKEN, Endpoint
from .exceptions import APIRequestError, AuthenticationError, RateLimitError

Transport = Callable[[Request, float, bool], tuple[int, bytes] | tuple[int, bytes, Mapping[str, str]]]
Sleep = Callable[[float], None]


def _urllib_transport(request: Request, timeout: float, verify_tls: bool):
    context = None
    if request.full_url.startswith("https://"):
        context = ssl.create_default_context() if verify_tls else ssl._create_unverified_context()
    try:
        with urlopen(request, timeout=timeout, context=context) as response:  # noqa: S310
            return int(response.status), response.read(), dict(response.headers.items())
    except HTTPError as exc:
        return int(exc.code), exc.read(), dict(exc.headers.items()) if exc.headers else {}


@dataclass
class GPExeClient:
    config: GPExeConfig
    transport: Transport = _urllib_transport
    sleep: Sleep = time.sleep
    _token: str = field(init=False, default="")
    _refresh_token: str = field(init=False, default="")

    def __post_init__(self) -> None:
        self.config.validate(require_credentials=False)
        self._token = self.config.token.strip()

    @property
    def token(self) -> str:
        return self._token

    def clear_token(self) -> None:
        self._token = ""

    def authenticate(self, *, force: bool = False) -> str:
        """Autentica tramite la mutation GraphQL TokenAuth usata dal client GPExe."""
        if self._token and not force:
            return self._token
        payload = build_token_payload(self.config.username, self.config.password)
        response = self.graphql(
            payload["query"],
            variables=payload["variables"],
            operation_name=payload["operationName"],
            authenticated=False,
        )
        self._token, self._refresh_token, _ = extract_auth_tokens(response)
        return self._token

    @property
    def refresh_token(self) -> str:
        return self._refresh_token

    def test_connection(self) -> bool:
        if not self._token:
            self.authenticate()
        response = self.graphql("query PASConnectionTest { __typename }", operation_name="PASConnectionTest")
        data = response.get("data") if isinstance(response, Mapping) else None
        if not isinstance(data, Mapping) or not data.get("__typename"):
            raise APIRequestError("Test GraphQL GPExe non valido.")
        return True

    def graphql(
        self, query: str, *, variables: Mapping[str, object] | None = None,
        operation_name: str | None = None, authenticated: bool = True,
    ) -> Mapping[str, Any]:
        if authenticated and not self._token:
            self.authenticate()
        payload: dict[str, Any] = {"query": query, "variables": dict(variables or {})}
        if operation_name:
            payload["operationName"] = operation_name
        url = normalize_gpexe_base_url(self.config.base_url) + "/"
        body = json.dumps(payload).encode("utf-8")
        refreshed = False
        attempts = 0
        while True:
            attempts += 1
            headers = {"Accept": "application/json", "Content-Type": "application/json"}
            if authenticated:
                headers.update(authorization_header(self._token))
            request = Request(url, data=body, headers=headers, method="POST")
            status, raw, response_headers = self._send(request)
            if status == 401 and authenticated and not refreshed and self.config.username and self.config.password:
                self.authenticate(force=True)
                refreshed = True
                continue
            if status == 429:
                if attempts > self.config.max_retries:
                    raise RateLimitError("Limite richieste GPExe raggiunto; riprovare più tardi.")
                self.sleep(self._retry_delay(response_headers, attempts))
                continue
            if status in {408, 500, 502, 503, 504}:
                if attempts > self.config.max_retries:
                    raise APIRequestError(self._http_error_message(status, raw))
                self.sleep(self._retry_delay(response_headers, attempts))
                continue
            if status == 401:
                raise AuthenticationError("Credenziali o token GPExe non validi.")
            if not 200 <= status < 300:
                raise APIRequestError(self._http_error_message(status, raw))
            decoded = self._decode(raw, status=status, headers=response_headers, url=url)
            if not isinstance(decoded, Mapping):
                raise APIRequestError("Risposta GraphQL GPExe non valida.")
            errors = decoded.get("errors")
            if errors:
                message = "; ".join(str(e.get("message", e)) if isinstance(e, Mapping) else str(e) for e in errors)
                raise APIRequestError(f"Errore GraphQL GPExe: {message}")
            return decoded

    def request(
        self,
        endpoint: Endpoint,
        *,
        path_values: Mapping[str, object] | None = None,
        query: Mapping[str, object] | None = None,
        json_body: Mapping[str, object] | None = None,
        form_body: Mapping[str, object] | None = None,
        authenticated: bool = True,
    ) -> Any:
        if authenticated and not self._token:
            self.authenticate()
        url = self._build_url(endpoint, path_values=path_values, query=query)
        if json_body is not None and form_body is not None:
            raise ValueError("Usare json_body oppure form_body, non entrambi.")
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
        elif form_body is not None:
            body = urlencode({k: str(v) for k, v in form_body.items()}).encode("utf-8")
        else:
            body = None
        refreshed = False
        attempts = 0
        while True:
            attempts += 1
            headers = {"Accept": "application/json"}
            if json_body is not None:
                headers["Content-Type"] = "application/json"
            elif form_body is not None:
                headers["Content-Type"] = "application/x-www-form-urlencoded"
            if authenticated:
                headers.update(authorization_header(self._token))
            request = Request(url, data=body, headers=headers, method=endpoint.method)
            status, raw, response_headers = self._send(request)

            if status == 401 and authenticated and not refreshed and self.config.username and self.config.password:
                self.authenticate(force=True)
                refreshed = True
                continue
            if status == 202:
                if attempts > self.config.max_poll_attempts:
                    raise APIRequestError("GPExe non ha completato la richiesta asincrona entro il limite previsto.")
                self.sleep(self._retry_delay(response_headers, attempts, polling=True))
                continue
            if status == 429:
                if attempts > self.config.max_retries:
                    raise RateLimitError("Limite richieste GPExe raggiunto; riprovare più tardi.")
                self.sleep(self._retry_delay(response_headers, attempts))
                continue
            if status in {408, 500, 502, 503, 504}:
                if attempts > self.config.max_retries:
                    raise APIRequestError(self._http_error_message(status, raw))
                self.sleep(self._retry_delay(response_headers, attempts))
                continue
            if status == 401:
                raise AuthenticationError("Credenziali o token GPExe non validi.")
            if not 200 <= status < 300:
                raise APIRequestError(self._http_error_message(status, raw))
            return self._decode(raw, status=status, headers=response_headers, url=url)

    def _build_url(self, endpoint: Endpoint, *, path_values=None, query=None) -> str:
        path = endpoint.format(**dict(path_values or {}))
        url = f"{normalize_gpexe_base_url(self.config.base_url)}/{path.lstrip('/')}"
        clean = {k: v for k, v in dict(query or {}).items() if v is not None}
        if clean:
            url = f"{url}?{urlencode(clean, doseq=True)}"
        return url

    def _send(self, request: Request) -> tuple[int, bytes, Mapping[str, str]]:
        try:
            result = self.transport(request, self.config.timeout_seconds, self.config.verify_tls)
            if len(result) == 2:
                status, raw = result
                return int(status), raw, {}
            status, raw, headers = result
            return int(status), raw, headers
        except (TimeoutError, socket.timeout) as exc:
            raise APIRequestError("Timeout durante la richiesta GPExe.") from exc
        except URLError as exc:
            reason = getattr(exc, "reason", exc)
            raise APIRequestError(f"Connessione GPExe non riuscita: {reason}") from exc
        except OSError as exc:
            raise APIRequestError(f"Errore di rete GPExe: {exc}") from exc

    def _retry_delay(self, headers: Mapping[str, str], attempt: int, polling: bool = False) -> float:
        retry_after = next((v for k, v in headers.items() if k.lower() == "retry-after"), None)
        if retry_after:
            try:
                return min(float(retry_after), self.config.max_retry_delay_seconds)
            except ValueError:
                pass
        base = self.config.poll_interval_seconds if polling else self.config.retry_backoff_seconds
        return min(base * (2 ** max(0, attempt - 1)), self.config.max_retry_delay_seconds)

    @staticmethod
    def _decode(
        raw: bytes,
        *,
        status: int | None = None,
        headers: Mapping[str, str] | None = None,
        url: str = "",
    ) -> Any:
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            content_type = next(
                (str(v) for k, v in dict(headers or {}).items() if k.lower() == "content-type"),
                "sconosciuto",
            )
            preview = raw.decode("utf-8", errors="replace")
            preview = " ".join(preview.split())[:180]
            safe_url = url.split("?", 1)[0]
            detail = (
                f"HTTP {status}; Content-Type {content_type}; URL {safe_url}; "
                f"anteprima: {preview or '[vuota]'}"
            )
            raise APIRequestError(f"Risposta GPExe non JSON o non valida ({detail}).") from exc

    @staticmethod
    def _http_error_message(status: int, raw: bytes) -> str:
        detail = ""
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else None
            if isinstance(payload, Mapping):
                detail = str(payload.get("detail") or payload.get("message") or payload.get("error") or "")
        except Exception:
            detail = raw.decode("utf-8", errors="replace")[:200] if raw else ""
        suffix = f": {detail}" if detail else "."
        return f"GPExe ha restituito HTTP {status}{suffix}"
