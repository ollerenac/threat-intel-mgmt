import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_pycti():
    client = MagicMock()
    client.indicator.create.return_value = {"id": "indicator--test-uuid-1234"}
    client.report.create.return_value = {"id": "report--test-uuid-5678"}
    client.stix_core_relationship.create.return_value = {"id": "relationship--test-uuid-9012"}
    client.attack_pattern.list.return_value = [
        {"id": "attack-pattern--test-uuid-3456", "name": "Phishing", "x_mitre_id": "T1566"}
    ]
    return client


@pytest.fixture
def mock_ollama():
    # ponytail: response.message.content attribute path validates Assumption A2 (ollama SDK 0.4.x+)
    client = MagicMock()
    client.chat.return_value.message.content = (
        '{"iocs":[{"type":"ip","value":"1.2.3.4"},{"type":"domain","value":"evil.example.com"}],'
        '"techniques":[{"name":"phishing","description":"email-based lure"}],'
        '"malware_families":["Emotet"],"threat_actors":[]}'
    )
    return client
