import pytest

# Import guard: skip all tests if production module not yet implemented
try:
    from generator import _build_stats_block, _make_updated_at_filter, _call_ollama, briefings
    import generator as _generator_module
    _SKIP_REASON = None
except ImportError as _e:
    _SKIP_REASON = f"generator not yet implemented: {_e}"

_skip = pytest.mark.skipif(_SKIP_REASON is not None, reason=_SKIP_REASON or "")


@_skip
def test_build_stats_block(mock_pycti):
    data = {
        "indicators": mock_pycti.indicator.list.return_value,
        "actors": mock_pycti.threat_actor.list.return_value,
        "malware": mock_pycti.malware.list.return_value,
        "campaigns": mock_pycti.campaign.list.return_value,
        "attack_patterns": mock_pycti.attack_pattern.list.return_value,
        "sectors": ["finance"],
    }
    result = _build_stats_block(data, 24)
    assert "Period:" in result


@_skip
def test_call_ollama_truncation(monkeypatch):
    # Mock returning 400-word string; result must be <= 320 words
    long_text = " ".join(["word"] * 400)
    fake_client = pytest.importorskip("unittest.mock").MagicMock()
    fake_client.chat.return_value.message.content = long_text
    monkeypatch.setattr(_generator_module, "_ollama_client", fake_client)
    result = _call_ollama("some stats block")
    assert len(result.split()) <= 320


@_skip
def test_updated_at_filter():
    result = _make_updated_at_filter(72)
    assert result["filters"][0]["key"] == "updated_at"


@_skip
def test_post_generate_returns_immediately(monkeypatch):
    from fastapi.testclient import TestClient
    import main as _main_module

    async def _noop(briefing_id, period_hours):
        pass

    monkeypatch.setattr(_main_module, "run_generate", _noop)
    client = TestClient(_main_module.app)
    response = client.post("/generate", json={"period_hours": 24})
    assert response.status_code == 200
    assert "briefing_id" in response.json()
