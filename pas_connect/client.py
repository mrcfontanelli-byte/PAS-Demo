"""Client REST minimale, testabile e privo di dipendenze aggiuntive."""
from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .auth import authorization_header, build_token_payload, extract_token
from .config import GPExeConfig
from .endpoints import AUTH_TOKEN, Endpoint
from .exceptions import APIRequestError

Transport = Callable[[Request, float, bool], tuple[int, bytes]]


def _urllib_transport(request: Request, timeout: float, verify_tls: bool) -> tuple[int, bytes]:
    context = None
    if request.full_url.startswith("https://"):
        context = ssl.create_default_context() if verify_tls else ssl._create_unverified_context()
    with urlopen(request, timeout=timeout, context=context) as response:  # noqa: S310
        return int(response.status), response.read()


@dataclass
class GPExeClient:
    config: GPExeConfig
    transport: Transport = _urllib_transport

    def __post_init__(self) -> None:
        self.config.validate(require_credentials=False)
        self._token = self.config.token.strip()

    @property
    def token(self) -> str:
        return self._token

    def authenticate(self) -> str:
        payload = build_token_payload(self.config.username, self.config.password)
        response = self.request(AUTH_TOKEN, json_body=payload, authenticated=False)
        self._token = extract_token(response)
        return self._token

    def request(
        self,
        endpoint: Endpoint,
        *,
        path_values: Mapping[str, object] | None = None,
        query: Mapping[str, object] | None = None,
        json_body: Mapping[str, object] | None = None,
        authenticated: bool = True,
    ) -> Any:
        path = endpoint.format(**dict(path_values or {}))
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        if query:
            clean_query = {
                key: value for key, value in query.items() if value is not None
            }
            if clean_query:
                url = f"{url}?{urlencode(clean_query, doseq=True)}"

        headers = {"Accept": "application/json"}
        body = None
        if json_body is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(json_body).encode("utf-8")
        if authenticated:
            headers.update(authorization_header(self._token))

        request = Request(url, data=body, headers=headers, method=endpoint.method)
        try:
            status, raw = self.transport(
                request, self.config.timeout_seconds, self.config.verify_tls
            )
        except HTTPError as exc:
            raise APIRequestError(f"GPExe HTTP {exc.code}: {exc.reason}") from exc
        except URLError as exc:
            raise APIRequestError(f"Connessione GPExe non riuscita: {exc.reason}") from exc
        except TimeoutError as exc:
            raise APIRequestError("Timeout durante la richiesta GPExe.") from exc

        if not 200 <= status < 300:
            raise APIRequestError(f"GPExe ha restituito lo stato HTTP {status}.")
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise APIRequestError("Risposta GPExe non JSON o non valida.") from exc
