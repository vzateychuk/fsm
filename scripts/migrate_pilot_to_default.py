#!/usr/bin/env python3
"""Migrate pilot ingest.db to default.db and seed user_profile from patient.yaml."""

from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.api.schema_init import ensure_schema  # noqa: E402
from src.common.patient import PatientInfo  # noqa: E402
from src.store.sql.sqlite_internal_store import SqliteInternalStore  # noqa: E402

DEFAULT_DB = ROOT / ".data/db/default.db"
INGEST_DB = ROOT / ".data/db/ingest.db"
PATIENT_YAML = ROOT / "config/patient.yaml"


async def migrate(*, force_backup: bool = True) -> int:
    if DEFAULT_DB.exists():
        print(f"Skip: {DEFAULT_DB} already exists")
        return 0

    if not INGEST_DB.exists():
        print(f"Error: source {INGEST_DB} not found. Nothing to migrate.", file=sys.stderr)
        return 1

    DEFAULT_DB.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(INGEST_DB, DEFAULT_DB)
    print(f"Copied {INGEST_DB} -> {DEFAULT_DB}")

    await ensure_schema(str(DEFAULT_DB))

    store = SqliteInternalStore(db_path=str(DEFAULT_DB))
    existing = await store.get_user_profile()
    if existing is None:
        patient = PatientInfo.load(PATIENT_YAML)
        await store.upsert_user_profile(patient)
        print(f"Seeded user_profile from {PATIENT_YAML}")
    else:
        print("user_profile row already present — skip seed")

    if force_backup:
        backup = INGEST_DB.with_suffix(".db.bak")
        if not backup.exists():
            shutil.copy2(INGEST_DB, backup)
            print(f"Backup: {backup}")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate ingest.db to default.db")
    parser.parse_args()
    raise SystemExit(asyncio.run(migrate()))


if __name__ == "__main__":
    main()
