
import pytest

from backend.pii_route import _get_policy_action


@pytest.mark.parametrize(
    "entity_type, policy, expected",
    [
        (
            "PERSON",
            {"hide": ["PERSON"], "keep": [], "review": []},
            ("redact", "hide"),
        ),
        (
            "EMAIL_ADDRESS",
            {"hide": [], "keep": ["EMAIL_ADDRESS"], "review": []},
            ("keep", "keep"),
        ),
        (
            "AADHAAR",
            {"hide": [], "keep": [], "review": ["AADHAAR"]},
            ("review", "review"),
        ),
        (
            "IFSC",
            {"hide": [], "keep": ["IFSC"], "review": []},
            ("keep", "keep"),
        ),
    ],
)
def test_policy_actions(entity_type, policy, expected):
    assert _get_policy_action(entity_type, policy) == expected


def test_hide_takes_precedence_over_review_and_keep():
    policy = {
        "hide": ["PERSON"],
        "keep": ["PERSON"],
        "review": ["PERSON"],
    }

    assert _get_policy_action("PERSON", policy) == ("redact", "hide")


def test_review_takes_precedence_over_keep():
    policy = {
        "hide": [],
        "keep": ["PERSON"],
        "review": ["PERSON"],
    }

    assert _get_policy_action("PERSON", policy) == ("review", "review")


def test_unmatched_entity_defaults_to_redaction():
    policy = {
        "hide": [],
        "keep": ["IFSC"],
        "review": [],
    }

    assert _get_policy_action("PERSON", policy) == (
        "redact",
        "default_redact",
    )


def test_no_policy_preserves_default_redaction():
    assert _get_policy_action("PERSON", None) == ("redact", None)
