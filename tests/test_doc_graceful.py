
import pytest
from app.core.extractors.doc import DocExtractor
from app.core.extractors.registry import ExtractorRegistry

def test_doc_extractor_missing_binary():
    """
    Verifies that DocExtractor returns NOT_EXTRACTABLE if binary is missing.
    Assumes binary is NOT in the environment (or mocking it out).
    """
    # Initialize with empty config (no paths.tools_dir override, so defaults to local/missing)
    ext = DocExtractor(config={})
    
    # We can rely on system state (likely missing antiword on this dev environment)
    # Or force it via config override to a non-existent path
    ext.config = {"paths": {"tools_dir": "non_existent_tools"}}
    
    # Extract
    res = ext.extract("dummy.doc")
    
    # Verify
    assert res.content is None
    assert res.metadata.get("status") == "not_extractable"
    assert "Antiword binary not found" in res.error

def test_registry_has_doc():
    reg = ExtractorRegistry(config={"features": {"extraction": {"doc": {"antiword_path": "foo"}}}})
    extractor = reg.get(".doc")
    assert isinstance(extractor, DocExtractor)
