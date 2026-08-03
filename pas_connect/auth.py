"""Funzioni pure per l'autenticazione GraphQL GPExe."""
from __future__ import annotations
from typing import Any, Mapping
from .exceptions import AuthenticationError

TOKEN_AUTH_MUTATION = """mutation TokenAuth($email: String!, $password: String!) {
  tokenAuth(email: $email, password: $password) {
    isActive
    token
    refreshToken
  }
}"""

REFRESH_TOKEN_MUTATION = """mutation RefreshToken($token: String!) {
  refreshToken(token: $token) {
    token
    refreshToken
  }
}"""

def build_token_payload(username: str, password: str) -> dict[str, Any]:
    if not username or not password:
        raise AuthenticationError("Email e password GPExe sono obbligatorie.")
    return {
        "operationName": "TokenAuth",
        "query": TOKEN_AUTH_MUTATION,
        "variables": {"email": username, "password": password},
    }

def extract_auth_tokens(payload: Mapping[str, Any]) -> tuple[str, str, bool]:
    if not isinstance(payload, Mapping):
        raise AuthenticationError("La risposta GraphQL GPExe non è valida.")
    errors = payload.get("errors")
    if errors:
        message = "; ".join(str(e.get("message", e)) if isinstance(e, Mapping) else str(e) for e in errors)
        raise AuthenticationError(f"Autenticazione GraphQL GPExe non riuscita: {message}")
    data = payload.get("data")
    auth = data.get("tokenAuth") if isinstance(data, Mapping) else None
    if not isinstance(auth, Mapping):
        raise AuthenticationError("La risposta GraphQL non contiene tokenAuth.")
    token = str(auth.get("token") or "").strip()
    refresh = str(auth.get("refreshToken") or "").strip()
    active = bool(auth.get("isActive", True))
    if not token:
        raise AuthenticationError("La risposta GraphQL GPExe non contiene un token valido.")
    if not active:
        raise AuthenticationError("L'account GPExe risulta non attivo.")
    return token, refresh, active

def extract_token(payload: Mapping[str, Any]) -> str:
    return extract_auth_tokens(payload)[0]

def authorization_header(token: str) -> dict[str, str]:
    if not token.strip():
        raise AuthenticationError("Token GPExe vuoto.")
    return {"Authorization": f"JWT {token.strip()}"}
