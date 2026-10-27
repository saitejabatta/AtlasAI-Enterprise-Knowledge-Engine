import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import duckdb

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from db_config import _create_workspace_database
from main import is_public_demo_mode


class PublicDemoModeTests(unittest.TestCase):
    def test_demo_mode_is_explicitly_configured(self):
        with patch.dict(os.environ, {"ATLAS_DEMO_MODE": "true"}):
            self.assertTrue(is_public_demo_mode())

        with patch.dict(os.environ, {"ATLAS_DEMO_MODE": "false"}):
            self.assertFalse(is_public_demo_mode())

    def test_production_demo_seed_loads_synthetic_data_only_when_enabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "demo.duckdb"
            env = {
                "ATLAS_ENV": "production",
                "ATLAS_DEMO_MODE": "true",
                "ATLAS_DEMO_SEED": "true",
            }
            with patch.dict(os.environ, env):
                _create_workspace_database(db_path)

            connection = duckdb.connect(str(db_path), read_only=True)
            try:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM patients").fetchone()[0],
                    5,
                )
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
