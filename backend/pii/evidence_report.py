
"""Privacy-preserving processing evidence reports.

Only validated metadata and aggregate processing results are retained.
Raw document text and detected PII values must never be included.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


REPORT_VERSION = "1.0"

ALLOWED_ENTITY_TYPES = {
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "INDIAN_PHONE",
    "LOCATION",
    "ADDRESS",
    "DATE_OF_BIRTH",
    "CREDIT_CARD",
    "US_SSN",
    "IP_ADDRESS",
    "IBAN_CODE",
    "EMPLOYEE_ID",
    "URL",
    "IN_AADHAAR",
    "AADHAAR",
    "IN_PAN",
    "PAN",
    "IN_VOTER",
    "IN_PASSPORT",
    "IN_UPI",
    "UPI_ID",
    "IN_IFSC",
    "IFSC",
    "UNKNOWN",
}

ALLOWED_ACTIONS = {"redact", "anonymize", "keep", "review"}

ALLOWED_CHECKS = {
    "extracted_text",
    "ocr_text",
    "metadata",
    "annotations",
    "form_fields",
    "bookmarks",
    "embedded_files",
    "pdf_open",
}

ALLOWED_SANITIZATION_FIELDS = {
    "attachments_removed",
    "annotations_removed",
    "form_fields_removed",
    "links_removed",
    "bookmarks_removed",
    "metadata_cleared",
    "xmp_metadata_cleared",
}

REPORT_LIMITATIONS = [
    "This report records processing evidence, not legal compliance.",
    "Entity counts depend on the accuracy of the configured detectors.",
    "Verification checks cannot prove complete anonymization.",
]


def _safe_code(value: Any, allowed: set[str], default: str) -> str:
    """Accept only predefined machine-readable values."""
    if not isinstance(value, str):
        return default

    normalized = value.strip().upper()

    return normalized if normalized in allowed else default


def _safe_count(value: Any) -> int | None:
    """Accept non-negative integers, excluding booleans."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None

    if value < 0:
        return None

    return value


def _count_entity_types(
    entities: list[dict[str, Any]],
) -> dict[str, int]:
    """Count validated entity types without retaining entity values."""

    counts = Counter()

    for entity in entities:
        if not isinstance(entity, dict):
            continue

        entity_type = _safe_code(
            entity.get("type"),
            ALLOWED_ENTITY_TYPES,
            "UNKNOWN",
        )

        counts[entity_type] += 1

    return dict(sorted(counts.items()))


def _count_policy_actions(
    entities: list[dict[str, Any]],
) -> dict[str, int]:
    """Count recognized policy actions only."""

    counts = Counter()

    for entity in entities:
        if not isinstance(entity, dict):
            continue

        action = entity.get("recommendation")

        if not isinstance(action, str):
            action = entity.get("action")

        if not isinstance(action, str):
            continue

        action = action.strip().lower()

        if action in ALLOWED_ACTIONS:
            counts[action] += 1

    return {
        action: counts[action]
        for action in sorted(ALLOWED_ACTIONS)
        if counts[action] > 0
    }


def _summarize_sanitization(
    summary: dict[str, Any] | None,
) -> dict[str, Any]:
    """Copy only explicitly approved sanitization metadata."""

    if not isinstance(summary, dict):
        return {"performed": False}

    safe_summary: dict[str, Any] = {"performed": True}

    for field in ALLOWED_SANITIZATION_FIELDS:
        value = summary.get(field)

        if isinstance(value, bool):
            safe_summary[field] = value
        elif _safe_count(value) is not None:
            safe_summary[field] = value

    return safe_summary


def _summarize_verification(
    verification: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return an aggregate verification summary without raw findings."""

    if not isinstance(verification, dict):
        return {
            "performed": False,
            "verified": None,
            "checks": {},
            "finding_count": 0,
            "limitations": [],
        }

    checks: dict[str, Any] = {}

    raw_checks = verification.get("checks", {})

    if isinstance(raw_checks, dict):
        for name, result in raw_checks.items():

            if name not in ALLOWED_CHECKS:
                continue

            if not isinstance(result, dict):
                continue

            safe_check = {
                "passed": result.get("passed") is True,
                "status": (
                    result.get("status")
                    if result.get("status") in {
                        "completed",
                        "failed",
                        "skipped",
                    }
                    else "completed"
                ),
            }

            for field in ("pages_checked", "files_found"):
                count = _safe_count(result.get(field))

                if count is not None:
                    safe_check[field] = count

            checks[name] = safe_check

    findings = verification.get("findings", [])

    finding_count = (
        len(findings)
        if isinstance(findings, list)
        else 0
    )

    return {
        "performed": True,
        "verified": verification.get("verified") is True,
        "checks": checks,
        "finding_count": finding_count,
        "limitations": [
            "Verification checks cannot prove complete anonymization.",
            "Only the configured verification checks were evaluated.",
        ],
    }


def _safe_purpose(purpose: str | None) -> str:
    """Accept only predefined processing purpose identifiers."""

    if purpose is None or not isinstance(purpose, str):
        return "Not specified"

    normalized = purpose.strip().lower()

    allowed_purposes = {
        "document_redaction",
        "contract_review",
    }

    # Normalize a human-readable legacy purpose.
    normalized = normalized.replace(" ", "_")

    if normalized in allowed_purposes:
        return normalized

    return "unspecified"
def build_evidence_report(
    *,
    document_type: str,
    purpose: str | None,
    entities: list[dict[str, Any]],
    sanitization_summary: dict[str, Any] | None = None,
    verification: dict[str, Any] | None = None,
    processing_status: str = "completed",
) -> dict[str, Any]:
    """Build a privacy-preserving processing evidence report."""

    if not isinstance(entities, list):
        raise ValueError("Entities must be a list.")

    safe_document_type = _safe_code(
        document_type,
        {"PDF", "TEXT", "IMAGE"},
        "UNKNOWN",
    )

    safe_status = _safe_code(
        processing_status,
        {"COMPLETED", "FAILED", "PARTIAL"},
        "UNKNOWN",
    ).lower()

    entity_counts = _count_entity_types(entities)
    action_counts = _count_policy_actions(entities)

    return {
        "report_version": REPORT_VERSION,
        "report_id": str(uuid4()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "processing": {
            "document_type": safe_document_type,
            "purpose": _safe_purpose(purpose),
            "status": safe_status,
        },
        "detection": {
            "total_entities_detected": sum(entity_counts.values()),
            "entity_counts": entity_counts,
        },
        "policy_decisions": {
            "action_counts": action_counts,
        },
        "pdf_sanitization": _summarize_sanitization(
            sanitization_summary
        ),
        "verification": _summarize_verification(verification),
        "privacy": {
            "contains_raw_pii": False,
            "contains_original_document_text": False,
            "limitations": REPORT_LIMITATIONS.copy(),
        },
    }
