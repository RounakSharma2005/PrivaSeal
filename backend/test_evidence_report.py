
from backend.pii.evidence_report import build_evidence_report
import json

def test_evidence_report_contains_aggregate_counts_only():
    entities = [
        {
            "type": "PAN",
            "value": "ABCDE1234F",
            "recommendation": "redact",
        },
        {
            "type": "EMAIL_ADDRESS",
            "value": "person@example.com",
            "recommendation": "keep",
        },
        {
            "type": "PAN",
            "value": "FGHIJ5678K",
            "recommendation": "review",
        },
    ]

    report = build_evidence_report(
        document_type="pdf",
        purpose="Contract review",
        entities=entities,
    )

    assert report["detection"]["total_entities_detected"] == 3
    assert report["detection"]["entity_counts"] == {
        "EMAIL_ADDRESS": 1,
        "PAN": 2,
    }

    assert report["policy_decisions"]["action_counts"] == {
        "redact": 1,
        "keep": 1,
        "review": 1,
    }

    serialized = str(report)

    assert "ABCDE1234F" not in serialized
    assert "FGHIJ5678K" not in serialized
    assert "person@example.com" not in serialized


def test_evidence_report_summarizes_pdf_verification():
    verification = {
        "verified": True,
        "checks": {
            "extracted_text": {"passed": True},
            "ocr_text": {
                "passed": True,
                "pages_checked": 2,
            },
            "metadata": {"passed": True},
        },
        "findings": [],
        "limitations": [
            "OCR can fail to recognize text.",
        ],
    }

    report = build_evidence_report(
        document_type="pdf",
        purpose="Document review",
        entities=[],
        verification=verification,
    )

    assert report["verification"]["performed"] is True
    assert report["verification"]["verified"] is True
    assert report["verification"]["finding_count"] == 0
    assert report["verification"]["checks"]["ocr_text"]["pages_checked"] == 2


def test_evidence_report_without_pdf_verification():
    report = build_evidence_report(
        document_type="text",
        purpose=None,
        entities=[],
    )

    assert report["verification"]["performed"] is False
    assert report["verification"]["verified"] is None
    assert report["processing"]["purpose"] == "Not specified"


def test_evidence_report_does_not_expose_verification_findings():
    verification = {
        "verified": False,
        "checks": {
            "extracted_text": {"passed": False},
        },
        "findings": [
            {
                "location": "page_text",
                "values_found": ["ABCDE1234F"],
            },
        ],
        "limitations": [],
    }

    report = build_evidence_report(
        document_type="pdf",
        purpose="Review",
        entities=[],
        verification=verification,
    )

    assert report["verification"]["finding_count"] == 1
    assert "ABCDE1234F" not in str(report)


def test_evidence_report_does_not_leak_sensitive_metadata():
    from backend.pii.evidence_report import build_evidence_report

    secret = "ABCDE1234F"

    report = build_evidence_report(
        document_type="PDF",
        purpose=secret,
        entities=[
            {
                "type": "IN_PAN",
                "recommendation": "redact",
                "value": secret,
            }
        ],
        sanitization_summary={
            "metadata_cleared": True,
            "unexpected_value": secret,
        },
        verification={
            "verified": True,
            "checks": {
                "metadata": {"passed": True},
                secret: {"passed": True},
            },
            "findings": [
                {"values_found": [secret]}
            ],
            "limitations": [secret],
        },
    )

    report_text = json.dumps(report)

    assert secret not in report_text
    assert report["processing"]["purpose"] == "unspecified"
    assert "unexpected_value" not in report["pdf_sanitization"]
    assert secret not in report["verification"]["limitations"]


def test_evidence_report_ignores_unknown_entity_types():
    from backend.pii.evidence_report import build_evidence_report

    report = build_evidence_report(
        document_type="PDF",
        purpose="document_redaction",
        entities=[
            {"type": "IN_PAN", "recommendation": "redact"},
            {"type": "SENSITIVE_CUSTOM_VALUE", "recommendation": "keep"},
        ],
    )

    assert report["detection"]["entity_counts"] == {
        "IN_PAN": 1,
        "UNKNOWN": 1,
    }


def test_evidence_report_rejects_unrecognized_actions():
    from backend.pii.evidence_report import build_evidence_report

    report = build_evidence_report(
        document_type="PDF",
        purpose="document_redaction",
        entities=[
            {"type": "IN_PAN", "recommendation": "unknown_action"},
        ],
    )

    assert report["policy_decisions"]["action_counts"] == {}


def test_evidence_report_sanitization_counts_are_validated():
    from backend.pii.evidence_report import build_evidence_report

    report = build_evidence_report(
        document_type="PDF",
        purpose="document_redaction",
        entities=[],
        sanitization_summary={
            "attachments_removed": 2,
            "annotations_removed": -1,
            "metadata_cleared": True,
            "links_removed": "sensitive data",
        },
    )

    summary = report["pdf_sanitization"]

    assert summary["attachments_removed"] == 2
    assert summary["metadata_cleared"] is True
    assert "annotations_removed" not in summary
    assert "links_removed" not in summary
