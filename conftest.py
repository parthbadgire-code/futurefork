"""
Pytest root configuration.
- Puts the repository root on sys.path.
- Runs tests offline (no LLM calls) against a throwaway SQLite database,
  never the developer's ./futurefork.db.
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ["FUTUREFORK_OFFLINE"] = "1"
_TEST_DB = Path(tempfile.mkdtemp(prefix="futurefork-test-")) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
