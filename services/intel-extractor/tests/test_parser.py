import pytest

try:
    from parser import extract_pdf_text, extract_url_text
    _IMPORT_OK = True
except ImportError:
    _IMPORT_OK = False


_skip = pytest.mark.skipif(not _IMPORT_OK, reason="parser not yet implemented")


@_skip
def test_extract_pdf_text():
    # RED: parser.py not yet implemented
    # When implemented: extract_pdf_text(pdf_bytes) returns non-empty string
    pdf_bytes = b"%PDF-1.4 1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj"
    result = extract_pdf_text(pdf_bytes)
    assert isinstance(result, str) and len(result) > 0
    pytest.fail("RED")


@_skip
def test_extract_url_text():
    # RED: parser.py not yet implemented
    # When implemented: extract_url_text(url) returns non-empty string
    result = extract_url_text("https://example.com")
    assert isinstance(result, str) and len(result) > 0
    pytest.fail("RED")


@_skip
def test_extract_url_text_trafilatura_fallback(monkeypatch):
    # RED: parser.py not yet implemented
    # When implemented: trafilatura.fetch_url returns None → fallback to requests+BS4
    import trafilatura
    monkeypatch.setattr(trafilatura, "fetch_url", lambda url: None)
    result = extract_url_text("https://example.com")
    assert isinstance(result, str) and len(result) > 0
    pytest.fail("RED")
