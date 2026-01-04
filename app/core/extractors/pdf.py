from pypdf import PdfReader
from .base import BaseExtractor
from .models import ExtractResult

class PdfExtractor(BaseExtractor):
    def extract(self, path: str) -> ExtractResult:
        try:
            reader = PdfReader(path)
            text = []
            for i, page in enumerate(reader.pages):
                extracted = page.extract_text()
                if extracted and extracted.strip():
                    text.append(extracted)
                else:
                    # Placeholder for future VLM
                    # [IMAGE page=3 index=1 extractable=false]
                    text.append(f"[IMAGE page={i+1} index=1 extractable=false]")
            
            full_text = "\n".join(text)
            
            # If mostly empty/placeholder, check for Scanned
            has_real_text = any(t for t in text if not t.startswith("[IMAGE"))
            
            if not has_real_text:
                extraction_cfg = self.config.get("extraction", {})
                binaries = self.config.get("binaries", {})
                
                if extraction_cfg.get("ocr", False):
                    if binaries.get("tesseract") and binaries.get("poppler"):
                        # Placeholder: Real implementation requires pytesseract/pdf2image
                         return ExtractResult(
                             content="[OCR Content Placeholder: Scanned PDF detected]",
                             metadata={"source": "ocr", "method": "placeholder"}
                         )
                    else:
                        return ExtractResult(content=None, error="OCR binaries missing", metadata={"source": "ocr_failed"})
                
                # OCR disabled
                return ExtractResult(content=None, metadata={"source": "image_only"})
                
            return ExtractResult(content=full_text, metadata={"source": "text"})
            
        except Exception as e:
            return ExtractResult(content=None, error=str(e), metadata={"source": "error"})
