import pytest

try:
    from opencti_client import lookup_attack_pattern, create_report, create_indicator
    _IMPORT_OK = True
except ImportError:
    _IMPORT_OK = False


_skip = pytest.mark.skipif(not _IMPORT_OK, reason="opencti_client not yet implemented")


def test_lookup_attack_pattern(mock_pycti):
    result = lookup_attack_pattern(mock_pycti, "phishing")
    assert result == "attack-pattern--test-uuid-3456"


def test_create_report(mock_pycti):
    result = create_report(
        mock_pycti,
        name="Test Report",
        published="2026-06-25T00:00:00Z",
        description="test",
        indicator_ids=["indicator--test-uuid-1234"],
    )
    assert result["id"] == "report--test-uuid-5678"
