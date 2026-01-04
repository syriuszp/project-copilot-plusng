from .base import BaseExtractor
from .models import ExtractResult

class ImageExtractor(BaseExtractor):
    def extract(self, path: str) -> ExtractResult:
        # Check if image extraction feature is enabled
        extraction_cfg = self.config.get("extraction", {})
        
        # If images disabled, return None (NOT_EXTRACTABLE)
        if not extraction_cfg.get("images", False):
            return ExtractResult(content=None, metadata={"source": "disabled"})
            
        # Images require OCR
        if not extraction_cfg.get("ocr", False):
            return ExtractResult(content=None, metadata={"source": "ocr_disabled"})

        binaries = self.config.get("binaries", {})
        if not binaries.get("tesseract"):
             return ExtractResult(content=None, error="Tesseract missing", metadata={"source": "no_binary"})

        try:
             # Real impl:
             # from PIL import Image
             # import pytesseract
             # return pytesseract.image_to_string(Image.open(path))
             return ExtractResult(content="[OCR Content Placeholder: Image text]", metadata={"source": "ocr"})
        except Exception as e:
            return ExtractResult(content=None, error=str(e), metadata={"source": "error"})
