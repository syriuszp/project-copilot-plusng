from docx import Document
from .base import BaseExtractor
from .models import ExtractResult

class DocxExtractor(BaseExtractor):
    def extract(self, path: str) -> ExtractResult:
        try:
            doc = Document(path)
            text = []
            
            # 1. Paragraphs
            for para in doc.paragraphs:
                text.append(para.text)
                
            # 2. Tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = [cell.text for cell in row.cells]
                    text.append(" | ".join(row_text))
            
            # 3. Embedded Images (OCR)
            # Check config
            extraction_cfg = self.config.get("extraction", {})
            if extraction_cfg.get("images", False) and extraction_cfg.get("ocr", False):
                 try:
                     from app.core.extractors.image import ImageExtractor
                     img_extractor = ImageExtractor(self.config)
                     import tempfile
                     import os
                     
                     # Iterate relationships
                     for rel in doc.part.rels.values():
                         if "image" in rel.target_ref.lower() or (hasattr(rel.target_part, "content_type") and rel.target_part.content_type.startswith("image/")):
                             try:
                                 image_data = rel.target_part.blob
                                 # Guess extension
                                 ext = ".png"
                                 if hasattr(rel.target_part, "content_type"):
                                     if "jpeg" in rel.target_part.content_type: ext = ".jpg"
                                     elif "png" in rel.target_part.content_type: ext = ".png"
                                 
                                 with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                                     tmp.write(image_data)
                                     tmp_path = tmp.name
                                     
                                 try:
                                     res = img_extractor.extract(tmp_path)
                                     if res.content:
                                          text.append(f"\n[IMG-OCR: {res.content}]")
                                 finally:
                                      if os.path.exists(tmp_path):
                                          os.unlink(tmp_path)
                             except Exception as e:
                                 pass 
                 except Exception as e:
                     pass

            return ExtractResult(content="\n".join(text), metadata={"source": "text"})
        except Exception as e:
            return ExtractResult(content=None, error=str(e), metadata={"source": "error"})
