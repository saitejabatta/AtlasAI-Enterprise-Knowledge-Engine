import sys
import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import duckdb


BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import db_config
from workspace_context import reset_workspace_id, set_workspace_id


class WorkspaceIsolationTests(unittest.TestCase):
    def test_each_workspace_gets_a_separate_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            template = base_dir / "atlas.db"
            seed = duckdb.connect(str(template))
            seed.execute(
                "CREATE TABLE patients (patient_id INTEGER, diagnosis VARCHAR, state VARCHAR)"
            )
            seed.execute("INSERT INTO patients VALUES (1, 'Diabetes', 'Texas')")
            seed.close()

            with (
                patch.object(db_config, "BASE_DIR", base_dir),
                patch.dict(os.environ, {"ATLAS_ENV": "production"}),
            ):
                workspace_a = str(uuid4())
                workspace_b = str(uuid4())

                token = set_workspace_id(workspace_a)
                try:
                    path_a = db_config.get_db_path()
                    connection_a = duckdb.connect(str(path_a))
                    connection_a.execute(
                        "CREATE TABLE private_upload (secret VARCHAR)"
                    )
                    connection_a.execute(
                        "INSERT INTO private_upload VALUES ('workspace A only')"
                    )
                    connection_a.close()
                finally:
                    reset_workspace_id(token)

                token = set_workspace_id(workspace_b)
                try:
                    path_b = db_config.get_db_path()
                    connection_b = duckdb.connect(str(path_b))
                    tables_b = {
                        row[0]
                        for row in connection_b.execute("SHOW TABLES").fetchall()
                    }
                    connection_b.close()
                finally:
                    reset_workspace_id(token)

            self.assertNotEqual(path_a, path_b)
            self.assertEqual(tables_b, set())


if __name__ == "__main__":
    unittest.main()
