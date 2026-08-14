"""Client read-only per la discovery del contratto REST ufficiale GPExe."""
from __future__ import annotations

import json
import re
import socket
import ssl
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import GPExeConfig, normalize_gpexe_base_url
from .endpoints import (
    ATHLETES,
    ATHLETE_DETAIL,
    ATHLETE_SESSION_DETAIL,
    AUTH_TOKEN,
    TEAM_SESSION_ATHLETES,
    TEAM_SESSION_DETAIL,
    Endpoint,
)
from .exceptions import APIRequestError, AuthenticationError, RateLimitError

RESTTransport = Callable[
    [Request, float, bool],
    tuple[int, bytes] | tuple[int, bytes, Mapping[str, str]],
]
Sleep = Callable[[float], None]
Clock = Callable[[], float]

_REDACTED = "[dato sensibile rimosso]"
_AUTHORIZATION_VALUE = re.compile(r"(?i)\bauthorization\s*([:=])\s*[^\r\n,;]+")
_SENSITIVE_ASSIGNMENT = re.compile(r"(?i)\b(token|password)\s*([:=])\s*([^\s,;]+)")


def _urllib_rest_transport(request: Request, timeout: float, verify_tls: bool):
    context = None
    if request.full_url.startswith("https://"):
        context = ssl.create_default_context() if verify_tls else ssl._create_unverified_context()
    try:
        with urlopen(request, timeout=timeout, context=context) as response:  # noqa: S310
            return int(response.status), response.read(), dict(response.headers.items())
    except HTTPError as exc:
        return int(exc.code), exc.read(), dict(exc.headers.items()) if exc.headers else {}


@dataclass(frozen=True)
class RESTProcessingResponse:
    """Risposta accettata ma non pronta; non avvia polling implicito."""

    status: int = 202
    state: str = "processing/not ready"
    payload: Any = None
    retry_after_seconds: float | None = None


@dataclass
class GPExeRESTClient:
    """Trasporto REST isolato, senza persistenza e limitato alla contract discovery."""

    config: GPExeConfig
    transport: RESTTransport = _urllib_rest_transport
    sleep: Sleep = time.sleep
    clock: Clock = time.monotonic
    rate_limit_per_minute: int = 40
    _token: str = field(init=False, default="")
    _request_times: list[float] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self.config.validate(require_credentials=False)
        if self.rate_limit_per_minute <= 0:
            raise ValueError("Il rate limit REST deve essere positivo.")
        self._base_url = normalize_gpexe_base_url(self.config.base_url)
        self._token = self.config.token.strip()

    @property
    def token(self) -> str:
        return self._token

    def clear_token(self) -> None:
        self._token = ""

    def authenticate(self, *, force: bool = False) -> str:
        if self._token and not force:
            return self._token
        if not self.config.username or not self.config.password:
            raise AuthenticationError("Username e password GPExe sono obbligatori.")
        payload = self._request(
            AUTH_TOKEN,
            json_body={"username": self.config.username, "password": self.config.password},
            authenticated=False,
        )
        token = payload.get("token") if isinstance(payload, Mapping) else None
        if not isinstance(token, str) or not token.strip():
            raise AuthenticationError("La risposta REST GPExe non contiene un token valido.")
        self._token = token.strip()
        return self._token

    def team_session(
        self,
        team_session_id: int,
        *,
        all_params: bool | None = None,
        export_template: int | str | None = None,
    ) -> Any:
        query: dict[str, object] = {}
        if all_params is not None:
            query["all_params"] = str(bool(all_params)).lower()
        if export_template is not None:
            query["export_template"] = export_template
        return self._request(
            TEAM_SESSION_DETAIL,
            path_values={"id": self._positive_id(team_session_id, "TeamSession")},
            query=query,
        )

    def athletes(self) -> Any:
        """Restituisce la prima pagina del roster REST account-level."""
        return self._request(ATHLETES)

    def athlete(self, athlete_id: int) -> Any:
        """Restituisce l'identita di un singolo atleta REST."""
        return self._request(
            ATHLETE_DETAIL,
            path_values={"id": self._positive_id(athlete_id, "Athlete")},
        )

    def athlete_sessions(self, team_session_id: int) -> Any:
        return self._request(
            TEAM_SESSION_ATHLETES,
            path_values={"id": self._positive_id(team_session_id, "TeamSession")},
        )

    def athlete_session(self, athlete_session_id: int) -> Any:
        return self._request(
            ATHLETE_SESSION_DETAIL,
            path_values={"id": self._positive_id(athlete_session_id, "AthleteSession")},
        )

    def _request(
        self,
        endpoint: Endpoint,
        *,
        path_values: Mapping[str, object] | None = None,
        query: Mapping[str, object] | None = None,
        json_body: Mapping[str, object] | None = None,
        authenticated: bool = True,
    ) -> Any:
        if authenticated and not self._token:
            self.authenticate()
        path = endpoint.format(**dict(path_values or {}))
        url = f"{self._base_url.rstrip('/')}/{path.lstrip('/')}"
        clean_query = {key: value for key, value in dict(query or {}).items() if value is not None}
        if clean_query:
            url = f"{url}?{urlencode(clean_query, doseq=True)}"

        headers = {"Accept": "application/json"}
        body = None
        if json_body is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(dict(json_body)).encode("utf-8")
        if authenticated:
            headers["Authorization"] = f"Token {self._token}"

        request = Request(url, data=body, headers=headers, method=endpoint.method)
        attempts = 0
        while True:
            attempts += 1
            self._respect_rate_limit()
            try:
                status, raw, response_headers = self._send(request)
            except APIRequestError:
                if attempts > self.config.max_retries:
                    raise
                self.sleep(self._retry_delay({}, attempts))
                continue
            if status in {408, 429, 500, 502, 503, 504} and attempts <= self.config.max_retries:
                self.sleep(self._retry_delay(response_headers, attempts))
                continue
            if status in {401, 403}:
                self.clear_token()
                raise AuthenticationError(f"Autenticazione REST GPExe rifiutata · HTTP {status}.")
            if status == 429:
                raise RateLimitError("Rate limit REST GPExe esaurito · HTTP 429.")
            if not 200 <= status < 300:
                raise APIRequestError(
                    f"Richiesta REST GPExe {endpoint.method} {path} · HTTP {status}."
                )
            if status == 202:
                return RESTProcessingResponse(
                    payload=self._decode(raw, status=status, headers=response_headers, url=url),
                    retry_after_seconds=self._retry_after_value(response_headers),
                )
            return self._decode(raw, status=status, headers=response_headers, url=url)

    def _respect_rate_limit(self) -> None:
        """Rispetta 40 richieste/minuto senza concorrenza o polling automatico."""
        now = self.clock()
        self._request_times = [stamp for stamp in self._request_times if now - stamp < 60.0]
        if len(self._request_times) >= self.rate_limit_per_minute:
            delay = max(0.0, 60.0 - (now - self._request_times[0]))
            if delay:
                self.sleep(delay)
                now = self.clock()
                self._request_times = [stamp for stamp in self._request_times if now - stamp < 60.0]
        self._request_times.append(now)

    def _send(self, request: Request) -> tuple[int, bytes, Mapping[str, str]]:
        try:
            result = self.transport(request, self.config.timeout_seconds, self.config.verify_tls)
            if len(result) == 2:
                status, raw = result
                return int(status), raw, {}
            status, raw, headers = result
            return int(status), raw, headers
        except (TimeoutError, socket.timeout) as exc:
            raise APIRequestError("Timeout durante la richiesta REST GPExe.") from exc
        except URLError as exc:
            raise APIRequestError(
                f"Connessione REST GPExe non riuscita: {self.redact(getattr(exc, 'reason', exc))}"
            ) from exc
        except OSError as exc:
            raise APIRequestError(f"Errore di rete REST GPExe: {self.redact(exc)}") from exc

    def _retry_delay(self, headers: Mapping[str, str], attempt: int) -> float:
        retry_after = self._retry_after_value(headers)
        if retry_after is not None:
            return retry_after
        return min(
            self.config.retry_backoff_seconds * (2 ** max(0, attempt - 1)),
            self.config.max_retry_delay_seconds,
        )

    def _retry_after_value(self, headers: Mapping[str, str]) -> float | None:
        retry_after = next((v for k, v in headers.items() if k.lower() == "retry-after"), None)
        if retry_after is None:
            return None
        try:
            return min(float(retry_after), self.config.max_retry_delay_seconds)
        except ValueError:
            return None

    def _decode(
        self,
        raw: bytes,
        *,
        status: int,
        headers: Mapping[str, str],
        url: str,
    ) -> Any:
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            content_type = next(
                (str(v) for k, v in headers.items() if k.lower() == "content-type"),
                "sconosciuto",
            )
            safe_url = url.split("?", 1)[0]
            raise APIRequestError(
                f"Risposta REST GPExe non JSON o non valida "
                f"(HTTP {status}; Content-Type {self.redact(content_type)}; URL {safe_url})."
            ) from exc

    def redact(self, value: object) -> str:
        safe = str(value)
        for secret in (self.config.password, self.config.token, self._token):
            if secret:
                safe = safe.replace(secret, _REDACTED)
        safe = _AUTHORIZATION_VALUE.sub(
            lambda match: f"Authorization{match.group(1)} {_REDACTED}", safe
        )
        return _SENSITIVE_ASSIGNMENT.sub(
            lambda match: f"{match.group(1)}{match.group(2)} {_REDACTED}", safe
        )

    @staticmethod
    def _positive_id(value: object, label: str) -> int:
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} ID deve essere un intero positivo.") from exc
        if normalized <= 0:
            raise ValueError(f"{label} ID deve essere un intero positivo.")
        return normalized
