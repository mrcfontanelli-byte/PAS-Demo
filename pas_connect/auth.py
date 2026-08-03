"""Funzioni pure per autenticazione GPExe."""
from __future__ import annotations

from typing import Any, Mapping

from .exceptions import AuthenticationError


def build_token_payload(username: str, password: str) -> dict[str, str]:
    if not username or not password:
        raise AuthenticationError("Username e password GPExe sono obbligatori.")
    return {"username": username, "password": password}


def extract_token(payload: Mapping[str, Any]) -> str:
    token = payload.get("token")
    if not isinstance(token, str) or not token.strip():
        raise AuthenticationError("La risposta GPExe non contiene un token valido.")
    return token.strip()


def authorization_header(token: str) -> dict[str, str]:
    if not token.strip():
        raise AuthenticationError("Token GPExe vuoto.")
    return {"Authorization": f"Token {token.strip()}"}
