
import os
import base64
import tempfile
import logging
from bs4 import BeautifulSoup
from pathlib import Path
from typing import Optional

from .base import BaseExtractor
from .models import ExtractResult
from .image import ImageExtractor

logger = logging.getLogger(__name__)

class HtmlExtractor(BaseExtractor):
    def extract(self, path: str) -> ExtractResult:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            
            return self._extract_from_string(content, base_path=os.path.dirname(path))
            
        except Exception as e:
            return ExtractResult(content=None, error=str(e), metadata={"source": "error"})

    def _extract_from_string(self, html_content: str, base_path: Optional[str] = None) -> ExtractResult:
        """
        Internal method to extract from string (useful for MHT or memory content).
        """
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            
            # Check for images if OCR enabled
            extraction_cfg = self.config.get("extraction", {})
            ocr_enabled = extraction_cfg.get("images", False) and extraction_cfg.get("ocr", False)
            
            if ocr_enabled:
                image_extractor = ImageExtractor(self.config)
                
                for img in soup.find_all('img'):
                    src = img.get('src')
                    if not src:
                        continue
                        
                    ocr_text = None
                    
                    # 1. Base64
                    if src.startswith('data:image'):
                        try:
                            # Parse base64
                            # data:image/png;base64,.....
                            header, encoded = src.split(',', 1)
                            data = base64.b64decode(encoded)
                            
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                                tmp.write(data)
                                tmp_path = tmp.name
                                
                            try:
                                res = image_extractor.extract(tmp_path)
                                if res.content:
                                    ocr_text = res.content
                            finally:
                                if os.path.exists(tmp_path):
                                    os.unlink(tmp_path)
                                    
                        except Exception as e:
                            logger.warning(f"Failed to process base64 image: {e}")

                    # 2. Local File (if base_path provided)
                    elif base_path and not src.startswith(('http://', 'https://')):
                        # Potential security risk: Path traversal.
                        # Simple check: join and check existence.
                        try:
                            # Normalize separators
                            local_img_path = os.path.join(base_path, src)
                            if os.path.exists(local_img_path):
                                res = image_extractor.extract(local_img_path)
                                if res.content:
                                    ocr_text = res.content
                        except Exception as e:
                            logger.warning(f"Failed to process local image {src}: {e}")
                            
                    # Replace IMG with text
                    if ocr_text:
                        new_node = soup.new_string(f" [IMG-OCR: {ocr_text}] ")
                        img.replace_with(new_node)
            
            # Extract plain text
            text = soup.get_text(separator="\n")
            return ExtractResult(content=text, metadata={"source": "html"})
            
        except Exception as e:
             return ExtractResult(content=None, error=str(e), metadata={"source": "error"})
