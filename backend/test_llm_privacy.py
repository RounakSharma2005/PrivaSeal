
import pytest

from backend import pii_route


@pytest.mark.asyncio
async def test_llm_review_is_disabled_by_default(monkeypatch):
    async def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "LLM was called when review was disabled"
        )

    monkeypatch.setattr(
        pii_route,
        "_get_llm_explanations",
        fail_if_called,
    )

    result = await pii_route._run_pii_pipeline(
        "Contact: 9876543210"
    )

    assert "External LLM review is disabled" in result["overall_risk_summary"]
