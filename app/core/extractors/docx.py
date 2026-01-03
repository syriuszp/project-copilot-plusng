
from docx import Document
from .base import BaseExtractor

class DocxExtractor(BaseExtractor):
    def extract(self, path: str) -> str:
        try:
            doc = Document(path)
            text = []
            for para in doc.paragraphs:
                text.append(para.text)
            return "\n".join(text)
        except Exception as e:
            raise RuntimeError(f"DOCX extraction failed: {e}")
