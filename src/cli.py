import argparse
import json

from src.evaluate import evaluate
from src.hybrid import smart_detect, smart_detect_details


def main():
    parser = argparse.ArgumentParser(description="Euro Language Detector CLI")
    parser.add_argument("text", nargs="*", help="Text to detect")
    parser.add_argument(
        "--details", action="store_true", help="Show full detection details"
    )
    parser.add_argument("--evaluate", help="Evaluate a JSONL dataset")
    parser.add_argument(
        "--no-report", action="store_true", help="Do not save evaluation report"
    )

    args = parser.parse_args()

    if args.evaluate:
        evaluate(dataset_path=args.evaluate, save_report=not args.no_report)
        return

    text = " ".join(args.text).strip()

    if not text:
        parser.print_help()
        return

    if args.details:
        result = smart_detect_details(text)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(smart_detect(text))


if __name__ == "__main__":
    main()
