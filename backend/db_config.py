from pathlib import Path
import os
import re

import duckdb

from workspace_context import get_workspace_id
from storage_paths import DATA_DIR


BASE_DIR = DATA_DIR
DB_PATH = BASE_DIR / "atlas.db"
CORE_TABLES = ("patients", "providers", "claims", "payments")


def _create_workspace_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    target = duckdb.connect(str(path))

    schemas = {
        "patients": "patient_id INTEGER, diagnosis VARCHAR, state VARCHAR",
        "providers": "provider_id INTEGER, provider_name VARCHAR",
        "claims": "claim_id INTEGER, patient_id INTEGER, provider_id INTEGER, claim_amount DOUBLE",
        "payments": "payment_id INTEGER, claim_id INTEGER, payment_amount DOUBLE",
    }

    try:
        demo_enabled = (
            os.getenv("ATLAS_DEMO_SEED", "true").lower() in {"1", "true", "yes"}
            and (
                os.getenv("ATLAS_ENV", "development").lower() != "production"
                or os.getenv("ATLAS_DEMO_MODE", "false").lower()
                in {"1", "true", "yes"}
            )
        )
        if demo_enabled:
            for table in CORE_TABLES:
                target.execute(
                    f'CREATE TABLE "{table}" ({schemas[table]})'
                )
            target.execute("""
                INSERT INTO patients VALUES
                (1, 'Diabetes', 'Texas'),
                (2, 'Diabetes', 'Texas'),
                (3, 'Hypertension', 'California'),
                (4, 'Diabetes', 'Florida'),
                (5, 'Asthma', 'Texas')
            """)
            target.execute("""
                INSERT INTO providers VALUES
                (101, 'Houston Medical'),
                (102, 'Dallas Care'),
                (103, 'Texas Health')
            """)
            target.execute("""
                INSERT INTO claims VALUES
                (1001, 1, 101, 5000),
                (1002, 2, 101, 8000),
                (1003, 4, 102, 12000),
                (1004, 5, 103, 2000)
            """)
            target.execute("""
                INSERT INTO payments VALUES
                (1, 1001, 4500),
                (2, 1002, 7500),
                (3, 1003, 11000),
                (4, 1004, 1800)
            """)
    finally:
        target.close()


def get_db_path() -> Path:
    workspace_id = get_workspace_id()
    if not workspace_id:
        return DB_PATH

    if not re.fullmatch(r"[a-f0-9-]{36}", workspace_id):
        raise ValueError("Invalid workspace identifier")

    path = BASE_DIR / "workspaces" / workspace_id / "atlas.db"
    if not path.exists():
        _create_workspace_database(path)
    return path
