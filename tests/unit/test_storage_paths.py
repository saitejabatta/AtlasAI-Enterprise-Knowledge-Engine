import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import storage_paths


class StoragePathTests(unittest.TestCase):
    def test_data_directory_uses_configured_persistent_mount(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"ATLAS_DATA_DIR": temp_dir}):
                importlib.reload(storage_paths)
                self.assertEqual(storage_paths.DATA_DIR, Path(temp_dir).resolve())

        importlib.reload(storage_paths)


if __name__ == "__main__":
    unittest.main()
