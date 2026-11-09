
def calculate_metrics(
    true_positives: int,
    false_positives: int,
    false_negatives: int,
) -> dict:
    """Calculate precision, recall and F1-score."""

    precision_denominator = true_positives + false_positives
    recall_denominator = true_positives + false_negatives

    precision = (
        true_positives / precision_denominator
        if precision_denominator
        else 0.0
    )

    recall = (
        true_positives / recall_denominator
        if recall_denominator
        else 0.0
    )

    f1_score = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )

    return {
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1_score, 4),
    }
