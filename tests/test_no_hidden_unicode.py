
import pytest
import os

# Bidi/Hidden characters to check for
BIDI_CHARS = set([
    '\u202A', '\u202B', '\u202C', '\u202D', '\u202E', # LRE, RLE, PDF, LRO, RLO
    '\u2066', '\u2067', '\u2068', '\u2069',           # LRI, RLI, FSI, PDI
    '\u200E', '\u200F'                                # LRM, RLM
])

def test_no_hidden_unicode():
    """
    Scans python files in the repo for hidden/bidi unicode characters.
    """
    # Simple scan of app/ and tests/
    root_dirs = ["app", "tests"]
    
    found_issues = []
    
    for root_dir in root_dirs:
        if not os.path.exists(root_dir):
            continue
            
        for root, _, files in os.walk(root_dir):
            for file in files:
                if file.endswith(".py"):
                    path = os.path.join(root, file)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            content = f.read()
                            for idx, char in enumerate(content):
                                if char in BIDI_CHARS:
                                    found_issues.append(f"{path}: char U+{ord(char):04X} at pos {idx}")
                    except Exception as e:
                        # Fail if we can't read a python file as utf-8?
                        # Or just ignore binary/other errors
                        pass

    assert not found_issues, f"Found hidden/bidi unicode characters:\n{chr(10).join(found_issues)}"
