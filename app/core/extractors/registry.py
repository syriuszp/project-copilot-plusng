
from typing import Dict, Optional, Type
from .base import BaseExtractor
from .plain import PlainTextExtractor
from .pdf import PdfExtractor
from .docx import DocxExtractor
from app.core.utils.binaries import BinaryChecker

class ExtractorRegistry:
    def __init__(self, config: Optional[dict] = None):
        self._extractors: Dict[str, BaseExtractor] = {}
        self.config = config or {}
        # Get extraction features or default
        # If partial dict, get defaults? 
        # ConfigValidator ensures types. 
        # Default flags: all enabled except OCR maybe? Or strict logic?
        # User requirement: "jeśli images=false, nie próbuj OCR".
        # Assume missing = True? Yes, MVP default enabled.
        # But OCR default false.
        
        self.features = self.config.get("extraction", {}) if "extraction" in self.config else self.config # Support testing direct feature dict
        
        # Binary Checks
        self.binaries = BinaryChecker.check_binaries(self.config)
        self.config["binaries"] = self.binaries # Propagate to extractors if needed
        
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
        
        # DOCX
        if self.features.get("docx", True):
            self.register(".docx", DocxExtractor(self.config))

        # PDF
        if self.features.get("pdf", True):
             self.register(".pdf", PdfExtractor(self.config))
        
        # Images
        if self.features.get("images", True):
            from .image import ImageExtractor
            img = ImageExtractor(self.config)
            for ext in [".png", ".jpg", ".jpeg"]:
                self.register(ext, img)
