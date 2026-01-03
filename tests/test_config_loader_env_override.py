
import os
import pytest
import yaml
from pathlib import Path
from app.ui.config_loader import load_config

@pytest.fixture
def clean_env():
    """Ensure environment is clean before and after tests."""
    vars_to_clear = [
        "PROJECT_COPILOT_CONFIG_FILE",
        "PROJECT_COPILOT_CONFIG_DIR",
        "PROJECT_COPILOT_ENV"
    ]
    old_values = {}
    for v in vars_to_clear:
        old_values[v] = os.environ.get(v)
        if v in os.environ:
            del os.environ[v]
    
    yield
    
    # Restore
    for v, val in old_values.items():
        if val is not None:
            os.environ[v] = val
        elif v in os.environ:
            del os.environ[v]

def test_load_config_defaults(clean_env):
    """Test default behavior (no overrides)."""
    # Assuming the repo has some config or handles missing gracefully
    config = load_config()
    # status OK or ERROR is fine, just shouldn't crash
    assert "status" in config
    assert "env" in config 
    assert config["env"] == "DEV" # Default fallback

def test_config_file_override(clean_env, tmp_path):
    """Test PROJECT_COPILOT_CONFIG_FILE override."""
    # Create a dummy config file
    cfg_file = tmp_path / "custom_config.yaml"
    db_file = tmp_path / "my_db.sqlite"
    
    data = {
        "setting": "custom_value",
        "database": {"path": "my_db.sqlite"} # Relative path
    }
    
    with open(cfg_file, "w") as f:
        yaml.dump(data, f)
        
    os.environ["PROJECT_COPILOT_CONFIG_FILE"] = str(cfg_file)
    
    config = load_config()
    
    assert config["status"] == "OK"
    assert config["config_path"] == str(cfg_file)
    assert config["data"]["setting"] == "custom_value"
    
    # DB path should be resolved relative to config dir (tmp_path)
    expected_db_path = str(tmp_path / "my_db.sqlite")
    assert config["db_path"] == expected_db_path

def test_config_dir_override(clean_env, tmp_path):
    """Test PROJECT_COPILOT_CONFIG_DIR override."""
    # Create general.yaml and prod.yaml
    general = tmp_path / "general.yaml"
    prod = tmp_path / "prod.yaml"
    
    with open(general, "w") as f:
        yaml.dump({"general_key": "gen_val"}, f)
        
    with open(prod, "w") as f:
        yaml.dump({"env_key": "prod_val"}, f)
        
    os.environ["PROJECT_COPILOT_CONFIG_DIR"] = str(tmp_path)
    os.environ["PROJECT_COPILOT_ENV"] = "PROD"
    
    config = load_config()
    
    assert config["status"] == "OK"
    assert config["env"] == "PROD"
    assert config["data"]["general_key"] == "gen_val"
    assert config["data"]["env_key"] == "prod_val"
    # config_path should point to the env-specific file (as per logic)
    assert config["config_path"] == str(prod)

def test_absolute_db_path_preserved(clean_env, tmp_path):
    """Test that implicit absolute path is preserved."""
    cfg_file = tmp_path / "abs_db.yaml"
    # On windows, assume C:/... or similar if we really wanted to test strict abs
    # But using Path(tmp_path) is already absolute.
    abs_db = str(tmp_path / "absolute.db")
    
    data = {
        "paths": {"db_path": abs_db}
    }
    
    with open(cfg_file, "w") as f:
        yaml.dump(data, f)
        
    os.environ["PROJECT_COPILOT_CONFIG_FILE"] = str(cfg_file)
    
    config = load_config()
    assert config["db_path"] == abs_db
