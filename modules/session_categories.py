"""Tassonomia canonica delle categorie di seduta visibili nel PAS."""
from __future__ import annotations

from typing import Any


DIFFERENT_TRAINING = "Different Training"
SESSION_CATEGORY_ALIASES = {
    "Different Traning": DIFFERENT_TRAINING,
}
DASHBOARD_SESSION_CATEGORIES = (
    "Full Training",
    "Individual Training",
    "Return to Play",
    "Active Recovery",
    DIFFERENT_TRAINING,
    "Match",
    "Recovery",
)


def canonical_session_category(value: Any) -> Any:
    """Normalizza gli alias storici senza reinterpretare valori sconosciuti."""
    if not isinstance(value, str):
        return value
    normalized = value.strip()
    return SESSION_CATEGORY_ALIASES.get(normalized, normalized)
