
import pytest
import logging
from unittest.mock import patch, mock_open
from app.ui.config_loader import load_config

def test_legacy_search_enabled_mapping():
    """
    Verifies that top-level search_enabled: true is mapped to features.search_enabled: true.
    """
    yaml_content = """
search_enabled: true
fts_enabled: true
database:
  path: "test.db"
indexing:
  poll_interval: 60
extraction:
  ocr:
    enabled: false
paths:
  db_path: "test.db"
  ingest_dir: "data"
  processed_dir: "processed"
  logs_dir: "logs"
    """
    with patch("builtins.open", mock_open(read_data=yaml_content)):
        with patch("app.ui.config_loader.Path.exists", return_value=True):
            # config_loader uses Path(env_override) or default. 
            # We mock file loading.
            # load_config iterates files.
            
            # We need to mock os.environ to avoid picking up real env config
            with patch.dict("os.environ", {}, clear=True):
                 # Mock Path behavior to return our file when checked
                 config = load_config()
                 if config["status"] != "OK":
                     print(f"Config Error: {config.get('error')}")
                 
    assert config["status"] == "OK"
    data = config["data"]
    assert "features" in data
    assert data["features"]["search_enabled"] is True
    assert data["features"]["fts_enabled"] is True
    assert "search_enabled" not in data # Should be popped

def test_priority_features_over_legacy():
    """
    Verifies that features.search_enabled takes precedence.
    """
    yaml_content = """
search_enabled: false
features:
  search_enabled: true
database:
  path: "test.db"
indexing:
  poll_interval: 60
extraction:
  ocr:
    enabled: false
paths:
  db_path: "test.db"
  ingest_dir: "data"
  processed_dir: "processed"
  logs_dir: "logs"
    """
    with patch("builtins.open", mock_open(read_data=yaml_content)):
        with patch("app.ui.config_loader.Path.exists", return_value=True):
            with patch.dict("os.environ", {}, clear=True):
                 config = load_config()
                 
    data = config["data"]
    assert data["features"]["search_enabled"] is True # False from legacy ignored

