
from pypdf import PdfReader
from .base import BaseExtractor

class PdfExtractor(BaseExtractor):
    def extract(self, path: str) -> str:
        try:
            reader = PdfReader(path)
            text = []
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted and extracted.strip():
                    text.append(extracted)
            
            full_text = "\n".join(text)
            
            # Fallback for Scanned PDFs
            if not full_text.strip():
                extraction_cfg = self.config.get("extraction", {})
                if extraction_cfg.get("ocr", False):
                    # Placeholder: Real implementation requires pytesseract/pdf2image
                    return "[OCR Content Placeholder: Scanned PDF detected]"
                return None # Signals 'not_extractable'
                
            return full_text
        except Exception as e:
            raise RuntimeError(f"PDF extraction failed: {e}")
