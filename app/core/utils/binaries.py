import shutil
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class BinaryChecker:
    @staticmethod
    def check_binaries(config: Dict[str, Any] = None) -> Dict[str, bool]:
        """
        Checks for required binaries (tesseract, poppler).
        """
        config = config or {}
        ocr_cfg = config.get("features", {}).get("extraction", {}) # Assuming pass root config or just features? 
        # Actually ConfigValidator struct is features.extraction.
        # Let's assume we pass the 'features.extraction' dict or root.
        # Flexible: pass root config.
        
        # Tesseract
        tesseract_cmd = "tesseract" # P2: Allow config override paths.ocr.tesseract_cmd
        has_tesseract = shutil.which(tesseract_cmd) is not None
        
        # Poppler (pdftoppm)
        poppler_cmd = "pdftoppm"
        has_poppler = shutil.which(poppler_cmd) is not None
        
        return {
            "tesseract": has_tesseract,
            "poppler": has_poppler
        }
