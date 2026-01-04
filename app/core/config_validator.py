
from pathlib import Path
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class ConfigValidator:
    """
    Validates configuration structure and types.
    """
    
    @staticmethod
    def validate(config: Dict[str, Any]) -> List[str]:
        errors = []
        
        # 1. Top-Level Sections
        if "features" not in config:
            errors.append("Missing section: 'features'")
        if "paths" not in config:
            errors.append("Missing section: 'paths'")
            
        # 2. Features Checks
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
        
        # 3. Paths Checks
        paths = config.get("paths", {})
        if not isinstance(paths, dict):
            errors.append("'paths' must be a dictionary")
        else:
            required_paths = ["db_path", "ingest_dir", "processed_dir", "logs_dir"]
            for p in required_paths:
                if p not in paths:
                    errors.append(f"Missing path config: 'paths.{p}'")
        
        return errors

    @staticmethod
    def _check_bool(section: dict, key: str, errors: list):
        if key in section and not isinstance(section[key], bool):
            errors.append(f"Field '{key}' must be boolean, got {type(section[key]).__name__}")
