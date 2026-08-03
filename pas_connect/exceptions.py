"""Eccezioni specifiche di PAS Connect."""


class PASConnectError(RuntimeError):
    """Errore base del livello PAS Connect."""


class ConfigurationError(PASConnectError):
    """Configurazione mancante o non valida."""


class AuthenticationError(PASConnectError):
    """Autenticazione al provider non riuscita."""


class APIRequestError(PASConnectError):
    """Richiesta API fallita o risposta non valida."""


class MappingError(PASConnectError):
    """Dato del provider non convertibile nello schema PAS."""
