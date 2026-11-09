
from types import SimpleNamespace

import pytest

from backend.evaluation.metrics import calculate_metrics
from backend.evaluation.dataset import load_dataset
from backend.evaluation.evaluator import evaluate_detector


def test_perfect_metrics():
    result = calculate_metrics(10, 0, 0)

    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["f1_score"] == 1.0


def test_metrics_with_false_positives():
    result = calculate_metrics(8, 2, 0)

    assert result["precision"] == 0.8
    assert result["recall"] == 1.0


def test_metrics_with_false_negatives():
    result = calculate_metrics(8, 0, 2)

    assert result["precision"] == 1.0
    assert result["recall"] == 0.8


def test_zero_predictions():
    result = calculate_metrics(0, 0, 0)

    assert result["precision"] == 0.0
    assert result["recall"] == 0.0
    assert result["f1_score"] == 0.0


def test_evaluator_exact_matching():
    dataset = [
        {
            "id": "test_1",
            "text": "PAN ABCDE1234F",
            "expected": [
                {
                    "type": "PAN",
                    "value": "ABCDE1234F",
                }
            ],
        }
    ]

    def fake_detector(text, score_threshold):
        return [
            SimpleNamespace(
                entity_type="PAN",
                start=4,
                end=14,
                score=0.99,
            )
        ]

    result = evaluate_detector(fake_detector, dataset)

    assert result["overall"]["true_positives"] == 1
    assert result["overall"]["false_positives"] == 0
    assert result["overall"]["false_negatives"] == 0
    assert result["overall"]["f1_score"] == 1.0


def test_dataset_loading():
    dataset = load_dataset()

    assert len(dataset) == 6
