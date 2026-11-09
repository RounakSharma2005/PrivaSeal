
"""Unit tests for Google Cloud DLP integration.

These tests use a mocked DLP client and do not require Google
Cloud credentials or make external API requests.
"""

from unittest.mock import MagicMock

import pytest

from google.cloud import dlp_v2


def inspect_text(dlp_client, project: str, text: str):
    """Inspect text using Google Cloud DLP."""

    parent = f"projects/{project}/locations/global"

    item = {"value": text}

    inspect_config = {
        "info_types": [
            {"name": "PERSON_NAME"},
            {"name": "EMAIL_ADDRESS"},
        ],
        "include_quote": True,
    }

    request = {
        "parent": parent,
        "inspect_config": inspect_config,
        "item": item,
    }

    response = dlp_client.inspect_content(
        request=request
    )

    findings = []

    for finding in response.result.findings:
        findings.append({
            "quote": finding.quote,
            "info_type": finding.info_type.name,
            "likelihood": finding.likelihood,
            "start": finding.location.codepoint_range.start,
            "end": finding.location.codepoint_range.end,
        })

    return findings


@pytest.fixture
def mock_dlp_client(monkeypatch):
    """Create a mocked Google DLP client."""

    mock_client = MagicMock()

    mock_finding = MagicMock()
    mock_finding.quote = "John Smith"
    mock_finding.info_type.name = "PERSON_NAME"
    mock_finding.likelihood = dlp_v2.Likelihood.POSSIBLE
    mock_finding.location.codepoint_range.start = 15
    mock_finding.location.codepoint_range.end = 25

    mock_response = MagicMock()
    mock_response.result.findings = [mock_finding]

    mock_client.inspect_content.return_value = mock_response

    monkeypatch.setattr(
        dlp_v2,
        "DlpServiceClient",
        lambda: mock_client,
    )

    return mock_client


def test_dlp_client_can_be_created(mock_dlp_client):
    """Verify that the mocked DLP client is available."""

    client = dlp_v2.DlpServiceClient()

    assert client is mock_dlp_client


def test_dlp_inspects_text(mock_dlp_client):
    """Verify that the DLP request is constructed correctly."""

    text = "My name is John Smith and my email is john@gmail.com"

    findings = inspect_text(
        mock_dlp_client,
        "test-project",
        text,
    )

    mock_dlp_client.inspect_content.assert_called_once()

    request = (
        mock_dlp_client.inspect_content.call_args.kwargs[
            "request"
        ]
    )

    assert request["parent"] == (
        "projects/test-project/locations/global"
    )

    assert request["item"] == {"value": text}

    assert request["inspect_config"]["include_quote"] is True

    assert {
        item["name"]
        for item in request["inspect_config"]["info_types"]
    } == {"PERSON_NAME", "EMAIL_ADDRESS"}

    assert len(findings) == 1


def test_dlp_returns_correct_finding(mock_dlp_client):
    """Verify that DLP findings are converted correctly."""

    findings = inspect_text(
        mock_dlp_client,
        "test-project",
        "My name is John Smith",
    )

    assert findings[0]["quote"] == "John Smith"
    assert findings[0]["info_type"] == "PERSON_NAME"
    assert findings[0]["start"] == 15
    assert findings[0]["end"] == 25


def test_dlp_handles_no_findings(mock_dlp_client):
    """Verify behavior when DLP detects no sensitive information."""

    mock_response = MagicMock()
    mock_response.result.findings = []

    mock_dlp_client.inspect_content.return_value = mock_response

    findings = inspect_text(
        mock_dlp_client,
        "test-project",
        "This is ordinary text.",
    )

    assert findings == []
