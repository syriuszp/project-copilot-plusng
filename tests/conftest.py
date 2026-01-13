
import sys
from pathlib import Path

# Fix PYTHONPATH for CI/tests to find 'app' package
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os
import pytest
from unittest.mock import patch

@pytest.fixture(autouse=True)
def mock_env_vars():
    """Globally mock essential ENV vars for all tests to prevent API Key errors."""
    with patch.dict(os.environ, {
        "GEMINI_API_KEY": "test_key",
        "PROJECT_COPILOT_ENV": "TEST"
    }):
        yield
