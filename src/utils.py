import json
import re
from pathlib import Path

_LANG_PATTERN = re.compile(r'"lang"\s*:\s*"([^"]+)"')

def fast_count_lines(path):
    """Counts non-empty lines in a file using fast binary read."""
    path = Path(path)
    if not path.exists():
        return 0
    with open(path, "rb") as handle:
        return handle.read().count(b"\n")

def read_jsonl_gen(path):
    """Generator that yields parsed JSON objects from a JSONL file. Handles errors gracefully."""
    path = Path(path)
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # Fallback for partially corrupted lines
                yield {"text": line, "corrupted": True}

def write_jsonl(path, rows, mode="w"):
    """Writes a list or generator of rows to a JSONL file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, mode, encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

def fast_count_dataset_langs(path):
    """Counts language occurrences in a dataset JSONL using regex (extremely fast)."""
    from collections import Counter
    counts = Counter()
    path = Path(path)
    if not path.exists():
        return counts
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            m = _LANG_PATTERN.search(line)
            if m:
                counts[m.group(1).lower()] += 1
    return counts

def ensure_dir(path):
    """Ensures a directory exists."""
    Path(path).mkdir(parents=True, exist_ok=True)
