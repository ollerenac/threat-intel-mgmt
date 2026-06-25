import pytest

try:
    from opencti_client import lookup_attack_pattern, create_report, create_indicator
    _IMPORT_OK = True
except ImportError:
    _IMPORT_OK = False


_skip = pytest.mark.skipif(not _IMPORT_OK, reason="opencti_client not yet implemented")


@_skip
def test_lookup_attack_pattern(mock_pycti):
    # RED: opencti_client.py not yet implemented
    # When implemented: lookup_attack_pattern returns internal OpenCTI ID of matched attack-pattern
    result = lookup_attack_pattern(mock_pycti, "phishing")
    assert result == "attack-pattern--test-uuid-3456"
    pytest.fail("RED")


@_skip
def test_create_report(mock_pycti):
    # RED: opencti_client.py not yet implemented
    # When implemented: create_report returns the report dict from pycti with correct id
    result = create_report(
        mock_pycti,
        name="Test Report",
        published="2026-06-25T00:00:00Z",
        description="test",
        indicator_ids=["indicator--test-uuid-1234"],
    )
    assert result["id"] == "report--test-uuid-5678"
    pytest.fail("RED")
