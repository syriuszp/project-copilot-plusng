from pypdf import PdfReader
from .base import BaseExtractor
from .models import ExtractResult

class PdfExtractor(BaseExtractor):
    def extract(self, path: str) -> ExtractResult:
        try:
            reader = PdfReader(path)
            text = []
            for i, page in enumerate(reader.pages):
                extracted = page.extract_text()
                if extracted and extracted.strip():
                    text.append(extracted)
                
                # Extended Extraction: Embedded Images
                # Check config
                features_cfg = self.config.get("features", {})
                extraction_cfg = features_cfg.get("extraction", {})
                if not extraction_cfg:
                     extraction_cfg = self.config.get("extraction", {})
                if extraction_cfg.get("images", False) and extraction_cfg.get("ocr", False):
                     try:
                         # Lazy import to avoid circular dependency issues if any, though Registry handles it
                         from app.core.extractors.image import ImageExtractor
                         img_extractor = ImageExtractor(self.config)
                         
                         for image_file_object in page.images:
                             # image_file_object.name, image_file_object.data
                             import tempfile
                             import os
                             
                             with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(image_file_object.name)[1]) as tmp:
                                 tmp.write(image_file_object.data)
                                 tmp_path = tmp.name
                             
                             try:
                                 res = img_extractor.extract(tmp_path)
                                 if res.content:
                                     text.append(f"\n[IMG-OCR (Page {i+1}): {res.content}]")
                             except Exception as e:
                                 # specific image fail shouldn't break whole PDF
                                 print(f"[WARN] PDF Image Extract Failed: {e}")
                                 pass 
                             finally:
                                 if os.path.exists(tmp_path):
                                     os.unlink(tmp_path)
                     except Exception as e:
                         pass # Warning?
                         print(f"[WARN] PDF Image Loop Failed: {e}")

            full_text = "\n".join(text)
            
            import datetime
            meta = {
                "source": "text",
                "chars": len(full_text),
                "extracted_at": datetime.datetime.now().isoformat()
            }

            if not full_text.strip():
                 # "no_text" status - implies valid file but empty content (e.g. scanned without OCR)
                 return ExtractResult(content=None, error=None, metadata={**meta, "status": "no_text"})
                 
            return ExtractResult(content=full_text, metadata=meta)
            
        except Exception as e:
            return ExtractResult(content=None, error=str(e), metadata={"source": "error"})
