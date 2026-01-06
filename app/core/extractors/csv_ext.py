
import csv
import io
import logging
from .base import BaseExtractor
from .models import ExtractResult

logger = logging.getLogger(__name__)

class CsvExtractor(BaseExtractor):
    def extract(self, path: str) -> ExtractResult:
        try:
            # 1. Read content trying common encodings
            content = None
            encoding_used = "utf-8"
            for enc in ["utf-8", "utf-8-sig", "cp1252", "cp1250", "latin-1"]:
                try:
                    with open(path, "r", encoding=enc) as f:
                        content = f.read()
                    encoding_used = enc
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                 return ExtractResult(content=None, error="Failed to decode CSV with supported encodings", metadata={"source": "error"})

            # 2. Sniff format
            try:
                sniffer = csv.Sniffer()
                # Sample first 4KB to sniff dialect
                dialect = sniffer.sniff(content[:4096])
            except csv.Error:
                # Fallback: assume comma
                dialect = csv.excel
                
            # 3. Parse
            f = io.StringIO(content)
            reader = csv.reader(f, dialect=dialect)
            
            lines = []
            for row in reader:
                # Filter empty values and join with space or pipe
                cleaned_row = [str(cell).strip() for cell in row if cell]
                if cleaned_row:
                    lines.append(" | ".join(cleaned_row))
            
            extracted_text = "\n".join(lines)
            
            return ExtractResult(
                content=extracted_text, 
                metadata={
                    "source": "csv",
                    "encoding": encoding_used, 
                    "rows": len(lines),
                    "dialect_delimiter": getattr(dialect, 'delimiter', ',')
                }
            )

        except Exception as e:
            return ExtractResult(content=None, error=str(e), metadata={"source": "error"})
