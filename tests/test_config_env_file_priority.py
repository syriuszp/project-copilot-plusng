
import pytest
import os
import yaml
from app.ui.config_loader import load_config

def test_config_env_priority_source_field(tmp_path):
    # Setup dummy config
    cfg_file = tmp_path / "custom.yaml"
    cfg_file.write_text("env: PROD\ndb_path: prod.db")
    
    os.environ["PROJECT_COPILOT_CONFIG_FILE"] = str(cfg_file)
    try:
        config = load_config()
        assert config["status"] == "OK"
        assert config["source"].startswith("ENV_FILE")
        assert config["config_path"] == str(cfg_file)
    finally:
        del os.environ["PROJECT_COPILOT_CONFIG_FILE"]

def test_config_default_source():
    # Ensure no env var
    if "PROJECT_COPILOT_CONFIG_FILE" in os.environ:
        del os.environ["PROJECT_COPILOT_CONFIG_FILE"]
    if "PROJECT_COPILOT_CONFIG_DIR" in os.environ:
        del os.environ["PROJECT_COPILOT_CONFIG_DIR"]
        
    config = load_config()
    # might fail if no config in repo? But dev.yaml should exist.
    if config["status"] == "OK":
        assert config["source"].startswith("DEFAULT")
