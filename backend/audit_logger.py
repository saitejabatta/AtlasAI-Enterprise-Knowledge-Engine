import json
from datetime import datetime, timezone
from pathlib import Path
from storage_paths import DATA_DIR
from workspace_context import get_workspace_id


BASE_DIR = DATA_DIR


def audit_log_path():
    workspace_id = get_workspace_id()
    if not workspace_id:
        raise RuntimeError("Workspace context is required")
    return BASE_DIR / "workspaces" / workspace_id / "audit_log.jsonl"


def write_audit_event(event):
    path = audit_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    audit_event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **event,
    }

    with path.open(
        "a",
        encoding="utf-8"
    ) as file:
        file.write(
            json.dumps(
                audit_event,
                default=str
            )
            + "\n"
        )


def read_audit_events(limit=100):
    path = audit_log_path()
    if not path.exists():
        return []

    lines = path.read_text(
        encoding="utf-8"
    ).splitlines()

    events = []

    for line in lines[-limit:]:
        try:
            events.append(
                json.loads(line)
            )
        except json.JSONDecodeError:
            continue

    return list(
        reversed(events)
    )
