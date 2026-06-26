import pytest

try:
    from searcher import search
    _IMPORT_OK = True
except ImportError:
    _IMPORT_OK = False

_skip = pytest.mark.skipif(not _IMPORT_OK, reason="searcher not yet implemented")


@_skip
def test_score_conversion(mock_chroma, mock_ollama, monkeypatch):
    # RESEARCH Pitfall 1: score = 1 - distance (HIGH IMPACT)
    # mock_chroma distances: [0.2, 0.8] → scores [0.8, 0.2]
    # threshold=0.3: score 0.8 passes, score 0.2 filtered out → 1 result
    import searcher
    monkeypatch.setattr(searcher, "_ollama", mock_ollama)
    results = search(mock_chroma, "Russian malware", threshold=0.3)
    assert len(results) == 1
    assert results[0]["score"] == 0.8
    assert results[0]["ioc_type"] == "IPv4-Addr"  # AISEM-03


@_skip
def test_threshold_filters(mock_chroma, mock_ollama, monkeypatch):
    # D-07: threshold=0.9 filters all results (scores 0.8 and 0.2 both below)
    import searcher
    monkeypatch.setattr(searcher, "_ollama", mock_ollama)
    results = search(mock_chroma, "Russian malware", threshold=0.9)
    assert len(results) == 0


@_skip
def test_search_returns_ranked(mock_chroma, mock_ollama, monkeypatch):
    # AISEM-02: results ordered by score descending (higher similarity first)
    import searcher
    monkeypatch.setattr(searcher, "_ollama", mock_ollama)
    results = search(mock_chroma, "Russian malware", threshold=0.1)
    assert len(results) == 2
    assert results[0]["score"] > results[1]["score"]


@_skip
def test_opencti_url_format(mock_chroma, mock_ollama, monkeypatch):
    # D-08: opencti_url and embedded_text must be present in results
    import searcher
    monkeypatch.setattr(searcher, "_ollama", mock_ollama)
    results = search(mock_chroma, "Russian malware", threshold=0.1)
    assert "indicator--test-uuid-1234" in results[0]["opencti_url"]
    assert "embedded_text" in results[0]  # D-08
    assert "score" in results[0]  # AISEM-03
