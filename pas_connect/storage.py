"""Persistenza locale isolata delle snapshot PAS Connect.

La snapshot non sostituisce il database Excel e non contiene credenziali.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class SnapshotStore:
    path: Path

    @classmethod
    def default(cls, root: Path | None = None) -> "SnapshotStore":
        base = root or Path.cwd()
        return cls(base / ".pas_data" / "gpexe_snapshot.json")

    def save(self, payload: Mapping[str, Any]) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(self.path)
        return self.path

    def load(self) -> dict[str, Any] | None:
        if not self.path.is_file():
            return None
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
