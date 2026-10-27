import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import duckdb
from fastapi import UploadFile
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url

from db_config import get_db_path
from secrets_manager import (
    decrypt_secret,
    encrypt_secret
)
from storage_paths import DATA_DIR
from workspace_context import get_workspace_id


BASE_DIR = DATA_DIR
MAX_CSV_UPLOAD_BYTES = int(
    os.getenv("ATLAS_MAX_CSV_UPLOAD_BYTES", str(250 * 1024 * 1024))
)


def workspace_root():
    workspace_id = get_workspace_id()
    if not workspace_id:
        raise RuntimeError("Workspace context is required")
    return BASE_DIR / "workspaces" / workspace_id


def upload_directory():
    return workspace_root() / "uploads"


def data_sources_path():
    return workspace_root() / "data_sources.json"


def ensure_storage():
    root = workspace_root()
    root.mkdir(
        parents=True,
        exist_ok=True
    )
    upload_directory().mkdir(
        parents=True,
        exist_ok=True
    )

    path = data_sources_path()
    if not path.exists():
        path.write_text(
            "[]",
            encoding="utf-8"
        )


def quote_identifier(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def sanitize_table_name(name):
    normalized = re.sub(
        r"[^A-Za-z0-9_]+",
        "_",
        name.lower()
    ).strip("_")

    if not normalized:
        normalized = "uploaded_dataset"

    if normalized[0].isdigit():
        normalized = f"dataset_{normalized}"

    return normalized[:48]


def unique_table_name(base_name):
    conn = duckdb.connect(str(get_db_path()))
    existing = {
        row[0]
        for row in conn.execute(
            "SHOW TABLES"
        ).fetchall()
    }
    conn.close()

    table_name = base_name
    index = 2

    while table_name in existing:
        table_name = f"{base_name}_{index}"
        index += 1

    return table_name


def unique_virtual_table_name(base_name, used_names):
    virtual_name = base_name
    index = 2

    while virtual_name in used_names:
        virtual_name = f"{base_name}_{index}"
        index += 1

    used_names.add(virtual_name)

    return virtual_name


def redacted_connection_url(connection_url):
    return re.sub(
        r"://([^:/@]+):([^@]+)@",
        r"://\1:***@",
        connection_url
    )


def validate_connection_target(database_type, connection_url):
    type_key = database_type.strip().lower()
    allowed_schemes = {
        "postgresql": "postgresql",
        "mysql": "mysql",
        "sqlite": "sqlite",
    }
    expected_scheme = allowed_schemes.get(type_key)
    if not expected_scheme:
        raise ValueError("Supported database types are PostgreSQL, MySQL, and SQLite")

    try:
        scheme = make_url(connection_url).drivername.split("+", 1)[0].lower()
    except Exception as exc:
        raise ValueError("Invalid SQLAlchemy database URL") from exc
    if scheme != expected_scheme:
        raise ValueError(
            f"Database URL does not match the selected {database_type} type"
        )

    if (
        expected_scheme == "sqlite"
        and os.getenv("ATLAS_ENV", "development").lower() == "production"
    ):
        raise ValueError("SQLite file connections are disabled in production")

    if os.getenv("ATLAS_ENV", "development").lower() == "production":
        host = (make_url(connection_url).host or "").rstrip(".").lower()
        allowed_hosts = {
            item.strip().rstrip(".").lower()
            for item in os.getenv("ATLAS_DATABASE_HOST_ALLOWLIST", "").split(",")
            if item.strip()
        }
        if not host or not allowed_hosts or host not in allowed_hosts:
            raise ValueError(
                "Production database connections must use an exact host in "
                "ATLAS_DATABASE_HOST_ALLOWLIST"
            )


def read_sources():
    ensure_storage()

    return json.loads(
        data_sources_path().read_text(
            encoding="utf-8"
        )
    )


def write_sources(sources):
    ensure_storage()

    data_sources_path().write_text(
        json.dumps(
            sources,
            indent=2
        ),
        encoding="utf-8"
    )


def get_connection_url(source):
    encrypted_url = source.get(
        "encrypted_connection_url"
    )

    if encrypted_url:
        return decrypt_secret(
            encrypted_url
        )

    plain_url = source.get(
        "connection_url"
    )

    if plain_url:
        return plain_url

    raise ValueError(
        "Database connection URL is missing"
    )


def migrate_plaintext_connection_urls():
    sources = read_sources()
    changed = False
    migrated_sources = []

    for source in sources:
        if (
            source.get("type") == "DATABASE"
            and source.get("connection_url")
            and not source.get("encrypted_connection_url")
        ):
            source = {
                **source,
                "encrypted_connection_url": encrypt_secret(
                    source["connection_url"]
                )
            }
            source.pop(
                "connection_url",
                None
            )
            changed = True

        migrated_sources.append(source)

    if changed:
        write_sources(
            migrated_sources
        )

    return migrated_sources


def current_virtual_table_names(sources):
    names = set()

    for source in sources:
        if source.get("table"):
            names.add(source["table"])

        for table in source.get("tables", []):
            names.add(table["virtual_table"])

    return names


def get_table_profile(table_name):
    conn = duckdb.connect(str(get_db_path()))
    quoted_table = quote_identifier(table_name)

    row_count = conn.execute(
        f"SELECT COUNT(*) FROM {quoted_table}"
    ).fetchone()[0]

    columns = conn.execute(
        f"DESCRIBE {quoted_table}"
    ).fetchall()

    conn.close()

    return {
        "rows": row_count,
        "columns": [
            {
                "name": column[0],
                "type": column[1]
            }
            for column in columns
        ]
    }


async def ingest_csv(file: UploadFile):
    ensure_storage()

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise ValueError(
            "Only CSV files are supported in this version"
        )

    source_id = f"src_{uuid4().hex[:12]}"
    original_name = Path(file.filename.replace("\\", "/")).name
    if not original_name:
        original_name = "uploaded_dataset.csv"
    stored_path = upload_directory() / f"{source_id}_{original_name}"
    base_table_name = sanitize_table_name(
        Path(original_name).stem
    )
    table_name = unique_table_name(
        base_table_name
    )
    table_created = False

    try:
        total_bytes = 0
        with stored_path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > MAX_CSV_UPLOAD_BYTES:
                    raise ValueError(
                        f"CSV exceeds the {MAX_CSV_UPLOAD_BYTES // (1024 * 1024)} MB upload limit"
                    )
                output.write(chunk)

        if total_bytes == 0:
            raise ValueError("CSV file is empty")

        escaped_path = str(stored_path).replace("'", "''")
        conn = duckdb.connect(str(get_db_path()))
        try:
            conn.execute(
                f"""
                CREATE OR REPLACE TABLE {quote_identifier(table_name)} AS
                SELECT *
                FROM read_csv_auto(
                    '{escaped_path}',
                    HEADER = TRUE,
                    SAMPLE_SIZE = -1
                )
                """
            )
            table_created = True
        finally:
            conn.close()

        profile = get_table_profile(table_name)
        created_at = datetime.now(timezone.utc).isoformat()
        source = {
            "id": source_id,
            "name": original_name,
            "type": "CSV",
            "status": "connected",
            "table": table_name,
            "rows": profile["rows"],
            "columns": profile["columns"],
            "created_at": created_at,
            "updated_at": created_at,
        }

        sources = read_sources()
        sources.append(source)
        write_sources(sources)
        return source
    except Exception:
        stored_path.unlink(missing_ok=True)
        if table_created:
            conn = duckdb.connect(str(get_db_path()))
            try:
                conn.execute(
                    f"DROP TABLE IF EXISTS {quote_identifier(table_name)}"
                )
            finally:
                conn.close()
        raise


def list_data_sources():
    sources = migrate_plaintext_connection_urls()

    refreshed_sources = []

    for source in sources:
        if source.get("type") == "DATABASE":
            refreshed_sources.append(source)
            continue

        try:
            profile = get_table_profile(
                source["table"]
            )
            refreshed_sources.append({
                **source,
                "status": "connected",
                "rows": profile["rows"],
                "columns": profile["columns"],
            })
        except Exception:
            refreshed_sources.append({
                **source,
                "status": "disconnected",
            })

    return refreshed_sources


def delete_data_source(source_id):
    sources = read_sources()
    source = next(
        (
            item
            for item in sources
            if item["id"] == source_id
        ),
        None
    )

    if not source:
        raise ValueError(
            "Data source not found"
        )

    if source.get("type") != "DATABASE":
        conn = duckdb.connect(str(get_db_path()))
        conn.execute(
            f"DROP TABLE IF EXISTS {quote_identifier(source['table'])}"
        )
        conn.close()

    write_sources([
        item
        for item in sources
        if item["id"] != source_id
    ])

    for path in upload_directory().glob(f"{source_id}_*"):
        path.unlink(
            missing_ok=True
        )

    return {
        "deleted": True,
        "source": source
    }


def connect_database(name, database_type, connection_url):
    ensure_storage()

    if not name.strip():
        raise ValueError(
            "Database name is required"
        )

    if not connection_url.strip():
        raise ValueError(
            "Connection URL is required"
        )

    validate_connection_target(database_type, connection_url)

    source_id = f"db_{uuid4().hex[:12]}"
    sources = read_sources()
    used_names = current_virtual_table_names(sources)
    source_prefix = sanitize_table_name(name)

    engine = create_engine(connection_url)
    inspector = inspect(engine)
    tables = []
    table_lookup = {}

    schemas = inspector.get_schema_names()

    for schema in schemas:
        if schema in {
            "information_schema",
            "pg_catalog",
            "pg_toast",
            "mysql",
            "performance_schema",
            "sys",
        }:
            continue

        for table_name in inspector.get_table_names(schema=schema):
            table_base = sanitize_table_name(
                f"{source_prefix}_{schema}_{table_name}"
                if schema
                else f"{source_prefix}_{table_name}"
            )
            virtual_table = unique_virtual_table_name(
                table_base,
                used_names
            )
            columns = [
                {
                    "name": column["name"],
                    "type": str(column["type"])
                }
                for column in inspector.get_columns(
                    table_name,
                    schema=schema
                )
            ]

            virtual_table = {
                "schema": schema,
                "name": table_name,
                "virtual_table": virtual_table,
                "columns": columns,
            }
            tables.append(virtual_table)
            table_lookup[(schema, table_name)] = virtual_table["virtual_table"]

    relationships = []
    for table in tables:
        try:
            foreign_keys = inspector.get_foreign_keys(
                table["name"],
                schema=table.get("schema"),
            )
        except Exception:
            foreign_keys = []

        for foreign_key in foreign_keys:
            referred_table = foreign_key.get("referred_table")
            referred_schema = foreign_key.get("referred_schema") or table.get("schema")
            target_virtual = table_lookup.get((referred_schema, referred_table))
            if not target_virtual:
                target_virtual = table_lookup.get((None, referred_table))
            if not target_virtual:
                continue

            for local_column, target_column in zip(
                foreign_key.get("constrained_columns") or [],
                foreign_key.get("referred_columns") or [],
            ):
                relationships.append({
                    "from_table": table["virtual_table"],
                    "from_column": local_column,
                    "to_table": target_virtual,
                    "to_column": target_column,
                })

    engine.dispose()

    if not tables:
        raise ValueError(
            "No tables found in connected database"
        )

    created_at = datetime.now(timezone.utc).isoformat()
    source = {
        "id": source_id,
        "name": name,
        "type": "DATABASE",
        "database_type": database_type,
        "status": "connected",
        "table": "",
        "rows": 0,
        "columns": [],
        "tables": tables,
        "relationships": relationships,
        "encrypted_connection_url": encrypt_secret(
            connection_url
        ),
        "connection_url_redacted": redacted_connection_url(
            connection_url
        ),
        "created_at": created_at,
        "updated_at": created_at,
    }

    sources.append(source)
    write_sources(sources)

    return public_source(source)


def public_source(source):
    public = {
        key: value
        for key, value in source.items()
        if key not in {
            "connection_url",
            "encrypted_connection_url",
        }
    }

    return public


def list_public_data_sources():
    return [
        public_source(source)
        for source in list_data_sources()
    ]


def get_external_table_map():
    mapping = {}

    for source in migrate_plaintext_connection_urls():
        if source.get("type") != "DATABASE":
            continue

        connection_url = get_connection_url(
            source
        )

        for table in source.get("tables", []):
            mapping[table["virtual_table"]] = {
                "source_id": source["id"],
                "connection_url": connection_url,
                "schema": table.get("schema"),
                "table": table["name"],
            }

    return mapping


def get_execution_context_for_plan(plan):
    table_map = get_external_table_map()
    referenced_tables = {plan.get("entity")}

    for filter_obj in plan.get("filters", []) or []:
        referenced_tables.add(
            filter_obj.get("table")
        )

    group_by = plan.get("group_by")
    if group_by and "." in group_by:
        referenced_tables.add(
            group_by.split(".")[0]
        )

    for join in plan.get("joins", []) or []:
        for side in ("left", "right"):
            reference = join.get(side, "")

            if "." in reference:
                referenced_tables.add(
                    reference.split(".")[0]
                )

    external_tables = {
        table
        for table in referenced_tables
        if table in table_map
    }

    if not external_tables:
        return None

    source_ids = {
        table_map[table]["source_id"]
        for table in external_tables
    }

    if len(source_ids) != 1:
        raise ValueError(
            "Cross-database queries are not supported yet"
        )

    return {
        "connection_url": table_map[next(iter(external_tables))]["connection_url"],
        "tables": {
            table: table_map[table]
            for table in external_tables
        }
    }
