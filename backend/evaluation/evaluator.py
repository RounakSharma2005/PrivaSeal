
from collections import defaultdict

from .metrics import calculate_metrics


def evaluate_detector(detector, dataset: list[dict]) -> dict:
    """
    Evaluate a detector using exact entity type and value matching.

    Also return case-level diagnostics to explain mismatches.
    """

    category_counts = defaultdict(
        lambda: {"tp": 0, "fp": 0, "fn": 0}
    )

    total_tp = 0
    total_fp = 0
    total_fn = 0

    case_results = []

    for case in dataset:
        text = case["text"]

        expected = {
            (item["type"], item["value"])
            for item in case["expected"]
        }

        detected_results = detector(
            text,
            score_threshold=0.91,
        )

        detected = set()

        for result in detected_results:
            detected.add(
                (
                    result.entity_type,
                    text[result.start:result.end],
                )
            )

        true_positives = expected & detected
        false_positives = detected - expected
        false_negatives = expected - detected

        total_tp += len(true_positives)
        total_fp += len(false_positives)
        total_fn += len(false_negatives)

        for entity_type, _ in (
            true_positives | false_positives | false_negatives
        ):
            counts = category_counts[entity_type]

            counts["tp"] += sum(
                1 for item in true_positives
                if item[0] == entity_type
            )

            counts["fp"] += sum(
                1 for item in false_positives
                if item[0] == entity_type
            )

            counts["fn"] += sum(
                1 for item in false_negatives
                if item[0] == entity_type
            )

        case_results.append({
            "case_id": case["id"],
            "text": text,
            "expected": [
                {"type": entity_type, "value": value}
                for entity_type, value in sorted(expected)
            ],
            "detected": [
                {"type": entity_type, "value": value}
                for entity_type, value in sorted(detected)
            ],
            "true_positives": [
                {"type": entity_type, "value": value}
                for entity_type, value in sorted(true_positives)
            ],
            "false_positives": [
                {"type": entity_type, "value": value}
                for entity_type, value in sorted(false_positives)
            ],
            "false_negatives": [
                {"type": entity_type, "value": value}
                for entity_type, value in sorted(false_negatives)
            ],
        })

    category_metrics = {
        category: calculate_metrics(
            counts["tp"],
            counts["fp"],
            counts["fn"],
        )
        for category, counts in category_counts.items()
    }

    return {
        "overall": calculate_metrics(
            total_tp,
            total_fp,
            total_fn,
        ),
        "categories": category_metrics,
        "dataset_size": len(dataset),
        "case_results": case_results,
    }
