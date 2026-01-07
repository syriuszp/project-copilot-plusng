
import os
import sys
import logging

# Ensure we can import from installed package or local
# If installed via pip, 'app' should be importable.

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("debug_ocr")

try:
    from app.core.extractors.image import ImageExtractor
    from app.ui.config_loader import load_config
except ImportError:
    # Fallback if running from repo root without pip install
    sys.path.append(os.getcwd())
    from app.core.extractors.image import ImageExtractor
    from app.ui.config_loader import load_config

def main():
    print("=== DEBUG PROD OCR ===")
    
    # 1. Load Config
    try:
        loaded = load_config()
        if loaded.get("status") != "OK":
             print(f"Config Error: {loaded.get('error')}")
             return
             
        config = loaded["data"]
        print(f"Config Loaded. Env: {os.environ.get('PROJECT_COPILOT_ENV')}")
        feat = config.get("features", {}).get("extraction", {})
        print(f"Extraction Config: {feat}")
        root_feat = config.get("extraction", {})
        print(f"Root Extraction Config (Fallback): {root_feat}")
    except Exception as e:
        print(f"Config Load Failed: {e}")
        return

    # 2. Init Extractor
    try:
        extractor = ImageExtractor(config)
        print(f"ImageExtractor initialized.")
    except Exception as e:
        print(f"ImageExtractor Init Failed: {e}")
        return

    # 3. Find target file
    # Try to find 7777.png in known paths
    candidates = [
        r"C:\Users\ROBBYRA\OneDrive - Mercedes-Benz (corpdir.onmicrosoft.com)\AI\Projects\ProjectCopilot\prod\data\ingest\7777.png",
        "data/ingest/7777.png",
        "7777.png"
    ]
    
    target = None
    for c in candidates:
        if os.path.exists(c):
            target = c
            break
            
    if not target:
        print("Could not find 7777.png. Please place it in data/ingest or current dir.")
        print(f"Checked: {candidates}")
        # List dir to help
        print("Listing current dir:")
        print(os.listdir("."))
        return

    print(f"Target File: {target}")
    
    # 4. Extract
    print("\n--- Running Extraction ---")
    try:
        res = extractor.extract(target)
        print("\n--- Extraction Result ---")
        print(f"Content Length: {len(res.content) if res.content else 0}")
        print(f"Content Preview: {res.content[:100] if res.content else 'None'}")
        print(f"Error: {res.error}")
        print(f"Metadata: {res.metadata}")
        
    except Exception as e:
        print(f"Extraction Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
