import json
from datetime import datetime, timezone
from pathlib import Path
from storage_paths import DATA_DIR
from workspace_context import get_workspace_id


BASE_DIR = DATA_DIR


def overrides_path():
    workspace_id = get_workspace_id()
    if not workspace_id:
        raise RuntimeError("Workspace context is required")
    return BASE_DIR / "workspaces" / workspace_id / "metadata_overrides.json"


def ensure_overrides_file():
    path = overrides_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            "{}",
            encoding="utf-8"
        )


def read_metadata_overrides():
    ensure_overrides_file()

    return json.loads(
        overrides_path().read_text(
            encoding="utf-8"
        )
    )


def write_metadata_overrides(overrides):
    ensure_overrides_file()

    overrides_path().write_text(
        json.dumps(
            overrides,
            indent=2
        ),
        encoding="utf-8"
    )


def get_table_override(table_name):
    overrides = read_metadata_overrides()

    return overrides.get(
        table_name,
        {
            "description": "",
            "columns": {},
            "sensitive_columns": [],
        }
    )


def update_table_override(table_name, payload):
    overrides = read_metadata_overrides()
    current = get_table_override(
        table_name
    )
    updated = {
        **current,
        "description": payload.get(
            "description",
            current.get("description", "")
        ),
        "columns": payload.get(
            "columns",
            current.get("columns", {})
        ),
        "sensitive_columns": payload.get(
            "sensitive_columns",
            current.get("sensitive_columns", [])
        ),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    overrides[table_name] = updated
    write_metadata_overrides(
        overrides
    )

    return updated
