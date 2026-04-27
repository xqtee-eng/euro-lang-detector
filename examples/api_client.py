import argparse
import json
from urllib import request


def post_json(base_url, path, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        base_url.rstrip("/") + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def get_json(base_url, path):
    with request.urlopen(base_url.rstrip("/") + path, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Small REST client for the detector API.")
    parser.add_argument("text", nargs="?", default="Bonjour tout le monde")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    args = parser.parse_args()

    print("Detect:")
    print(json.dumps(post_json(args.base_url, "/detect", {"text": args.text, "top_k": 3}), ensure_ascii=False, indent=2))
    print("\nAnalyze:")
    print(json.dumps(post_json(args.base_url, "/analyze", {"text": args.text, "top_k": 3}), ensure_ascii=False, indent=2))
    print("\nSafety:")
    print(json.dumps(get_json(args.base_url, "/safety.json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
