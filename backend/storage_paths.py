import os
from pathlib import Path


CODE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("ATLAS_DATA_DIR", str(CODE_DIR))).expanduser().resolve()
