
import shutil
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


from dataclasses import dataclass

@dataclass
class ToolStatus:
    name: str
    status: str # AVAILABLE, MISSING, DISABLED
    path: Optional[str] = None
    required: bool = False
    details: Optional[str] = None

class ExternalTools:
    """
    Helper for detecting external binaries (Tesseract, Poppler).
    Logic:
    1. Check config override (e.g. features.extraction.ocr.tesseract_path)
    2. Check 'tools/' directory in project root.
    3. Check system PATH (shutil.which).
    """

    @staticmethod
    def check_binaries(config: Dict[str, Any] = None) -> Dict[str, ToolStatus]:
        config = config or {}
        features = config.get("features", {})
        extraction = features.get("extraction", {})
        
        # Tools Directory (Option A)
        paths = config.get("paths", {})
        tools_dir = paths.get("tools_dir", "tools")
        project_root = Path(__file__).resolve().parents[2]
        resolved_tools = (project_root / tools_dir).resolve()
        
        # Determine requirements
        ocr_enabled = extraction.get("ocr", {})
        if isinstance(ocr_enabled, bool): # Legacy/Bool support
             is_ocr_active = ocr_enabled
             ocr_overrides = {}
        else:
             is_ocr_active = ocr_enabled.get("enabled", False)
             ocr_overrides = ocr_enabled
        
        results = {}
        
        # 1. Tesseract
        tess_override = ocr_overrides.get("tesseract_path")
        tess_bin = ExternalTools._find_binary("tesseract", "tesseract.exe", resolved_tools, tess_override)
        
        results["tesseract"] = ToolStatus(
            name="tesseract",
            status="AVAILABLE" if tess_bin else "MISSING",
            path=tess_bin,
            required=is_ocr_active,
            details="Required for OCR" if is_ocr_active else "Optional"
        )
        
        # 2. Poppler (PDF Images)
        # Poppler config might be under extraction.pdf_advanced or ocr?
        # Let's check overrides. config/general.yaml has extraction.pdf_advanced
        pdf_adv = extraction.get("pdf_advanced", {})
        pop_override = pdf_adv.get("poppler_path")
        
        # Poppler usually needs 'pdftoppm'
        poppler_bin = ExternalTools._find_binary("poppler", "pdftoppm.exe", resolved_tools, pop_override)
        if not poppler_bin:
             # Try without .exe for linux?
             poppler_bin = ExternalTools._find_binary("poppler", "pdftoppm", resolved_tools, pop_override)

        results["poppler"] = ToolStatus(
            name="poppler",
            status="AVAILABLE" if poppler_bin else "MISSING",
            path=poppler_bin,
            required=is_ocr_active, # Currently tied to OCR enabled? Or image PDF support?
            details="Required for PDF-to-Image" if is_ocr_active else "Optional"
        )

        # 3. Antiword (.doc)
        # Check overrides in extraction.doc?
        doc_cfg = extraction.get("doc", {})
        antiword_override = doc_cfg.get("antiword_path")
        
        antiword_bin = ExternalTools._find_binary("antiword", "antiword.exe", resolved_tools, antiword_override)
        if not antiword_bin:
             antiword_bin = ExternalTools._find_binary("antiword", "antiword", resolved_tools, antiword_override)
             
        results["antiword"] = ToolStatus(
            name="antiword",
            status="AVAILABLE" if antiword_bin else "MISSING",
            path=antiword_bin,
            required=False,
            details="Required for .doc extraction"
        )
        for tool, status in results.items():
            if status.required and status.status == "MISSING":
                logger.error(f"REQUIRED tool missing: {tool}")
            elif status.status == "AVAILABLE":
                logger.info(f"Tool {tool}: AVAILABLE at {status.path}")
            
        return results

    @staticmethod
    def _find_binary(tool_name: str, target_name: str, tools_dir: Path, config_path: Optional[str] = None) -> Optional[str]:
        # 1. Config override
        if config_path:
             cp = Path(config_path)
             if cp.exists(): return str(cp)
             
        # 2. Tools Directory
        if tools_dir.exists():
             # Standard: tools/tool_name/target
             p1 = tools_dir / tool_name / target_name
             if p1.exists(): return str(p1)
             
             # Flat: tools/target
             p2 = tools_dir / target_name
             if p2.exists(): return str(p2)
             
             # Poppler style: tools/tool_name/bin/target
             p3 = tools_dir / tool_name / "bin" / target_name
             if p3.exists(): return str(p3)

             # Poppler style flat: tools/bin/target
             p4 = tools_dir / "bin" / target_name
             if p4.exists(): return str(p4)

        # 3. System PATH
        return shutil.which(target_name)
