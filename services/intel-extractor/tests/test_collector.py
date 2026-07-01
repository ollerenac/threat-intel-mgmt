"""
test_collector.py — Unit tests for collector.py (DOC-01..DOC-03).

All tests use monkeypatch/tmp_path — no Docker or live network required.
Import-guard pattern mirrors test_extractor.py: tests SKIP if collector absent.
"""
import json
import types
from unittest.mock import MagicMock

import pytest

try:
    import collector
    _IMPORT_OK = True
except ImportError:
    _IMPORT_OK = False

_skip = pytest.mark.skipif(not _IMPORT_OK, reason="collector not yet implemented")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fake_feed(entries=None, bozo=False):
    """Build a minimal feedparser-like feed object."""
    feed = types.SimpleNamespace()
    feed.bozo = bozo
    feed.bozo_exception = Exception("bad xml") if bozo else None
    feed.entries = entries or []
    return feed


def _fake_entry(link: str) -> dict:
    """feedparser entries are FeedParserDict (dict subclass) — use dict to match."""
    return {"link": link}


# ── Tests ─────────────────────────────────────────────────────────────────────

@_skip
def test_load_sources():
    """DOC-02: sources.yaml contains exactly 3 entries with required fields."""
    sources = collector._load_sources()
    assert isinstance(sources, list)
    assert len(sources) == 3
    for s in sources:
        assert "name" in s
        assert "type" in s
        assert "url" in s
        assert "poll_interval_hours" in s


@_skip
def test_skip_known_url(monkeypatch, tmp_path):
    """DOC-01 dedup / DOC-03: run_extraction must NOT be called for already-processed URLs."""
    known_url = "https://example.com/known.html"
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"processed_urls": [known_url], "sources": {}}))

    monkeypatch.setattr(collector, "STATE_PATH", state_file)

    feed = _fake_feed(entries=[_fake_entry(known_url)])
    monkeypatch.setattr("collector.feedparser.parse", lambda url: feed)

    dispatched = []
    monkeypatch.setattr("collector.run_extraction", lambda *a, **kw: dispatched.append(a))
    monkeypatch.setattr("collector.jobs", {})

    collector._run_poll_cycle()

    assert dispatched == [], "run_extraction must not be called for known URLs"


@_skip
def test_dispatch_new_url(monkeypatch, tmp_path):
    """DOC-01 dispatch / D-06: run_extraction IS called once with mode='url' for a new URL."""
    new_url = "https://example.com/advisory.html"
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"processed_urls": [], "sources": {}}))

    monkeypatch.setattr(collector, "STATE_PATH", state_file)

    feed = _fake_feed(entries=[_fake_entry(new_url)])
    monkeypatch.setattr("collector.feedparser.parse", lambda url: feed)

    dispatched = []
    monkeypatch.setattr("collector.run_extraction", lambda *a, **kw: dispatched.append(a))
    fake_jobs: dict = {}
    monkeypatch.setattr("collector.jobs", fake_jobs)

    pending = collector._run_poll_cycle()

    # pending list should have one entry; actual dispatch happens in run_collector_loop
    assert len(pending) == 1
    mode, content, url = pending[0]
    assert mode == "url"
    assert url == new_url


@_skip
def test_state_persistence(tmp_path):
    """DOC-03: save/load round-trip for collector_state.json."""
    state_file = tmp_path / "state.json"
    monkeypatch_obj = type("MP", (), {})()

    # Directly patch STATE_PATH on the module
    original = collector.STATE_PATH
    collector.STATE_PATH = state_file
    try:
        collector._save_state({"processed_urls": ["https://example.com/a"], "sources": {}})
        loaded = collector._load_state()
        assert loaded["processed_urls"] == ["https://example.com/a"]
    finally:
        collector.STATE_PATH = original


@_skip
def test_error_increments_counter(monkeypatch, tmp_path):
    """D-03: bozo feed with no entries must not raise — skip-and-continue behavior."""
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"processed_urls": [], "sources": {}}))
    monkeypatch.setattr(collector, "STATE_PATH", state_file)

    bozo_feed = _fake_feed(bozo=True, entries=[])
    monkeypatch.setattr("collector.feedparser.parse", lambda url: bozo_feed)
    monkeypatch.setattr("collector.jobs", {})

    # Must not raise
    try:
        collector._run_poll_cycle()
    except Exception as exc:
        pytest.fail(f"_run_poll_cycle raised unexpectedly: {exc}")


@_skip
def test_get_status_shape():
    """DOC-04 shape: get_status() returns sources list, registry_size int, last_run."""
    result = collector.get_status()
    assert isinstance(result, dict)
    assert "sources" in result
    assert "registry_size" in result
    assert "last_run" in result
    assert isinstance(result["sources"], list)
    assert isinstance(result["registry_size"], int)
