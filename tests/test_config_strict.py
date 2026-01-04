
import pytest
import yaml
from pathlib import Path
from unittest.mock import MagicMock, patch
from app.core.config_validator import ConfigValidator

def test_config_strict_valid(tmp_path):
    # Valid config
    config = {
        "features": {
            "search_enabled": True, 
            "fts_enabled": False,
            "extraction": {"images": True, "ocr": False, "docx": True, "pdf": True}
        },
        "paths": {
            "db_path": "foo.db",
            "ingest_dir": str(tmp_path / "ingest"),
            "processed_dir": str(tmp_path / "processed"),
            "logs_dir": str(tmp_path / "logs")
        }
    }
    errors = ConfigValidator.validate(config)
    assert not errors
    
    # Should create directories
    assert (tmp_path / "ingest").exists()
    assert (tmp_path / "processed").exists()
    assert (tmp_path / "logs").exists()

def test_config_strict_missing_paths():
    config = {
        "features": {"search_enabled": True},
        "paths": {"db_path": "foo.db"} # Missing ingest/logs/processed
    }
    errors = ConfigValidator.validate(config)
    assert any("Missing path config" in e for e in errors)
    assert len(errors) >= 3

def test_config_strict_bad_types():
    config = {
        "features": {"search_enabled": "yes"}, # Str not Bool
        "paths": {"db_path": "db"}
    }
    errors = ConfigValidator.validate(config)
    assert any("must be boolean" in e for e in errors)

