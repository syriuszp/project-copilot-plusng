from docx import Document
from .base import BaseExtractor
from .models import ExtractResult

class DocxExtractor(BaseExtractor):
    def extract(self, path: str) -> ExtractResult:
        try:
            doc = Document(path)
            text = []
            for para in doc.paragraphs:
                text.append(para.text)
            return ExtractResult(content="\n".join(text), metadata={"source": "text"})
        except Exception as e:
            return ExtractResult(content=None, error=str(e), metadata={"source": "error"})
