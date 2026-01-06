
import subprocess
import logging
from typing import Optional

from app.core.extractors.base import BaseExtractor
from app.core.extractors.models import ExtractResult
from app.core.external_tools import ExternalTools

logger = logging.getLogger(__name__)

class DocExtractor(BaseExtractor):
    """
    Extracts text from legacy MS Word (.doc) files using 'antiword'.
    Requirement: antiword executable must be available (Option A: checked in repo).
    """

    def extract(self, path: str) -> ExtractResult:
        # Check binary availability
        tool_status = ExternalTools.check_binaries(self.config).get("antiword")
        
        if not tool_status or tool_status.status != "AVAILABLE":
             return ExtractResult(
                 content=None, 
                 metadata={"source": "antiword_missing", "status": "not_extractable"},
                 error="Antiword binary not found. See docs/extraction.md."
             )

        antiword_bin = tool_status.path
        
        try:
            # Run antiword
            # -m UTF-8.txt maps to UTF-8 output usually, or just use -m UTF-8
            # antiword <file>
            # We want UTF-8 output.
            # antiword -m UTF-8 <file> might be needed if mapping is supported.
            # Or just rely on stdout decoding.
            # Default antiword outputs text.
            
            cmd = [antiword_bin, "-m", "UTF-8.txt", path]
            # If mapping file not found, it might warn. 
            # Safe default: just [antiword_bin, path] and hope for best?
            # User requirement: "próbuje odpalić tools/bin/antiword/antiword.exe <file.doc>"
            # But "antiword -m UTF-8.txt" is good practice if mapping exists.
            # Let's try standard invocation or check if mapping file is needed relative to CWD.
            # For portable usage, antiword needs mapping files in %HOME%/.antiword usually or explicit path via env?
            # Setting ANTIWORDHOME env var might be needed if using mapping files.
            # For MVP/P1-lite, let's try generic run. If encoding issues, user can supply mapping.
            # Command: antiword -w 0 <path> (width 0 for no wrapping)
            
            # Since we didn't setup ANTIWORDHOME, maybe just run without -m?
            # Or try passing env?
            # Let's assume the user provides a self-contained antiword setup or we just run it raw.
            # "antiword -w 0" is good for extraction.
            
            cmd = [antiword_bin, "-w", "0", path]
            
            env = dict(logging.os.environ) # Copy env?
            # If antiword directory has mapping files, maybe set ANTIWORDHOME?
            # Assuming bin is in tools/antiword/antiword.exe
            # ANTIWORDHOME could be tools/antiword
            bin_path = logging.os.path.dirname(antiword_bin)
            env["ANTIWORDHOME"] = bin_path 

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                env=env,
                encoding='utf-8', 
                errors='replace' # Handle encoding weirdness
            )
            
            text = process.stdout.strip()
            
            if not text:
                # Could be empty doc or extraction failed silently
                return ExtractResult(content="", metadata={"source": "antiword"})

            return ExtractResult(content=text, metadata={"source": "antiword"})

        except subprocess.CalledProcessError as e:
            err = e.stderr or str(e)
            logger.warning(f"Antiword failed for {path}: {err}")
            return ExtractResult(content=None, error=f"Antiword error: {err}", metadata={"source": "error"})
            
        except Exception as e:
            logger.error(f"DocExtraction exception: {e}")
            return ExtractResult(content=None, error=str(e), metadata={"source": "exception"})
