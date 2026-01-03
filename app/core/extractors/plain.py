
import os
from .base import BaseExtractor

class PlainTextExtractor(BaseExtractor):
    def extract(self, path: str) -> str:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
