import os
import re
import pytest
from pathlib import Path

# Patterns that look like API keys (simple heuristics)
# Google/Gemini keys often start with AIza
API_KEY_PATTERNS = [
    r"AIza[0-9A-Za-z-_]{35}",
    r"sk-[a-zA-Z0-9]{32,}",
]

REPO_ROOT = Path(__file__).parent.parent

def is_git_ignored(path, root):
    # This is a naive check. Ideally we'd use 'git check-ignore' but running subprocess matches dev env better.
    # For this test, we check if file exists. If it exists, it MUST be ignored.
    # But this test is "no secrets committed", so we check if they exist in the repo file list (handled by not having them checked out).
    # Since we are running in a local env where they MIGHT exist as files (but not committed), 
    # we primarily want to check if any *committed* file contains secrets.
    # Or, simpler: ensure forbidden filenames are NOT present in the list of files to be committed (if we could check staging).
    # Since we can't easily check git staging from here without subprocess, 
    # we will verify that the .gitignore contains the required entries.
    pass

def test_gitignore_has_security_entries():
    """Ensure .gitignore explicitly excludes secret patterns."""
    gitignore_path = REPO_ROOT / ".gitignore"
    assert gitignore_path.exists()
    
    content = gitignore_path.read_text(encoding="utf-8")
    required_patterns = [
        "config/secrets.local.json",
        "*.local.json",
        ".env"
    ]
    for pattern in required_patterns:
        assert pattern in content, f".gitignore missing required pattern: {pattern}"

def test_no_api_keys_in_codebase():
    """Scan all text files in the repo for strings looking like API keys."""
    # Extensions to scan
    extensions = {".py", ".md", ".json", ".yaml", ".yml", ".txt", ".sql"}
    
    # Exclude these dirs
    exclude_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules", "prod", "data", "logs"}
    
    found_secrets = []

    for root, dirs, files in os.walk(REPO_ROOT):
        # Filter directories inplace
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            file_path = Path(root) / file
            
            # Skip if strict match to secrets file
            if file_path.name == "secrets.local.json": 
                 continue # Should be ignored by git, but might exist locally. We don't scan it.

            if file_path.suffix in extensions:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    for pattern in API_KEY_PATTERNS:
                        matches = re.finditer(pattern, content)
                        for match in matches:
                            # Context
                            start = max(0, match.start() - 10)
                            end = min(len(content), match.end() + 10)
                            snippet = content[start:end]
                            
                            # Whitelist checks (dummy example keys in docs/tests)
                            if "example" in snippet.lower() or "dummy" in snippet.lower() or "placehold" in snippet.lower():
                                continue
                                
                            found_secrets.append(f"Possible key in {file_path.name}: ...{match.group()}...")
                except Exception:
                    # Binary file or access issue
                    pass

    assert not found_secrets, f"Found potential API keys in codebase: {found_secrets}"
