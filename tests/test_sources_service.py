
import pytest
import os
from pathlib import Path
from app.services import sources_service
from app.models.artifacts import Artifact

@pytest.fixture
def mock_ingest_dir(tmp_path):
    # Create some dummy files
    (tmp_path / "doc.txt").write_text("Hello World " * 100) # Text
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n") # Fake png
    (tmp_path / "calc.py").write_text("print(1+1)") # Code
    (tmp_path / "data.json").write_text('{"key": "value"}') # Json
    (tmp_path / "notes.md").write_text("# Notes") # Markdown
    (tmp_path / "manual.pdf").write_bytes(b"%PDF-1.4") # PDF
    
    return str(tmp_path)

def test_list_artifacts_all(mock_ingest_dir):
    artifacts = sources_service.list_artifacts(mock_ingest_dir)
    assert len(artifacts) == 6
    # Check Model
    assert isinstance(artifacts[0], Artifact)

def test_list_artifacts_filter_ext(mock_ingest_dir):
    txts = sources_service.list_artifacts(mock_ingest_dir, filter_ext=".txt")
    assert len(txts) == 1
    assert txts[0].name == "doc.txt"

def test_list_artifacts_search(mock_ingest_dir):
    res = sources_service.list_artifacts(mock_ingest_dir, search_term="manual")
    assert len(res) == 1
    assert res[0].name == "manual.pdf"

def test_get_artifact_details(mock_ingest_dir):
    path = os.path.join(mock_ingest_dir, "doc.txt")
    details = sources_service.get_artifact_details(path, compute_hash=True)
    
    assert details.name == "doc.txt"
    assert details.size > 0
    assert details.hash is not None # Check hash calculation

def test_preview_text(mock_ingest_dir):
    path = os.path.join(mock_ingest_dir, "doc.txt")
    res = sources_service.preview_artifact(path)
    
    assert res.type == "text"
    assert "Hello World" in res.content

def test_preview_image(mock_ingest_dir):
    path = os.path.join(mock_ingest_dir, "image.png")
    res = sources_service.preview_artifact(path)
    assert res.type == "image"
    assert res.content == path

def test_preview_pdf_placeholder(mock_ingest_dir):
    path = os.path.join(mock_ingest_dir, "manual.pdf")
    res = sources_service.preview_artifact(path)
    assert res.type == "pdf_placeholder"

def test_preview_missing_file():
    res = sources_service.preview_artifact("non_existent_file.txt")
    assert res.type == "error"
