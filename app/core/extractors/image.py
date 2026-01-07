import subprocess
import os
from .base import BaseExtractor
from .models import ExtractResult
from app.core.external_tools import ExternalTools

class ImageExtractor(BaseExtractor):
    def extract(self, path: str) -> ExtractResult:
        # Check if image extraction feature is enabled
        features_cfg = self.config.get("features", {})
        extraction_cfg = features_cfg.get("extraction", {})
        if not extraction_cfg:
             extraction_cfg = self.config.get("extraction", {})
        
        # If images disabled, return None (NOT_EXTRACTABLE)
        if not extraction_cfg.get("images", False):
            print(f"[DEBUG] ImageExtractor: Images disabled in config.")
            return ExtractResult(content=None, metadata={"source": "disabled"})
            
        ocr_val = extraction_cfg.get("ocr", False)
        # Images require OCR
        if not ocr_val:
            print(f"[DEBUG] ImageExtractor: OCR disabled in config.")
            return ExtractResult(content=None, metadata={"source": "ocr_disabled"})

        # Check Binaries via centralized logic (Option A)
        tool_status = ExternalTools.check_binaries(self.config)
        tess_status = tool_status.get("tesseract")
        
        if not tess_status or tess_status.status != "AVAILABLE":
             return ExtractResult(content=None, error=None, metadata={"source": "no_binary_fallback"})
             
        tesseract_bin = tess_status.path

        try:
             # Run Tesseract
             # tesseract <input> stdout
             # stdout=PIPE, stderr=PIPE
            print(f"[DEBUG] ImageExtractor: Running tesseract on {path}")
            proc = subprocess.run(
                [tesseract_bin, path, "stdout"],
                capture_output=True,
                text=True,
                check=False
            )
            
            if proc.returncode != 0:
                print(f"[ERROR] Tesseract failed: {proc.stderr}")
                return ExtractResult(content=None, error=f"OCR Warning: {proc.stderr}", metadata={"source": "error"})
                
            text = proc.stdout.strip()
            print(f"[DEBUG] Tesseract output length: {len(text)}")
            
            if not text:
                print(f"[DEBUG] Tesseract returned empty text.")
                return ExtractResult(content=None, metadata={"source": "ocr_empty"})
                 
            return ExtractResult(content=text, metadata={"source": "ocr"})
             
        except subprocess.CalledProcessError as e:
            # Capture stderr for error message but don't spam console
            err_msg = e.stderr or str(e)
            return ExtractResult(content=None, error=f"OCR Failed: {err_msg[:200]}", metadata={"source": "error"})
        except Exception as e:
            return ExtractResult(content=None, error=str(e), metadata={"source": "error"})
