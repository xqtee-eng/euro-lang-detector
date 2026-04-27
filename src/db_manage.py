import argparse
import json

from src.storage import (
    export_jsonl_backup,
    import_jsonl_backup,
    init_db,
    storage_summary,
)


def main():
    parser = argparse.ArgumentParser(description="Manage SQLite storage.")
    parser.add_argument(
        "command",
        choices=("init", "import-jsonl", "export-jsonl", "stats"),
        help="Storage command to run.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force JSONL import even if it was already imported.",
    )
    args = parser.parse_args()

    if args.command == "init":
        init_db()
        result = storage_summary()
    elif args.command == "import-jsonl":
        result = import_jsonl_backup(force=args.force)
    elif args.command == "export-jsonl":
        result = export_jsonl_backup()
    else:
        result = storage_summary()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
