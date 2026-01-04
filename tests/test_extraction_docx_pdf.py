
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from app.core.extractors.registry import ExtractorRegistry
from app.core.extractors.docx import DocxExtractor
from app.core.extractors.pdf import PdfExtractor

# Mocks for library dependencies to ensure tests run even if libs not installed in test env
# But ideally for "Strict Audit" we should verify they ARE installed?
# We'll use patches to simulate library behavior to test OUR logic.

@pytest.fixture
def mock_docx():
    with patch("app.core.extractors.docx.Document") as m:
        doc_mock = MagicMock()
        para_mock = MagicMock()
        para_mock.text = "Docx Content"
        doc_mock.paragraphs = [para_mock]
        m.return_value = doc_mock
        yield m

@pytest.fixture
def mock_pdf_reader():
    with patch("app.core.extractors.pdf.PdfReader") as m:
        pdf_mock = MagicMock()
        page_mock = MagicMock()
        page_mock.extract_text.return_value = "Pdf Page Content"
        pdf_mock.pages = [page_mock]
        m.return_value = pdf_mock
        yield m

def test_registry_defaults():
    # Verify strict MVP set (txt, docx, pdf, images)
    reg = ExtractorRegistry({"features": {"extraction": {"images": True}}})
    assert reg.get(".txt")
    assert reg.get(".docx")
    assert reg.get(".pdf")
    assert reg.get(".png")

def test_docx_extractor(tmp_path, mock_docx):
    # Verify Docx Logic
    f = tmp_path / "test.docx"
    f.write_text("fake binary")
    
    ext = DocxExtractor({})
    res = ext.extract(str(f))
    assert res == "Docx Content"

def test_pdf_extractor_text(tmp_path, mock_pdf_reader):
    # Verify PDF text mode
    f = tmp_path / "test.pdf"
    f.write_text("fake binary")
    
    ext = PdfExtractor({"features": {"extraction": {"ocr": False}}}) # Ensure no OCR fallback
    res = ext.extract(str(f))
    assert res == "Pdf Page Content"

def test_pdf_extractor_ocr_fallback(tmp_path, mock_pdf_reader):
    # Test fallback logic trigger (if pages empty)
    f = tmp_path / "scan.pdf"
    f.write_text("fake binary")
    
    # Mock empty pdf
    mock_pdf_reader.return_value.pages[0].extract_text.return_value = ""
    
    # Mock BinaryChecker saying Tesseract is Missing
    # We need to mock where BinaryChecker is used.
    # It's checked in Registry and passed to config.
    # Extractor reads config['binaries'].
    
    config = {
        "features": {"extraction": {"ocr": True}},
        "binaries": {"tesseract": False, "poppler": False}
    }
    
    ext = PdfExtractor(config)
    
    # Should return None (NOT_EXTRACTABLE) because OCR needed but binaries missing
    res = ext.extract(str(f))
    assert res is None

def test_image_extractor_no_ocr():
    from app.core.extractors.image import ImageExtractor
    config = {"features": {"extraction": {"ocr": False}}}
    ext = ImageExtractor(config)
    res = ext.extract("foo.png")
    assert res is None # NOT_EXTRACTABLE
