"""The tests run on the example data of data/, without a database (pure logic)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://unused")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATA_DIR", str(ROOT / "data"))

import pytest  # noqa: E402

from server import content  # noqa: E402


@pytest.fixture(autouse=True)
def game_data():
    content.load()
