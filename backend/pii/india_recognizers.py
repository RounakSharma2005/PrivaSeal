
"""
India-specific PII detection and validation utilities.

Detects candidate Aadhaar, PAN, UPI ID, IFSC, and Indian phone values.

Format and checksum checks are signals, not proof that an identifier
was issued or belongs to a particular person.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PIIMatch:
    """A detected candidate with offsets into the original text."""

    entity_type: str
    value: str
    start: int
    end: int
    confidence: float


PATTERNS = {
    "AADHAAR": re.compile(
        r"(?<!\d)(?:\d[ -]?){11}\d(?!\d)"
    ),

    "PAN": re.compile(
        r"(?<![A-Z0-9])[A-Z]{5}\d{4}[A-Z](?![A-Z0-9])",
        re.IGNORECASE,
    ),

    # Trailing sentence punctuation is not included in the match.
    "UPI_ID": re.compile(
        r"(?<![\w.+-])[a-zA-Z0-9][a-zA-Z0-9._-]{0,254}"
        r"@[a-zA-Z][a-zA-Z0-9]{1,63}(?![\w-])"
    ),

    "IFSC": re.compile(
        r"(?<![A-Z0-9])[A-Z]{4}0[A-Z0-9]{6}(?![A-Z0-9])",
        re.IGNORECASE,
    ),

    "INDIAN_PHONE": re.compile(
        r"(?<!\d)(?:\+91[\s-]?|91[\s-]?|0[\s-]?)?"
        r"[6-9]\d{4}[\s-]?\d{5}(?!\d)"
    ),
}


# Verhoeff multiplication table.
_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)

_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)


# Common UPI handles.
# This is a supplementary list, not an exhaustive registry.
UPI_HANDLES = {
    "okaxis",
    "okhdfcbank",
    "okicici",
    "oksbi",
    "ybl",
    "ibl",
    "axl",
    "paytm",
    "upi",
    "apl",
    "boi",
    "sbi",
    "hdfcbank",
    "icici",
    "kotak",
    "barodampay",
}


_LABEL_PATTERN = re.compile(
    r"\b(email|e-mail|upi(?:\s+id)?|vpa|payment\s+address|"
    r"aadhaar|aadhar|uidai|uid)\b",
    re.IGNORECASE,
)


def normalize_digits(value: str) -> str:
    """Remove spaces and hyphens from an identifier candidate."""

    return re.sub(r"[\s-]", "", value)


def is_valid_aadhaar_checksum(value: str) -> bool:
    """
    Check the Verhoeff checksum of a 12-digit Aadhaar candidate.

    A valid checksum does not prove that the number was issued or
    belongs to a particular person.
    """

    digits = normalize_digits(value)

    if not re.fullmatch(r"\d{12}", digits):
        return False

    checksum = 0

    for position, digit in enumerate(reversed(digits)):
        checksum = _D[checksum][_P[position % 8][int(digit)]]

    return checksum == 0


def _nearest_label(text: str, start: int) -> str | None:
    """Return the nearest relevant label before a candidate on its line."""

    line_start = text.rfind("\n", 0, start) + 1
    prefix = text[line_start:start]

    labels = list(_LABEL_PATTERN.finditer(prefix))

    if not labels:
        return None

    nearest = labels[-1]

    # Avoid using a distant label to classify an unrelated identifier.
    if len(prefix) - nearest.end() > 60:
        return None

    return nearest.group(1).lower()


def _has_aadhaar_context(text: str, start: int) -> bool:
    label = _nearest_label(text, start)

    return label in {
        "aadhaar",
        "aadhar",
        "uid",
        "uidai",
    }


def _is_upi_candidate(
    text: str,
    start: int,
    value: str,
) -> bool:
    """Reduce email/UPI overlap using nearby labels and known handles."""

    label = _nearest_label(text, start)

    if label in {
        "upi",
        "upi id",
        "vpa",
        "payment address",
    }:
        return True

    # An explicit email label takes precedence over generic UPI shape.
    if label in {"email", "e-mail"}:
        return False

    handle = value.rsplit("@", 1)[-1].lower()

    return handle in UPI_HANDLES


def _find_matches(
    text: str,
    entity_type: str,
) -> list[PIIMatch]:
    """Find candidates while preserving original text offsets."""

    pattern = PATTERNS[entity_type]
    matches: list[PIIMatch] = []

    for match in pattern.finditer(text):
        value = match.group(0)

        if entity_type == "AADHAAR":
            valid_checksum = is_valid_aadhaar_checksum(value)

            if valid_checksum:
                confidence = 0.95

            elif _has_aadhaar_context(text, match.start()):
                # Keep a context-supported candidate for review/redaction.
                confidence = 0.70

            else:
                continue

        elif entity_type == "PAN":
            if not re.fullmatch(
                r"[A-Z]{5}\d{4}[A-Z]",
                value,
                re.IGNORECASE,
            ):
                continue

            confidence = 0.90

        elif entity_type == "IFSC":
            confidence = 0.90

        elif entity_type == "UPI_ID":
            if not _is_upi_candidate(
                text,
                match.start(),
                value,
            ):
                continue

            confidence = 0.85

        elif entity_type == "INDIAN_PHONE":
            digits = re.sub(r"\D", "", value)

            if digits.startswith("91") and len(digits) == 12:
                digits = digits[2:]

            elif digits.startswith("0") and len(digits) == 11:
                digits = digits[1:]

            if len(digits) != 10 or digits[0] not in "6789":
                continue

            confidence = 0.80

        else:
            continue

        matches.append(
            PIIMatch(
                entity_type=entity_type,
                value=value,
                start=match.start(),
                end=match.end(),
                confidence=confidence,
            )
        )

    return matches


def detect_indian_pii(text: str) -> list[PIIMatch]:
    """
    Detect supported India-specific PII candidates.

    Offsets refer to the original input string. Results can overlap
    with other recognizers and should be reviewed before redaction.
    """

    if not isinstance(text, str) or not text:
        return []

    matches: list[PIIMatch] = []

    for entity_type in PATTERNS:
        matches.extend(
            _find_matches(text, entity_type)
        )

    return sorted(
        matches,
        key=lambda item: (item.start, item.end),
    )
