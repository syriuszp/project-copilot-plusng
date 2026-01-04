
import shutil
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ExternalTools:
    """
    Helper for detecting external binaries (Tesseract, Poppler).
    Logic:
    1. Check config override (e.g. features.extraction.ocr.tesseract_path)
    2. Check 'tools/' directory in project root.
    3. Check system PATH (shutil.which).
    """

    @staticmethod
    def check_binaries(config: Dict[str, Any] = None) -> Dict[str, bool]:
        config = config or {}
        features = config.get("features", {})
        extraction = features.get("extraction", {})
        
        # 1. Tesseract
        tesseract_bin = ExternalTools._find_binary("tesseract", "tesseract.exe", extraction.get("ocr", {}).get("tesseract_path"))
        
        # 2. Poppler (pdftoppm is usually the one checked)
        poppler_bin = ExternalTools._find_binary("pdftoppm", "pdftoppm.exe", extraction.get("ocr", {}).get("poppler_path"))
        
        results = {
            "tesseract": tesseract_bin is not None,
            "poppler": poppler_bin is not None
        }
        
        # Logging for visibility
        if not results["tesseract"] and extraction.get("ocr", False): # Only warn if OCR enabled
            logger.warning("OCR enabled but Tesseract binary not found (looked in tools/ and PATH).")
        
        if results["tesseract"]:
            logger.info(f"Tesseract found: {tesseract_bin}")
            
        return results

    @staticmethod
    def _find_binary(name: str, win_name: str, config_path: Optional[str] = None) -> Optional[str]:
        # 1. Config override
        if config_path and os.path.exists(config_path):
            return config_path
            
        target_name = win_name if os.name == 'nt' else name
        
        # 2. Local tools/ directory
        # Assuming project root is 3 levels up from app/core/external_tools.py?
        # app/core/external_tools.py -> app/core -> app -> [root]
        # Or relative to CWD.
        cwd = Path.cwd()
        local_path = cwd / "tools" / name / target_name # e.g. tools/tesseract/tesseract.exe
        if local_path.exists():
            return str(local_path)
            
        # Also check tools/<target_name> directly?
        local_direct = cwd / "tools" / target_name
        if local_direct.exists():
            return str(local_direct)
            
        # 3. System PATH
        return shutil.which(target_name)
