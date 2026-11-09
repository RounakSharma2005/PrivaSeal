
import json
from pathlib import Path


DATASET_PATH = (
    Path(__file__).resolve().parents[1]
    / "evaluation_data"
    / "pii_test_cases.json"
)


def load_dataset(path: Path = DATASET_PATH) -> list[dict]:
    """Load and validate the synthetic PII evaluation dataset."""

    with path.open("r", encoding="utf-8") as file:
        cases = json.load(file)

    if not isinstance(cases, list):
        raise ValueError("Evaluation dataset must be a JSON list.")

    seen_ids = set()

    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Each dataset entry must be an object.")

        case_id = case.get("id")
        text = case.get("text")
        expected = case.get("expected")

        if not isinstance(case_id, str) or not case_id:
            raise ValueError("Each case requires a valid ID.")

        if case_id in seen_ids:
            raise ValueError(f"Duplicate case ID: {case_id}")

        seen_ids.add(case_id)

        if not isinstance(text, str):
            raise ValueError(f"Invalid text in {case_id}.")

        if not isinstance(expected, list):
            raise ValueError(f"Expected entities must be a list: {case_id}")

        for entity in expected:
            if (
                not isinstance(entity, dict)
                or not isinstance(entity.get("type"), str)
                or not isinstance(entity.get("value"), str)
                or not entity["value"]
            ):
                raise ValueError(
                    f"Invalid expected entity in {case_id}."
                )

            if entity["value"] not in text:
                raise ValueError(
                    f"Expected value is absent from text in {case_id}."
                )

    return cases
