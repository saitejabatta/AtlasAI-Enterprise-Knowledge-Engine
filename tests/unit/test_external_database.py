import sys
import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine


BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import data_sources
import db_config
from executor import execute_query
from query_compiler import compile_sql
from relationships import get_relationships
from workspace_context import reset_workspace_id, set_workspace_id


class ExternalDatabaseTests(unittest.TestCase):
    def test_database_type_must_match_url_and_production_rejects_sqlite(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            data_sources.validate_connection_target(
                "PostgreSQL",
                "sqlite:///:memory:",
            )

        with patch.dict(os.environ, {"ATLAS_ENV": "production"}):
            with self.assertRaisesRegex(ValueError, "disabled in production"):
                data_sources.validate_connection_target(
                    "SQLite",
                    "sqlite:///:memory:",
                )

    def test_production_database_hosts_must_be_allowlisted_exactly(self):
        with patch.dict(
            os.environ,
            {
                "ATLAS_ENV": "production",
                "ATLAS_DATABASE_HOST_ALLOWLIST": "warehouse.example.com",
            },
        ):
            data_sources.validate_connection_target(
                "postgresql",
                "postgresql://atlas:secret@warehouse.example.com/analytics",
            )
            with self.assertRaisesRegex(ValueError, "exact host"):
                data_sources.validate_connection_target(
                    "postgresql",
                    "postgresql://atlas:secret@other.example.com/analytics",
                )

        with patch.dict(
            os.environ,
            {
                "ATLAS_ENV": "production",
                "ATLAS_DATABASE_HOST_ALLOWLIST": "",
            },
        ):
            with self.assertRaisesRegex(ValueError, "exact host"):
                data_sources.validate_connection_target(
                    "mysql",
                    "mysql+pymysql://atlas:secret@warehouse.example.com/analytics",
                )

    def test_sqlite_connection_metadata_and_query_pushdown(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            backend_root = root / "backend"
            source_path = root / "customer-data.db"
            source_engine = create_engine(f"sqlite:///{source_path}")
            with source_engine.begin() as connection:
                connection.exec_driver_sql(
                    "CREATE TABLE regions (region_id INTEGER PRIMARY KEY, region_name TEXT)"
                )
                connection.exec_driver_sql(
                    "CREATE TABLE customers (customer_id INTEGER, region_id INTEGER REFERENCES regions(region_id))"
                )
                connection.exec_driver_sql(
                    "INSERT INTO regions VALUES (1, 'Texas'), (2, 'Ohio')"
                )
                connection.exec_driver_sql(
                    "INSERT INTO customers VALUES (1, 1), (2, 1), (3, 2)"
                )
            source_engine.dispose()

            workspace_id = str(uuid4())
            token = set_workspace_id(workspace_id)
            try:
                with (
                    patch.object(data_sources, "BASE_DIR", backend_root),
                    patch.object(db_config, "BASE_DIR", backend_root),
                    patch.object(data_sources, "encrypt_secret", lambda value: value),
                    patch.object(data_sources, "decrypt_secret", lambda value: value),
                ):
                    source = data_sources.connect_database(
                        "customer source",
                        "SQLite",
                        f"sqlite:///{source_path}",
                    )
                    table_names = {
                        table["name"]: table["virtual_table"]
                        for table in source["tables"]
                    }
                    customers = table_names["customers"]
                    regions = table_names["regions"]
                    self.assertEqual(len(source["relationships"]), 1)
                    self.assertEqual(len(get_relationships()), 4)
                    plan = {
                        "intent": "count",
                        "entity": customers,
                        "aggregation": "COUNT",
                        "metric": "",
                        "group_by": "",
                        "filters": [
                            {
                                "table": regions,
                                "column": "region_name",
                                "operator": "=",
                                "value": "Texas",
                            }
                        ],
                        "joins": [
                            {
                                "left": f"{customers}.region_id",
                                "right": f"{regions}.region_id",
                            }
                        ],
                    }
                    sql = compile_sql(plan)
                    result = execute_query(sql, plan)

            finally:
                reset_workspace_id(token)

        self.assertEqual(
            {table["name"] for table in source["tables"]},
            {"customers", "regions"},
        )
        self.assertEqual(int(result.iloc[0]["total_count"]), 2)


if __name__ == "__main__":
    unittest.main()
