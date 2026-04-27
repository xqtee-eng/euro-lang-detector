import argparse
import json
import sys

from src.hybrid import smart_detect, smart_detect_details


def configure_console_encoding():
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except ValueError:
                pass


def main():
    configure_console_encoding()
    parser = argparse.ArgumentParser(description="Detect European languages.")
    parser.add_argument("text", nargs="*", help="Text to classify")
    parser.add_argument("--details", action="store_true", help="Print structured details")
    parser.add_argument("--top-k", type=int, default=3, help="Number of candidates to return")
    args = parser.parse_args()

    top_k = max(1, min(args.top_k, 10))

    if args.text:
        text = " ".join(args.text)
        result = smart_detect_details(text, top_k=top_k)
        if args.details:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(result["language"])
        return

    while True:
        text = input("Text (empty to exit): ").strip()
        if not text:
            break

        if args.details:
            print(
                json.dumps(
                    smart_detect_details(text, top_k=top_k),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print("Detected:", smart_detect(text))


if __name__ == "__main__":
    main()
