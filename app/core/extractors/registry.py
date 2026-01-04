
from typing import Dict, Optional, Type
from .base import BaseExtractor
from .plain import PlainTextExtractor
from .pdf import PdfExtractor
from .docx import DocxExtractor

class ExtractorRegistry:
    def __init__(self, config: Optional[dict] = None):
        self._extractors: Dict[str, BaseExtractor] = {}
        self.config = config or {}
        # Register defaults
        self.register_defaults()

    def register(self, ext: str, extractor: BaseExtractor):
        self._extractors[ext.lower()] = extractor

    def get(self, ext: str) -> Optional[BaseExtractor]:
        return self._extractors.get(ext.lower())

    def register_defaults(self):
        plain = PlainTextExtractor(self.config)
        for ext in [".txt", ".md", ".json", ".yaml", ".yml", ".py", ".log"]:
            self.register(ext, plain)
        
        self.register(".pdf", PdfExtractor(self.config))
        self.register(".docx", DocxExtractor(self.config))
        
        from .image import ImageExtractor
        img = ImageExtractor(self.config)
        for ext in [".png", ".jpg", ".jpeg"]:
            self.register(ext, img)
