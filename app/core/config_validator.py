
from pathlib import Path
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class ConfigValidator:
    """
    Validates configuration structure and types.
    Strict enforcement for Epic 3.1 Hardening.
    """
    
    @staticmethod
    def validate(config: Dict[str, Any]) -> List[str]:
        errors = []
        
        # 1. Top-Level Sections
        if "features" not in config:
            errors.append("Missing required section: 'features'")
        if "paths" not in config:
            errors.append("Missing required section: 'paths'")
            
        # 2. Features Checks (Strict bools)
        features = config.get("features", {})
        if not isinstance(features, dict):
             errors.append("'features' must be a dictionary")
        else:
            ConfigValidator._check_bool(features, "search_enabled", errors)
            ConfigValidator._check_bool(features, "fts_enabled", errors)
            
            # Extraction
            extraction = features.get("extraction", {})
            if extraction:
                 if not isinstance(extraction, dict):
                    errors.append("'features.extraction' must be a dictionary")
                 else:
                    ConfigValidator._check_bool(extraction, "images", errors)
                    ConfigValidator._check_bool(extraction, "ocr", errors)
                    ConfigValidator._check_bool(extraction, "docx", errors)
                    ConfigValidator._check_bool(extraction, "pdf", errors)
        
        # 3. Paths Checks (Existence & Type)
        paths = config.get("paths", {})
        if not isinstance(paths, dict):
            errors.append("'paths' must be a dictionary")
        else:
            required_paths = ["db_path", "ingest_dir", "processed_dir", "logs_dir"]
            for p in required_paths:
                if p not in paths:
                    errors.append(f"Missing path config: 'paths.{p}'")
                else:
                    # Check existence logic? 
                    # DoD says: "jeśli nie istnieją -> utwórz albo daj jednoznaczny error w UI"
                    # We can try to create directories here or just validity of path string.
                    # Creating usage directories (logs, ingest) is safe. Creating db_path (file) is not.
                    val = paths[p]
                    if not isinstance(val, str):
                        errors.append(f"'paths.{p}' must be a string")
                        continue
                        
                    # Attempt creation for directories
                    if p in ["ingest_dir", "processed_dir", "logs_dir"]:
                        try:
                            path_obj = Path(val)
                            # Handle relative paths? Usually relative to Repo Root or CWD?
                            # Config paths usually resolved by app context, but let's try basic validity.
                            if not path_obj.exists():
                                # Try create (Audit requirement: "create or give error")
                                path_obj.mkdir(parents=True, exist_ok=True)
                        except Exception as e:
                            errors.append(f"Path 'paths.{p}' ({val}) is invalid or not creatable: {e}")

        # 4. Strict Logging of Results (DoD)
        if errors:
            logger.error(f"Config Validation Failed: {errors}")
        else:
            logger.info("Config OK: Features=%s", features)
            
        return errors

    @staticmethod
    def _check_bool(section: dict, key: str, errors: list):
        if key in section and not isinstance(section[key], bool):
            errors.append(f"Field '{key}' must be boolean, got {type(section[key]).__name__}")
