"""Piano di sincronizzazione; nessuna scrittura dati è attiva in v3.7.36."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SyncResource(str, Enum):
    TEAMS = "teams"
    CATEGORIES = "categories"
    TAGS = "tags"
    ATHLETES = "athletes"
    SESSIONS = "sessions"
    ATHLETE_SESSIONS = "athlete_sessions"
    TRACKS = "tracks"


@dataclass(frozen=True)
class SyncStep:
    order: int
    resource: SyncResource
    incremental: bool
    required_for_analysis: bool


@dataclass(frozen=True)
class SyncPlan:
    steps: tuple[SyncStep, ...]

    def validate(self) -> None:
        orders = [step.order for step in self.steps]
        if orders != sorted(orders) or len(orders) != len(set(orders)):
            raise ValueError("Ordine del piano di sincronizzazione non valido.")


def build_default_sync_plan() -> SyncPlan:
    plan = SyncPlan(
        steps=(
            SyncStep(1, SyncResource.TEAMS, True, True),
            SyncStep(2, SyncResource.CATEGORIES, False, True),
            SyncStep(3, SyncResource.TAGS, False, False),
            SyncStep(4, SyncResource.ATHLETES, False, True),
            SyncStep(5, SyncResource.SESSIONS, True, True),
            SyncStep(6, SyncResource.ATHLETE_SESSIONS, True, True),
            SyncStep(7, SyncResource.TRACKS, True, False),
        )
    )
    plan.validate()
    return plan
