import logging
from typing import Dict, Optional, Type
from .base import BaseExtractor
from .plain import PlainTextExtractor
from .pdf import PdfExtractor
from .docx import DocxExtractor
from app.core.external_tools import ExternalTools

logger = logging.getLogger(__name__)

class ExtractorRegistry:
    def __init__(self, config: Optional[dict] = None):
        self._extractors: Dict[str, BaseExtractor] = {}
        self.config = config or {}
        
        # Resolve 'extraction' features config (Audit P0)
        # Priority: config['features']['extraction'] -> config['extraction'] -> {}
        features_section = self.config.get("features", {})
        if "extraction" in features_section:
            self.features = features_section["extraction"]
        elif "extraction" in self.config:
             self.features = self.config["extraction"]
        else:
             self.features = {}
        
        # Binary Checks
        self.binaries = ExternalTools.check_binaries(self.config)
        self.config["binaries"] = self.binaries # Propagate to extractors if needed
        
        # Register defaults
        self.register_defaults()

    def register(self, ext: str, extractor: BaseExtractor):
        self._extractors[ext.lower()] = extractor

    def get(self, ext: str) -> Optional[BaseExtractor]:
        return self._extractors.get(ext.lower())

    def register_defaults(self):
        # 1. Plain Text (Always available)
        plain = PlainTextExtractor(self.config)
        for ext in [".txt", ".md", ".json", ".yaml", ".yml", ".py", ".log", ".sql", ".ini", ".conf"]:
            self.register(ext, plain)
        
        # 2. DOCX
        if self.features.get("docx", True):
            try:
                from .docx import DocxExtractor
                self.register(".docx", DocxExtractor(self.config))
            except ImportError as e:
                logger.warning(f"Could not import DocxExtractor: {e}")

        # 3. PDF
        if self.features.get("pdf", True):
            try:
                from .pdf import PdfExtractor
                self.register(".pdf", PdfExtractor(self.config))
            except ImportError as e:
                 logger.warning(f"Could not import PdfExtractor: {e}")
        
        # 4. Images
        # User Requirement: images -> ImageExtractor (OCR conditional inside)
        if self.features.get("images", True):
            try:
                from .image import ImageExtractor
                img = ImageExtractor(self.config)
                for ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"]:
                    self.register(ext, img)
            except ImportError as e:
                 logger.warning(f"Could not import ImageExtractor: {e}")

        # 5. HTML / MHT
        try:
            from .html import HtmlExtractor
            html = HtmlExtractor(self.config)
            for ext in [".html", ".htm"]:
                self.register(ext, html)
        except ImportError as e:
            logger.warning(f"Could not import HtmlExtractor: {e}")
            
        try:
            from .mht import MhtExtractor
            mht = MhtExtractor(self.config)
            for ext in [".mht", ".mhtml"]:
                self.register(ext, mht)
        except ImportError as e:
             logger.warning(f"Could not import MhtExtractor: {e}")
            
        # 6. CSV
        try:
            from .csv_ext import CsvExtractor
            csv_ext = CsvExtractor(self.config)
            self.register(".csv", csv_ext)
        except ImportError as e:
             logger.warning(f"Could not import CsvExtractor: {e}")

        # 7. DOC (Antiword)
        # P1-lite (Auditor R3)
        try:
            from .doc import DocExtractor
            self.register(".doc", DocExtractor(self.config))
        except ImportError as e:
            logger.warning(f"Could not import DocExtractor: {e}")
