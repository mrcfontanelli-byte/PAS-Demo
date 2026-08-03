"""Client GraphQL GPExe indipendente da Streamlit e privo di logging sensibile."""
from __future__ import annotations

import json
import socket
import ssl
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .auth import authorization_header, build_token_payload, extract_auth_tokens
from .config import GPExeConfig, normalize_gpexe_base_url
from .exceptions import APIRequestError, AuthenticationError

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
class GPExeGraphQLClient:
    config: GPExeConfig
    transport: Transport = _urllib_transport
    sleep: Sleep = time.sleep
    _token: str = field(init=False, default="")
    _refresh_token: str = field(init=False, default="")
    _is_active: bool | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.config.validate(require_credentials=False)
        self._token = self.config.token.strip()

    @property
    def token(self) -> str:
        return self._token

    def clear_token(self) -> None:
        self._token = ""
        self._refresh_token = ""
        self._is_active = None

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
        self._token, self._refresh_token, self._is_active = extract_auth_tokens(response)
        return self._token

    @property
    def refresh_token(self) -> str:
        return self._refresh_token

    @property
    def is_active(self) -> bool | None:
        return self._is_active

    def test_connection(self) -> bool:
        self.authenticate(force=not bool(self.config.token))
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
        attempts = 0
        while True:
            attempts += 1
            headers = {"Accept": "application/json", "Content-Type": "application/json"}
            if authenticated:
                headers.update(authorization_header(self._token))
            request = Request(url, data=body, headers=headers, method="POST")
            try:
                status, raw, response_headers = self._send(request)
            except APIRequestError:
                if attempts > self.config.max_retries:
                    raise
                self.sleep(self._retry_delay({}, attempts))
                continue
            if status in {408, 429, 500, 502, 503, 504}:
                if attempts > self.config.max_retries:
                    raise APIRequestError(self._http_error_message(status, raw))
                self.sleep(self._retry_delay(response_headers, attempts))
                continue
            if not 200 <= status < 300:
                raise APIRequestError(self._http_error_message(status, raw))
            decoded = self._decode(raw, status=status, headers=response_headers, url=url)
            if not isinstance(decoded, Mapping):
                raise APIRequestError("Risposta GraphQL GPExe non valida.")
            errors = decoded.get("errors")
            if errors:
                message = "; ".join(
                    str(item.get("message", "Errore non specificato"))
                    if isinstance(item, Mapping) else "Errore non specificato"
                    for item in errors
                )
                safe_message = self._redact(message)
                if operation_name == "TokenAuth":
                    raise AuthenticationError(
                        f"Credenziali GPExe non valide o autenticazione rifiutata: {safe_message}"
                    )
                raise APIRequestError(f"Errore GraphQL GPExe: {safe_message}")
            data = decoded.get("data")
            if not isinstance(data, Mapping):
                raise APIRequestError("La risposta GraphQL GPExe non contiene un campo data valido.")
            return decoded

    def request(self, *_: object, **__: object) -> Any:
        """Impedisce l'uso accidentale dei precedenti endpoint REST presunti."""
        raise APIRequestError(
            "Query GraphQL Team/TeamSession da acquisire e verificare."
        )

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
            safe_url = url.split("?", 1)[0]
            detail = (
                f"HTTP {status}; Content-Type {content_type}; URL {safe_url}"
            )
            raise APIRequestError(f"Risposta GPExe non JSON o non valida ({detail}).") from exc

    @staticmethod
    def _http_error_message(status: int, raw: bytes) -> str:
        return f"GPExe ha restituito HTTP {status}."

    def _redact(self, message: str) -> str:
        safe = str(message)
        for secret in (self.config.password, self._token, self._refresh_token, self.config.token):
            if secret:
                safe = safe.replace(secret, "[dato sensibile rimosso]")
        return safe


# Alias temporaneo per non interrompere gli import interni: entrambe le classi
# espongono esclusivamente il trasporto GraphQL verificato.
GPExeClient = GPExeGraphQLClient
