"""Controllo deterministico della struttura di una release PAS."""
from __future__ import annotations

import ast
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIRED_FILES = (
    "app.py",
    "requirements.txt",
    "README.md",
    "CHANGELOG.md",
    "modules/__init__.py",
    "modules/config.py",
    "modules/version.py",
    "Database Hellas 25-26.xlsx",
)


def validate_requirements(path: Path) -> list[str]:
    errors: list[str] = []
    allowed_name_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.[]")
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name = line
        for separator in ("@", "(", "<", "=", ">", "~", "!", ";"):
            name = name.split(separator, 1)[0]
        name = name.strip()
        if not name or any(char not in allowed_name_chars for char in name):
            errors.append(f"requirements.txt:{number}: requisito non valido: {raw!r}")
    return errors


def main() -> int:
    errors: list[str] = []
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            errors.append(f"File mancante: {relative}")

    req = ROOT / "requirements.txt"
    if req.is_file():
        errors.extend(validate_requirements(req))

    py_files = sorted(ROOT.rglob("*.py"))
    for path in py_files:
        try:
            source = path.read_text(encoding="utf-8")
            ast.parse(source, filename=str(path))
            compile(source, str(path), "exec")
        except Exception as exc:  # pragma: no cover - utility script
            errors.append(f"Errore Python in {path.relative_to(ROOT)}: {exc}")

    db = ROOT / "Database Hellas 25-26.xlsx"
    db_hash = hashlib.sha256(db.read_bytes()).hexdigest() if db.is_file() else "n/a"

    if errors:
        print("VALIDAZIONE FALLITA")
        for error in errors:
            print(f"- {error}")
        return 1

    print("VALIDAZIONE OK")
    print(f"File Python compilati: {len(py_files)}")
    print(f"SHA-256 database: {db_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
