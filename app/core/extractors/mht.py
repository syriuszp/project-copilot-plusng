
import email
import base64
import logging
import os
from .base import BaseExtractor
from .models import ExtractResult
from .html import HtmlExtractor

logger = logging.getLogger(__name__)

class MhtExtractor(BaseExtractor):
    def extract(self, path: str) -> ExtractResult:
        try:
            # 1. Read Raw Bytes & Decode Whole File
            with open(path, "rb") as f:
                raw_data = f.read()
            
            # Detect Encoding (BOM or Fallback)
            encoding = "utf-8" # Default
            encoding_source = "default"
            
            # 1. BOM Check
            if raw_data.startswith(b'\xff\xfe'): 
                encoding = "utf-16-le"
                encoding_source = "bom_le"
            elif raw_data.startswith(b'\xfe\xff'): 
                encoding = "utf-16-be"
                encoding_source = "bom_be"
            elif raw_data.startswith(b'\xef\xbb\xbf'): 
                encoding = "utf-8-sig"
                encoding_source = "bom_utf8"
            
            # 2. Heuristic Check (Null bytes pattern for UTF-16LE: "h\x00e\x00l\x00l\x00o\x00")
            elif encoding_source == "default":
                # Check first 100 bytes for alternating nulls
                sample = raw_data[:100]
                if len(sample) > 10:
                    nulls_even = sum(1 for i in range(0, len(sample), 2) if sample[i] == 0)
                    nulls_odd = sum(1 for i in range(1, len(sample), 2) if sample[i] == 0)
                    
                    if nulls_odd > len(sample) * 0.4: # Lots of nulls at odd positions -> LE
                        encoding = "utf-16-le"
                        encoding_source = "heuristic_le"
                    elif nulls_even > len(sample) * 0.4: # Lots of nulls at even positions -> BE
                        encoding = "utf-16-be"
                        encoding_source = "heuristic_be"
            
            print(f"[MhtExtractor] {os.path.basename(path)} detected as {encoding} ({encoding_source})")

            # Try to decode
            decoded_content = None
            try:
                decoded_content = raw_data.decode(encoding)
            except Exception as e:
                print(f"[MhtExtractor] Decode failed for {encoding}: {e}")
                # Fallback strategies
                for enc in ["cp1252", "cp1250", "latin-1"]:
                     try:
                         decoded_content = raw_data.decode(enc)
                         break
                     except: pass
            
            if not decoded_content:
                 decoded_content = raw_data.decode("utf-8", errors="replace")
            
            # 2. Parse as Email/MIME
            msg = email.message_from_string(decoded_content)
            
            # Check if valid multipart
            if msg.is_multipart():
                html_content = None
                cid_map = {}
                
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_id = part.get("Content-ID")
                    if content_id: content_id = content_id.strip("<>")

                    if content_type == "text/html" and not html_content:
                        try:
                            # Payload is bytes
                            payload = part.get_payload(decode=True)
                            if payload:
                                # Detect Encoding of the PART
                                part_encoding = part.get_content_charset()
                                part_source = "header"
                                
                                # BOM Check on Part
                                if payload.startswith(b'\xff\xfe'): 
                                    part_encoding = "utf-16-le"
                                    part_source = "bom_le"
                                elif payload.startswith(b'\xfe\xff'): 
                                    part_encoding = "utf-16-be"
                                    part_source = "bom_be"
                                elif payload.startswith(b'\xef\xbb\xbf'): 
                                    part_encoding = "utf-8-sig"
                                    part_source = "bom_utf8"
                                
                                # Heuristic on Part (if header is missing or vague, or if we want to be aggressive)
                                # Word often says "text/html" without charset, or implies cp1252 but sends utf-16
                                if not part_encoding or part_encoding == "utf-8" or part_source == "header": 
                                    # Double check for UTF-16 nulls
                                    sample = payload[:100]
                                    if len(sample) > 10:
                                        nulls_even = sum(1 for i in range(0, len(sample), 2) if sample[i] == 0)
                                        nulls_odd = sum(1 for i in range(1, len(sample), 2) if sample[i] == 0)
                                        
                                        if nulls_odd > len(sample) * 0.4:
                                            part_encoding = "utf-16-le"
                                            part_source = "heuristic_le"
                                        elif nulls_even > len(sample) * 0.4:
                                            part_encoding = "utf-16-be"
                                            part_source = "heuristic_be"

                                part_encoding = part_encoding or "utf-8"
                                print(f"[MhtExtractor] Part {content_id} detected as {part_encoding} ({part_source})")

                                try:
                                    html_content = payload.decode(part_encoding)
                                except:
                                    # Retry fallback list
                                    success = False
                                    for enc in ["utf-16", "cp1252", "cp1250", "latin-1"]:
                                        try:
                                            html_content = payload.decode(enc)
                                            success = True
                                            break
                                        except: pass
                                    
                                    if not success:
                                        html_content = payload.decode("utf-8", errors="replace")
                                        
                            else:
                                html_content = part.get_payload() # String case (rare if multipart)
                        except Exception as e:
                            logger.warning(f"Failed to decode HTML part: {e}")
                    
                    elif content_type.startswith("image/"):
                        try:
                            data = part.get_payload(decode=True)
                            if content_id and data:
                                b64_str = base64.b64encode(data).decode("ascii")
                                cid_map[f"cid:{content_id}"] = f"data:{content_type};base64,{b64_str}"
                        except: pass

                if not html_content:
                     # Maybe root is html?
                     if msg.get_content_type() == "text/html":
                         html_content = str(msg.get_payload())
                
                # Replace CIDs
                if html_content and cid_map:
                    for cid, data_uri in cid_map.items():
                        html_content = html_content.replace(cid, data_uri)
                
                if not html_content:
                     # Fallback: maybe the whole file was just HTML but parsed as multipart?
                     # Check decoded_content
                     if "<html" in decoded_content.lower():
                         html_content = decoded_content
            
            else:
                # Not multipart -> Likely just an HTML file
                html_content = decoded_content

            if not html_content:
                 return ExtractResult(content=None, error="No HTML content found", metadata={"source": "mht_empty"})

            # 3. Delegate to HtmlExtractor
            html_extractor = HtmlExtractor(self.config)
            result = html_extractor._extract_from_string(html_content, base_path=None)
            
            if result.metadata:
                result.metadata["source"] = "mht"
                result.metadata["encoding_detected"] = encoding
                result.metadata["encoding_source"] = encoding_source
                
            return result

        except Exception as e:
            return ExtractResult(content=None, error=str(e), metadata={"source": "error"})
