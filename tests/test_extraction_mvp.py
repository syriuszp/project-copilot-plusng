
import pytest
from unittest.mock import MagicMock, patch
from app.core.extractors.registry import ExtractorRegistry
from app.core.extractors.pdf import PdfExtractor
from app.core.extractors.docx import DocxExtractor
from app.core.extractors.image import ImageExtractor

def test_registry_defaults():
    registry = ExtractorRegistry()
    assert isinstance(registry.get(".pdf"), PdfExtractor)
    assert isinstance(registry.get(".docx"), DocxExtractor)
    assert isinstance(registry.get(".png"), ImageExtractor)
    assert isinstance(registry.get(".jpg"), ImageExtractor)

def test_image_extraction_flags():
    # 1. Images Disabled
    cfg_disabled = {"extraction": {"images": False, "ocr": True}}
    reg = ExtractorRegistry(cfg_disabled)
    extractor = reg.get(".png")
    assert extractor.extract("foo.png") is None

    # 2. Images Enabled, OCR Disabled
    cfg_no_ocr = {"extraction": {"images": True, "ocr": False}}
    reg = ExtractorRegistry(cfg_no_ocr)
    extractor = reg.get(".png")
    assert extractor.extract("foo.png") is None

    # 3. Images Enabled, OCR Enabled
    cfg_full = {"extraction": {"images": True, "ocr": True}}
    reg = ExtractorRegistry(cfg_full)
    extractor = reg.get(".png")
    res = extractor.extract("foo.png")
    assert "[OCR Content Placeholder" in res

@patch("app.core.extractors.pdf.PdfReader")
def test_pdf_ocr_fallback(mock_reader_cls):
    # Mock Empty PDF
    mock_reader = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "" # Empty
    mock_reader.pages = [mock_page]
    mock_reader_cls.return_value = mock_reader

    # 1. OCR Disabled -> None
    cfg_no_ocr = {"extraction": {"ocr": False}}
    extractor = PdfExtractor(cfg_no_ocr)
    assert extractor.extract("dummy.pdf") is None

    # 2. OCR Enabled -> Placeholder
    cfg_ocr = {"extraction": {"ocr": True}}
    extractor = PdfExtractor(cfg_ocr)
    res = extractor.extract("dummy.pdf")
    assert "[OCR Content Placeholder" in res

@patch("app.core.extractors.pdf.PdfReader")
def test_pdf_normal_text(mock_reader_cls):
    # Mock Normal PDF
    mock_reader = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Real Text"
    mock_reader.pages = [mock_page]
    mock_reader_cls.return_value = mock_reader

    extractor = PdfExtractor({})
    res = extractor.extract("dummy.pdf")
    assert res == "Real Text"

