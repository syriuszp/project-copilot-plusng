
from pypdf import PdfReader
from .base import BaseExtractor

class PdfExtractor(BaseExtractor):
    def extract(self, path: str) -> str:
        try:
            reader = PdfReader(path)
            text = []
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text.append(extracted)
            return "\n".join(text)
        except Exception as e:
            raise RuntimeError(f"PDF extraction failed: {e}")
