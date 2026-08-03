"""Funzioni pure per autenticazione GPExe."""
from __future__ import annotations

from typing import Any, Mapping

from .exceptions import AuthenticationError


def build_token_payload(username: str, password: str) -> dict[str, str]:
    if not username or not password:
        raise AuthenticationError("Username e password GPExe sono obbligatori.")
    return {"username": username, "password": password}


def extract_token(payload: Mapping[str, Any]) -> str:
    if not isinstance(payload, Mapping):
        raise AuthenticationError("La risposta GPExe di autenticazione non è un oggetto valido.")
    for key in ("token", "access_token", "key"):
        token = payload.get(key)
        if isinstance(token, str) and token.strip():
            return token.strip()
    data = payload.get("data")
    if isinstance(data, Mapping):
        for key in ("token", "access_token", "key"):
            token = data.get(key)
            if isinstance(token, str) and token.strip():
                return token.strip()
    raise AuthenticationError("La risposta GPExe non contiene un token valido.")


def authorization_header(token: str) -> dict[str, str]:
    if not token.strip():
        raise AuthenticationError("Token GPExe vuoto.")
    return {"Authorization": f"Token {token.strip()}"}
