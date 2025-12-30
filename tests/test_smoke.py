from pathlib import Path

def test_repo_layout_has_app_main():
    repo_root = Path(__file__).resolve().parents[1]
    assert (repo_root / "app" / "main.py").exists()
