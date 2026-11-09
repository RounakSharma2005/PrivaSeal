
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from backend.pii.analyzer import analyze_text
    from backend.evaluation.dataset import load_dataset
    from backend.evaluation.evaluator import evaluate_detector
except ImportError:
    from pii.analyzer import analyze_text
    from evaluation.dataset import load_dataset
    from evaluation.evaluator import evaluate_detector


def main():
    dataset = load_dataset()

    print("\nRunning Conseal PII detector evaluation...")
    print(f"Dataset cases: {len(dataset)}")

    # Run the actual production detector.
    report = evaluate_detector(
        detector=analyze_text,
        dataset=dataset,
    )

    report["metadata"] = {
        "project": "Conseal",
        "evaluation_type": "synthetic_baseline",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_size": len(dataset),
        "detector": "analyze_text",
    }

    output_path = (
        Path(__file__).resolve().parents[1]
        / "evaluation_data"
        / "latest_evaluation_report.json"
    )

    output_path.write_text(
        json.dumps(report, indent=4),
        encoding="utf-8",
    )

    print("\n========== CONSEAL EVALUATION ==========")

    overall = report["overall"]

    print(f"Precision : {overall['precision']:.4f}")
    print(f"Recall    : {overall['recall']:.4f}")
    print(f"F1-score  : {overall['f1_score']:.4f}")

    print("\n========== CATEGORY RESULTS ==========")

    for category, metrics in report["categories"].items():
        print(f"\n{category}")
        print(f"  Precision: {metrics['precision']:.4f}")
        print(f"  Recall:    {metrics['recall']:.4f}")
        print(f"  F1-score:  {metrics['f1_score']:.4f}")

    print("\nReport saved to:")
    print(output_path)


if __name__ == "__main__":
    main()
