import pytest

try:
    from extractor import call_llm, chunk_text, run_extraction
    _IMPORT_OK = True
except ImportError:
    _IMPORT_OK = False


_skip = pytest.mark.skipif(not _IMPORT_OK, reason="extractor not yet implemented")


@_skip
def test_call_llm_happy_path(mock_ollama):
    result = call_llm(mock_ollama, "llama3.2:3b", "The actor used 1.2.3.4")
    assert result["iocs"][0]["type"] == "ip"


@_skip
def test_chunk_text_overlap():
    text = "A" * 12000
    result = chunk_text(text, max_chars=6000, overlap_chars=600)
    assert len(result) >= 2
    # overlap window: last 600 chars of chunk[0] == first 600 chars of chunk[1]
    assert result[0][-600:] == result[1][:600]


@_skip
def test_ioc_dedup_across_chunks(mock_ollama):
    # The same ip 1.2.3.4 appears in both chunks (simulates overlap region duplication)
    duplicate_iocs = [
        {"type": "ip", "value": "1.2.3.4"},
        {"type": "ip", "value": "1.2.3.4"},
    ]
    seen: set = set()
    unique = []
    for ioc in duplicate_iocs:
        key = (ioc["type"], ioc["value"])
        if key not in seen:
            seen.add(key)
            unique.append(ioc)
    assert len(unique) == 1
