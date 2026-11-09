
from types import SimpleNamespace

import pytest

import backend.pii_route as route


class FakeAnonymizer:
    """A predictable anonymizer for testing policy filtering."""

    def anonymize(self, text, analyzer_results):
        results = sorted(
            analyzer_results,
            key=lambda item: item.start,
            reverse=True,
        )

        for result in results:
            text = (
                text[:result.start]
                + f"<{result.entity_type}>"
                + text[result.end:]
            )

        return SimpleNamespace(text=text)


def make_result(text, entity_type, value, score=0.99):
    start = text.index(value)

    return SimpleNamespace(
        entity_type=entity_type,
        start=start,
        end=start + len(value),
        score=score,
    )


@pytest.fixture
def mock_pipeline(monkeypatch):
    monkeypatch.setattr(route, "ENABLE_LLM_REVIEW", False)
    monkeypatch.setattr(route, "anonymizer", FakeAnonymizer())

    def configure_detections(text, entity_types):
        results = [
            make_result(text, entity_type, value)
            for entity_type, value in entity_types
        ]

        monkeypatch.setattr(
            route,
            "analyze_text",
            lambda *args, **kwargs: results,
        )

    return configure_detections


@pytest.mark.asyncio
async def test_hide_entity_is_redacted(mock_pipeline):
    text = "Contact Rahul Sharma for assistance."

    mock_pipeline(
        text,
        [("PERSON", "Rahul Sharma")],
    )

    result = await route._run_pii_pipeline(
        text,
        policy={
            "hide": ["PERSON"],
            "keep": [],
            "review": [],
        },
    )

    assert "Rahul Sharma" not in result["anonymized_text"]
    assert "<PERSON>" in result["anonymized_text"]


@pytest.mark.asyncio
async def test_keep_entity_remains_visible(mock_pipeline):
    text = "Bank IFSC is SBIN0001234."

    mock_pipeline(
        text,
        [("IFSC", "SBIN0001234")],
    )

    result = await route._run_pii_pipeline(
        text,
        policy={
            "hide": [],
            "keep": ["IFSC"],
            "review": [],
        },
    )

    assert "SBIN0001234" in result["anonymized_text"]

    entity = result["entities"][0]
    assert entity.recommendation == "keep"


@pytest.mark.asyncio
async def test_review_entity_remains_visible_and_is_flagged(
    mock_pipeline,
):
    text = "Aadhaar number is 123456789012."

    mock_pipeline(
        text,
        [("AADHAAR", "123456789012")],
    )

    result = await route._run_pii_pipeline(
        text,
        policy={
            "hide": [],
            "keep": [],
            "review": ["AADHAAR"],
        },
    )

    assert "123456789012" in result["anonymized_text"]

    entity = result["entities"][0]
    assert entity.recommendation == "review"

    assert any(
        item.value == "123456789012"
        and "human review" in item.explanation.lower()
        for item in result["non_redacted"]
    )


@pytest.mark.asyncio
async def test_mixed_policy_applies_all_three_actions(mock_pipeline):
    text = (
        "Rahul Sharma uses rahul@example.com. "
        "Aadhaar number is 123456789012."
    )

    mock_pipeline(
        text,
        [
            ("PERSON", "Rahul Sharma"),
            ("EMAIL_ADDRESS", "rahul@example.com"),
            ("AADHAAR", "123456789012"),
        ],
    )

    result = await route._run_pii_pipeline(
        text,
        policy={
            "hide": ["PERSON"],
            "keep": ["EMAIL_ADDRESS"],
            "review": ["AADHAAR"],
        },
    )

    output = result["anonymized_text"]

    assert "Rahul Sharma" not in output
    assert "<PERSON>" in output

    assert "rahul@example.com" in output
    assert "123456789012" in output

    recommendations = {
        entity.type: entity.recommendation
        for entity in result["entities"]
    }

    assert recommendations["PERSON"] == "redact"
    assert recommendations["EMAIL_ADDRESS"] == "keep"
    assert recommendations["AADHAAR"] == "review"


@pytest.mark.asyncio
async def test_no_policy_preserves_default_redaction(mock_pipeline):
    text = "Contact Rahul Sharma."

    mock_pipeline(
        text,
        [("PERSON", "Rahul Sharma")],
    )

    result = await route._run_pii_pipeline(text)

    assert "Rahul Sharma" not in result["anonymized_text"]
    assert "<PERSON>" in result["anonymized_text"]
