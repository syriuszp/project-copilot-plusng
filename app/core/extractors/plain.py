
import os
from .base import BaseExtractor
from .models import ExtractResult

class PlainTextExtractor(BaseExtractor):
    def extract(self, path: str) -> ExtractResult:
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            return ExtractResult(content=content, metadata={"source": "text"})
        except Exception as e:
            return ExtractResult(content=None, error=str(e), metadata={"source": "error"})
