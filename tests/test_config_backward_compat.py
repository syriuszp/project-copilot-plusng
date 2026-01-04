
import pytest
import yaml
from app.ui.config_loader import load_config
from app.core.config_validator import ConfigValidator

@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.delenv("PROJECT_COPILOT_CONFIG_FILE", raising=False)
    monkeypatch.delenv("PROJECT_COPILOT_CONFIG_DIR", raising=False)
    monkeypatch.delenv("PROJECT_COPILOT_ENV", raising=False)

def test_legacy_config_mapping(tmp_path, monkeypatch, clean_env):
    """
    Test that top-level search_enabled is mapped to features.search_enabled.
    """
    config_file = tmp_path / "legacy.yaml"
    config_file.write_text("""
paths:
  db_path: db.sqlite
  ingest_dir: ingest
  processed_dir: proc
  logs_dir: logs
search_enabled: true
""", encoding='utf-8')
    
    monkeypatch.setenv("PROJECT_COPILOT_CONFIG_FILE", str(config_file))
    
    status = load_config()
    assert status["status"] == "OK"
    data = status["data"]
    
    # Check mapping
    assert "search_enabled" not in data
    assert "features" in data
    assert data["features"]["search_enabled"] is True

def test_missing_paths_error(tmp_path, monkeypatch, clean_env):
    """
    Test that validator catches missing paths.
    """
    config_file = tmp_path / "invalid.yaml"
    config_file.write_text("""
features:
  search_enabled: true
paths:
  db_path: db.sqlite
  # Missing ingest_dir etc
""", encoding='utf-8')
    
    monkeypatch.setenv("PROJECT_COPILOT_CONFIG_FILE", str(config_file))
    
    status = load_config()
    assert status["status"] == "ERROR"
    assert "Missing path config: 'paths.ingest_dir'" in status["error"]

def test_invalid_type_error(tmp_path, monkeypatch, clean_env):
    """
    Test that validator catches invalid types (bool expected).
    """
    config_file = tmp_path / "bad_type.yaml"
    config_file.write_text("""
paths:
  db_path: db.sqlite
  ingest_dir: ingest
  processed_dir: proc
  logs_dir: logs
features:
  search_enabled: "yes" # String instead of bool
""", encoding='utf-8')
    
    monkeypatch.setenv("PROJECT_COPILOT_CONFIG_FILE", str(config_file))
    
    status = load_config()
    assert status["status"] == "ERROR"
    assert "Field 'search_enabled' must be boolean" in status["error"]
