import pytest

try:
    from indexer import build_embed_text
    _IMPORT_OK = True
except ImportError:
    _IMPORT_OK = False

_skip = pytest.mark.skipif(not _IMPORT_OK, reason="indexer not yet implemented")


@_skip
def test_build_embed_text_with_description():
    # D-01: em dash format when description present, labels appended
    ind = {
        "x_opencti_main_observable_type": "IPv4-Addr",
        "name": "1.2.3.4",
        "description": "C2 server",
        "objectLabel": [{"value": "botnet-cc"}],
    }
    assert build_embed_text(ind) == "IPv4-Addr: 1.2.3.4 — C2 server botnet-cc"


@_skip
def test_build_embed_text_no_description():
    # D-03: bracket format when no description
    ind = {
        "x_opencti_main_observable_type": "IPv4-Addr",
        "name": "1.2.3.4",
        "description": None,
        "objectLabel": [{"value": "malware-distribution"}],
    }
    assert build_embed_text(ind) == "IPv4-Addr: 1.2.3.4 [malware-distribution]"


@_skip
def test_build_embed_text_no_description_no_labels():
    # D-03: empty bracket when no description and no labels
    ind = {
        "x_opencti_main_observable_type": "IPv4-Addr",
        "name": "1.2.3.4",
        "description": None,
        "objectLabel": [],
    }
    assert build_embed_text(ind) == "IPv4-Addr: 1.2.3.4 []"


@_skip
def test_build_embed_text_empty_labels_ignored():
    # D-01: no trailing space when labels empty but description present
    ind = {
        "x_opencti_main_observable_type": "IPv4-Addr",
        "name": "1.2.3.4",
        "description": "Ransomware C2",
        "objectLabel": [],
    }
    assert build_embed_text(ind) == "IPv4-Addr: 1.2.3.4 — Ransomware C2"
