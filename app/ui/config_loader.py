
import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from app.core.config_validator import ConfigValidator

logger = logging.getLogger(__name__)


class ConfigResolver:
    """
    Standardized access to configuration.
    Ensures single source of truth for feature flags and settings.
    Wrapper around the raw config dictionary.
    """
    def __init__(self, config_data: Dict[str, Any]):
        self._data = config_data
        self._features = config_data.get("features", {})
        self._extraction = self._features.get("extraction", {})

    @property
    def raw_config(self) -> Dict[str, Any]:
        return self._data
        
    @property
    def is_search_enabled(self) -> bool:
        # P0 Hardening: Centralized logic
        return bool(self._features.get("search_enabled", False))

    @property
    def is_fts_enabled(self) -> bool:
        return bool(self._features.get("fts_enabled", False))
        
    def get_extraction_setting(self, key: str, default: Any = None) -> Any:
        return self._extraction.get(key, default)

    def get_db_path(self) -> Optional[str]:
        # Logic already in config_loader but good to have here too as accessor
        # But config loader returns status dict with db_path separately.
        # This resolver wraps the 'data' part usually.
        return None 

def load_config() -> Dict[str, Any]:
    """
    Loads configuration from YAML files and environment variables.
    Returns a dictionary with configuration and status metadata.
    The 'data' key will contain the normalized configuration.
    """
    config_status = {
        "status": "OK",
        "error": None,
        "env": get_env(),
        "config_path": None,
        "db_path": None,
        "data": {}
    }

    # --- 1. Read Overrides from ENV ---
    env_override_file = os.environ.get("PROJECT_COPILOT_CONFIG_FILE")
    env_override_dir = os.environ.get("PROJECT_COPILOT_CONFIG_DIR")
    
    # Priority for ENV: ENV var > default detection
    env = config_status["env"] 

    # --- 2. Determine Config Directory and Files ---
    if env_override_file:
        config_path = Path(env_override_file)
        config_dir = config_path.parent
        
        # FIX: Ensure general.yaml is loaded for defaults/flags
        general_cfg = config_dir / "general.yaml"
        # If config_path IS general.yaml, don't load twice
        if general_cfg.exists() and general_cfg.resolve() != config_path.resolve():
            files_to_load = [general_cfg, config_path]
            logger.info(f"Loading base config from {general_cfg}")
        else:
            files_to_load = [config_path]
            
        config_status["config_path"] = str(config_path)
        config_status["source"] = "ENV_FILE (PROJECT_COPILOT_CONFIG_FILE)"
    elif env_override_dir:
        config_dir = Path(env_override_dir)
        files_to_load = [
            config_dir / "general.yaml",
            config_dir / f"{env.lower()}.yaml"
        ]
        config_status["source"] = "ENV_DIR (PROJECT_COPILOT_CONFIG_DIR)"
    else:
        project_root = Path(__file__).resolve().parent.parent.parent
        config_dir = project_root / "config"
        files_to_load = [
            config_dir / "general.yaml",
            config_dir / f"{env.lower()}.yaml"
        ]
        config_status["source"] = "DEFAULT (repo/site-packages)"

    # --- 3. Load Configs ---
    loaded_config = {}
    files_found = 0
    
    try:
        # Pre-populate default structure
        loaded_config["features"] = {
            # search_enabled default handled in Resolver (False)
            "extraction": {"pdf": True, "images": False, "ocr": False}
        }
        
        for file_path in files_to_load:
            if file_path.exists():
                files_found += 1
                if not env_override_file:
                     config_status["config_path"] = str(file_path)

                with open(file_path, "r", encoding="utf-8") as f:
                    # Recursive update needed ideally, but simple update for now
                    # For hardening, we might want deep merge, but MVP:
                    file_data = yaml.safe_load(f) or {}
                    
                    # Manual deep merge for 'features' if strictly needed, 
                    # but simple update is risky if it wipes defaults.
                    # Let's use simple logic: top level keys overwrite.
                    if "features" in file_data and "features" in loaded_config:
                         loaded_config["features"].update(file_data["features"])
                         del file_data["features"]
                         
                    loaded_config.update(file_data)
        
        if files_found == 0:
            config_status["status"] = "ERROR"
            config_status["error"] = f"No config files found in {config_dir} (tried: {[str(f) for f in files_to_load]})"
        else:
            # --- 3b. Backward Compatibility (P0 Hardening) ---
            # Ensure 'features' exists and load legacy top-level keys if missing in features
            fts = loaded_config.get("features", {})
            
            # Legacy: 'search_enabled' at top level
            if "search_enabled" in loaded_config:
                legacy_search = loaded_config.pop("search_enabled")
                if "search_enabled" not in fts:
                    fts["search_enabled"] = bool(legacy_search)
                    logger.warning("Config: Mapped top-level 'search_enabled' to 'features.search_enabled'.")
            
            # Legacy: 'fts_enabled' at top level
            if "fts_enabled" in loaded_config:
                legacy_fts = loaded_config.pop("fts_enabled")
                if "fts_enabled" not in fts:
                     fts["fts_enabled"] = bool(legacy_fts)

            # Legacy: 'features.search.enabled'
            if "search" in fts and isinstance(fts["search"], dict):
                if "enabled" in fts["search"] and "search_enabled" not in fts:
                     fts["search_enabled"] = fts["search"]["enabled"]
                     
            loaded_config["features"] = fts

            # --- 3c. Validation (Hardening) ---
            validation_errors = ConfigValidator.validate(loaded_config)
            if validation_errors:
                config_status["status"] = "ERROR"
                config_status["error"] = "Invalid Configuration:\n" + "\n".join(validation_errors)
                # We still allow loading data for debugging config
                config_status["data"] = loaded_config
                return config_status

            config_status["data"] = loaded_config
            
            # [FINAL-P1] SAFE DEFAULT Guard
            if env == "PROD":
                feat = loaded_config.get("features", {})
                sem = feat.get("semantic_enabled", False)
                if sem:
                    logger.warning("🚨 PROD WARNING: Semantic Search is ENABLED. Ensure Vector DB is provisioned and costs monitored.")
            raw_db_path = None
            if "database" in loaded_config and "path" in loaded_config["database"]:
                 raw_db_path = loaded_config["database"]["path"]
            elif "paths" in loaded_config and "db_path" in loaded_config["paths"]:
                 raw_db_path = loaded_config["paths"]["db_path"]
            elif "db_path" in loaded_config: # Legacy support
                 raw_db_path = loaded_config["db_path"]
            
            # FIX: Always resolve relative DB paths against PROJECT ROOT, not config dir.
            project_root = Path(__file__).resolve().parent.parent.parent
            
            if raw_db_path:
                db_path_obj = Path(raw_db_path)
                if not db_path_obj.is_absolute():
                    config_status["db_path"] = str(project_root / raw_db_path)
                else:
                    config_status["db_path"] = str(db_path_obj)
            else:
                 config_status["db_path"] = None
            
            # --- 5. Tool Status (Risk 2) ---
            # Resolve tools early so UI knows status
            try:
                from app.core.external_tools import ExternalTools
                tools = ExternalTools.check_binaries(loaded_config)
                tool_status_dict = {}
                for name, status in tools.items():
                    tool_status_dict[name] = {
                        "available": status.status == "AVAILABLE",
                        "path": status.path,
                        "error": None if status.status == "AVAILABLE" else "Binary not found"
                    }
                
                # Ensure runtime dict exists
                if "runtime" not in loaded_config:
                    loaded_config["runtime"] = {}
                loaded_config["runtime"]["tool_status"] = tool_status_dict
            except Exception as e:
                logger.warning(f"Failed to resolve tools in config loader: {e}")

            # Log startup config (DoD)
            features = loaded_config.get("features", {})
            logger.info(
                f"Config loaded: env={env}, config={config_status['config_path']}, "
                f"features.search_enabled={features.get('search_enabled')}, "
                f"features.fts_enabled={features.get('fts_enabled')}"
            )

    except Exception as e:
        config_status["status"] = "ERROR"
        config_status["error"] = str(e)
        import traceback
        traceback.print_exc()

    return config_status


def get_env() -> str:
    """
    Detects the current environment.
    Checks PROJECT_COPILOT_ENV, defaults to DEV.
    """
    return os.environ.get("PROJECT_COPILOT_ENV", "DEV").upper()
