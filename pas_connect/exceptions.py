"""Eccezioni specifiche di PAS Connect."""


class PASConnectError(RuntimeError):
    """Errore base del livello PAS Connect."""


class ConfigurationError(PASConnectError):
    """Configurazione mancante o non valida."""


class AuthenticationError(PASConnectError):
    """Autenticazione al provider non riuscita."""


class APIRequestError(PASConnectError):
    """Richiesta API fallita o risposta non valida."""

    def __init__(self, message: str, *, graphql_errors: tuple[dict, ...] = ()) -> None:
        super().__init__(message)
        self.graphql_errors = graphql_errors


class MappingError(PASConnectError):
    """Dato del provider non convertibile nello schema PAS."""


class RateLimitError(APIRequestError):
    """Rate limit GPExe esaurito dopo i tentativi previsti."""
