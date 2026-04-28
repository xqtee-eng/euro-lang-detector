import argparse
import json
from collections import Counter, defaultdict

from src.config import DATASET_PATH, EVALUATION_REPORT_PATH, TEST_DATASET_PATH
from src.hybrid import smart_detect_details
from src.related_languages import same_related_group
from src.storage import record_training_run


def _default_dataset_path():
    return TEST_DATASET_PATH if TEST_DATASET_PATH.exists() else DATASET_PATH


def evaluate(dataset_path=None, save_report=True):
    dataset_path = dataset_path or _default_dataset_path()
    correct = 0
    group_correct = 0
    total = 0
    unknown = 0
    by_language = defaultdict(
        lambda: {"samples": 0, "correct": 0, "group_correct": 0, "unknown": 0}
    )
    confusion = defaultdict(Counter)
    low_confidence = []

    with open(dataset_path, "r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            expected = row["lang"]
            result = smart_detect_details(row["text"], record_unknown=False)
            prediction = result["language"]

            if prediction == expected:
                correct += 1
                by_language[expected]["correct"] += 1
                group_correct += 1
                by_language[expected]["group_correct"] += 1
            elif same_related_group(expected, prediction):
                group_correct += 1
                by_language[expected]["group_correct"] += 1
            if prediction == "unknown":
                unknown += 1
                by_language[expected]["unknown"] += 1

            confidence = float(result.get("confidence", 0.0))
            related = result.get("related_classifier") or {}
            if confidence < 0.45 or prediction != expected:
                low_confidence.append(
                    {
                        "text": row["text"],
                        "expected": expected,
                        "predicted": prediction,
                        "confidence": round(confidence, 4),
                        "source": result.get("source"),
                        "reason": result.get("reason"),
                        "language_group": result.get("language_group"),
                        "group_reliability": result.get("group_reliability"),
                        "ambiguous_group": result.get("ambiguous_group", False),
                        "related_margin": related.get("margin"),
                        "related_suggested_language": related.get("suggested_language"),
                        "related_applied": related.get("applied", False),
                    }
                )

            by_language[expected]["samples"] += 1
            confusion[expected][prediction] += 1
            total += 1

    accuracy = correct / total if total else 0.0
    group_accuracy = group_correct / total if total else 0.0
    language_rows = {}
    for language, stats in sorted(by_language.items()):
        samples = stats["samples"]
        language_rows[language] = {
            **stats,
            "accuracy": round(stats["correct"] / samples, 4) if samples else 0.0,
            "group_accuracy": (
                round(stats.get("group_correct", 0) / samples, 4) if samples else 0.0
            ),
        }

    report = {
        "dataset": str(dataset_path),
        "samples": total,
        "correct": correct,
        "group_correct": group_correct,
        "unknown": unknown,
        "accuracy": round(accuracy, 4),
        "group_accuracy": round(group_accuracy, 4),
        "by_language": language_rows,
        "confusion": {
            expected: dict(predictions)
            for expected, predictions in sorted(confusion.items())
        },
        "low_confidence": low_confidence[:100],
    }

    print(f"Dataset: {dataset_path}")
    print(f"Samples: {total}")
    print(f"Correct: {correct}")
    print(f"Group-correct: {group_correct}")
    print(f"Unknown: {unknown}")
    if total == 0:
        print(
            "Dataset is empty. Add samples to data/dataset.jsonl or data/raw/*.txt first."
        )
    print(f"Accuracy: {accuracy:.4f}")
    print(f"Group accuracy: {group_accuracy:.4f}")
    print("By language:")
    for language, stats in language_rows.items():
        print(
            f"  {language}: {stats['correct']}/{stats['samples']} "
            f"accuracy={stats['accuracy']:.4f} "
            f"group_accuracy={stats['group_accuracy']:.4f} unknown={stats['unknown']}"
        )

    if low_confidence:
        print("\nWrong / low-confidence cases:")
        for item in low_confidence[:100]:
            print(
                f"  {item['text']!r} "
                f"expected={item['expected']} "
                f"got={item['predicted']} "
                f"confidence={item['confidence']} "
                f"source={item['source']} "
                f"reason={item['reason']}"
            )

    if save_report:
        EVALUATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(EVALUATION_REPORT_PATH, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        print(f"Saved report to {EVALUATION_REPORT_PATH}")
        record_training_run(
            kind="evaluate",
            samples=total,
            correct=correct,
            unknown=unknown,
            accuracy=accuracy,
            report_path=str(EVALUATION_REPORT_PATH),
            notes=f"Evaluated {dataset_path}",
        )

    return accuracy


def main():
    parser = argparse.ArgumentParser(description="Evaluate the detector.")
    parser.add_argument(
        "--dataset", default=None, help="Optional path to a jsonl dataset."
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Do not write models/evaluation_report.json.",
    )
    args = parser.parse_args()
    evaluate(dataset_path=args.dataset, save_report=not args.no_report)


if __name__ == "__main__":
    main()
