
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from app.core.external_tools import ExternalTools

def debug_ocr():
    print("--- OCR Debug ---")
    
    # 1. Inspect 'tools' dir
    tools_dir = Path("tools")
    if not tools_dir.exists():
        print(f"Directory 'tools' does NOT exist in {os.getcwd()}")
    else:
        print(f"Directory 'tools' found.")
        print("Contents:")
        for root, dirs, files in os.walk(tools_dir):
            for name in files:
                print(f" - {os.path.join(root, name)}")
    
    # 2. Test Detection
    bin_path = ExternalTools._find_binary("tesseract", "tesseract.exe")
    print(f"\nDetection Result: {bin_path}")
    
    if bin_path:
        print("SUCCESS: Tesseract binary detected.")
        
        # Check for tessdata
        tess_dir = Path(bin_path).parent / "tessdata"
        if tess_dir.exists():
            print(f"wbTessdata dir found: {tess_dir}")
            eng_data = tess_dir / "eng.traineddata"
            if eng_data.exists():
                 print(f" - eng.traineddata FOUND. OCR should work.")
            else:
                 print(f" - eng.traineddata NOT FOUND. OCR might fail.")
        else:
             print(f"WARN: tessdata dir NOT FOUND at {tess_dir}. OCR likely to fail.")
             # Check if it's in the root tools/tesseract?
             alt_tess = Path(bin_path).parent.parent / "tessdata" # unlikely if structure is standard
             if alt_tess.exists():
                 print(f" - Found tessdata in parent: {alt_tess}")
             
    else:
        print("FAILURE: Tesseract NOT detected.")
        print("Expected locations:")
        print(f" - Config Override (None)")
        print(f" - {tools_dir / 'tesseract' / 'tesseract.exe'}")
        print(f" - {tools_dir / 'tesseract.exe'}")
        print(f" - SYSTEM PATH")

if __name__ == "__main__":
    debug_ocr()
