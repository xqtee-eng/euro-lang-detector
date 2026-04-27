import argparse
import sys
from collections import Counter
from pathlib import Path

# Add project root to sys.path for direct script execution
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.build_dataset import RAW_DATA_DIR
from src.config import FREQUENCY_DIR
from src.european_languages import SUPPORTED_LANGUAGE_CODES, get_language_name
from src.rules import WORD_RE
from src.storage import bulk_upsert_lexicon_words
from src.word_lexicon import clear_lexicon_cache


def normalize_word(word):
    return str(word or "").strip().lower()


def read_frequency_file(language):
    language = str(language or "").strip().lower()
    path = FREQUENCY_DIR / f"{language}.tsv"
    rows = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            word = normalize_word(parts[0])
            if not word:
                continue
            try:
                frequency = int(parts[1]) if len(parts) > 1 else 1
            except ValueError:
                frequency = 1
            rows.append({"word": word, "frequency": max(1, frequency)})
    return rows


def list_frequency_files():
    FREQUENCY_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for language in SUPPORTED_LANGUAGE_CODES:
        path = FREQUENCY_DIR / f"{language}.tsv"
        entries = read_frequency_file(language)
        rows.append(
            {
                "language": language,
                "name": get_language_name(language),
                "path": str(path),
                "exists": path.exists(),
                "entries": len(entries),
                "total_frequency": sum(item["frequency"] for item in entries),
            }
        )
    return rows


def _tokens_from_raw_file(path):
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            for match in WORD_RE.finditer(line.lower()):
                token = normalize_word(match.group(0))
                if len(token) >= 2:
                    yield token


def generate_frequency_lists(max_words_per_language=1000):
    FREQUENCY_DIR.mkdir(parents=True, exist_ok=True)
    created = 0
    total_entries = 0
    for language in SUPPORTED_LANGUAGE_CODES:
        raw_path = RAW_DATA_DIR / f"{language}.txt"
        if not raw_path.exists():
            continue
        counts = Counter(_tokens_from_raw_file(raw_path))
        rows = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        rows = rows[: max(1, int(max_words_per_language or 1000))]
        path = FREQUENCY_DIR / f"{language}.tsv"
        with open(path, "w", encoding="utf-8") as handle:
            for word, frequency in rows:
                handle.write(f"{word}\t{frequency}\n")
        created += 1
        total_entries += len(rows)
    return {"files": created, "entries": total_entries, "directory": str(FREQUENCY_DIR)}


def save_frequency_text(language, text, mode="replace"):
    language = str(language or "").strip().lower()
    if language not in SUPPORTED_LANGUAGE_CODES:
        raise ValueError(f"Unsupported language code: {language}")

    parsed = []
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.replace(",", "\t", 1).split("\t")
        word = normalize_word(parts[0])
        if not word:
            continue
        try:
            frequency = int(parts[1]) if len(parts) > 1 and parts[1].strip() else 1
        except ValueError:
            frequency = 1
        parsed.append((word, max(1, frequency)))

    if not parsed:
        raise ValueError("No valid frequency rows found. Use: word<TAB>frequency")

    FREQUENCY_DIR.mkdir(parents=True, exist_ok=True)
    path = FREQUENCY_DIR / f"{language}.tsv"
    existing = []
    if mode == "append" and path.exists():
        existing = [(row["word"], row["frequency"]) for row in read_frequency_file(language)]

    merged = {}
    for word, frequency in existing + parsed:
        merged[word] = max(merged.get(word, 0), frequency)

    rows = sorted(merged.items(), key=lambda item: (-item[1], item[0]))
    with open(path, "w", encoding="utf-8") as handle:
        for word, frequency in rows:
            handle.write(f"{word}\t{frequency}\n")

    return {
        "language": language,
        "path": str(path),
        "mode": "append" if mode == "append" else "replace",
        "imported_rows": len(parsed),
        "total_rows": len(rows),
    }


def import_frequency_lists(limit_per_language=1000):
    languages = 0
    rows_to_import = []
    for language in SUPPORTED_LANGUAGE_CODES:
        rows = read_frequency_file(language)
        if not rows:
            continue
        languages += 1
        for row in rows[: max(1, int(limit_per_language or 1000))]:
            rows_to_import.append(
                {
                    "language": language,
                    "word": row["word"],
                    "enabled": True,
                    "source": "frequency",
                    "frequency": row["frequency"],
                    "notes": "Imported from data/frequency TSV.",
                }
            )
    imported = bulk_upsert_lexicon_words(rows_to_import)
    clear_lexicon_cache()
    return {"languages": languages, "imported": imported, "directory": str(FREQUENCY_DIR)}


def main():
    parser = argparse.ArgumentParser(description="Generate and import word frequency lists.")
    parser.add_argument("--generate", action="store_true", help="Generate data/frequency/*.tsv from data/raw/*.txt.")
    parser.add_argument("--import-lexicon", action="store_true", help="Import frequency lists into SQLite lexicon_words.")
    parser.add_argument("--max-words-per-language", type=int, default=1000)
    parser.add_argument("--limit-per-language", type=int, default=1000)
    args = parser.parse_args()

    if args.generate or not args.import_lexicon:
        print(generate_frequency_lists(max_words_per_language=args.max_words_per_language))
    if args.import_lexicon:
        print(import_frequency_lists(limit_per_language=args.limit_per_language))


if __name__ == "__main__":
    main()
