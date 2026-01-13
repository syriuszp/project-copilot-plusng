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

            # 3. Visual Page OCR (Hybrid Strategy)
            # Use pdftoppm to render page and OCR it if vector text is present but not extractable
            if extraction_cfg.get("ocr", False):
                 from app.core.external_tools import ExternalTools
                 tool_status = ExternalTools.check_binaries(self.config)
                 poppler_bin = tool_status.get("poppler", {}).path
                 
                 if poppler_bin:
                     try:
                         import subprocess
                         import tempfile
                         import os
                         
                         # Render page to PNG
                         # pdftoppm -png -f {page_index+1} -l {page_index+1} -r 200 {pdf_path} {prefix}
                         # Output will be {prefix}-1.png (because -f/-l 1-based)
                         
                         with tempfile.TemporaryDirectory() as tmp_dir:
                             out_prefix = os.path.join(tmp_dir, f"page_{i}")
                             # pdftoppm args: -png (format), -f (first page), -l (last page), -r (resolution)
                             cmd = [
                                 poppler_bin,
                                 "-png",
                                 "-f", str(i+1),
                                 "-l", str(i+1),
                                 "-r", "200", # 200 DPI is loop compromise between speed/quality
                                 path,
                                 out_prefix
                             ]
                             
                             subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                             
                             # Find generated file (usually out_prefix-1.png or similar, pdftoppm appends suffix)
                             # Since we isolated in tmp_dir, just grab the png
                             png_file = None
                             for f in os.listdir(tmp_dir):
                                 if f.endswith(".png"):
                                     png_file = os.path.join(tmp_dir, f)
                                     break
                                     
                             if png_file:
                                 try:
                                     # Reuse ImageExtractor
                                     if 'img_extractor' not in locals():
                                          from app.core.extractors.image import ImageExtractor
                                          img_extractor = ImageExtractor(self.config)
                                          
                                     res = img_extractor.extract(png_file)
                                     if res.content:
                                         # Deduplication heuristic:
                                         # If the Visual OCR text is mostly contained in already extracted text, skip it.
                                         # This avoids doubling the text size for normal PDFs.
                                         
                                         # Normalize simple (remove whitespace)
                                         existing_content = (extracted or "") + "".join(text[-5:]) # Look at recent context
                                         clean_visual = res.content.replace(" ", "").replace("\n", "")
                                         clean_existing = existing_content.replace(" ", "").replace("\n", "")
                                         
                                         # If > 80% of visual text is already in existing, assume duplicate
                                         # (Very rough, but prevents massive bloat)
                                         # But for 'Display.pdf', 'Password' is NOT in existing.
                                         
                                         # Simpler intelligence: Check length ratio. 
                                         # If standard text > 1000 chars and visual text < 1200 chars, likely duplicate.
                                         # But let's just append with a marker. Search is robust to duplicates.
                                         
                                         text.append(f"\n[VISUAL-OCR (Page {i+1}): {res.content}]")
                                 except Exception as e:
                                     print(f"[WARN] PDF Visual OCR Error: {e}")
                     except Exception as e:
                         # e.g. subprocess fail
                         print(f"[WARN] PDF Visual Render Error: {e}")
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
