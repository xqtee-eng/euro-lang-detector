import argparse
import random
from pathlib import Path

from src.config import (
    CLOSE_PACK_DIR,
    DATA_DIR,
    DATASET_PATH,
    TEST_DATASET_PATH,
    TRAIN_DATASET_PATH,
)
from src.european_languages import SUPPORTED_LANGUAGE_CODES

RAW_DATA_DIR = DATA_DIR / "raw"


def load_txt(path, min_length=10):
    with open(path, "r", encoding="utf-8") as handle:
        return [line.strip() for line in handle if len(line.strip()) >= min_length]


from src.utils import write_jsonl


def _sample_rows_from_dir(
    directory, max_samples_per_language, rng, min_length=10, source="raw"
):
    rows = []
    if not Path(directory).exists():
        return rows

    for path in sorted(Path(directory).glob("*.txt")):
        language = path.stem.lower()
        if language not in SUPPORTED_LANGUAGE_CODES:
            continue

        texts = load_txt(path, min_length=min_length)
        if not texts:
            continue

        sample_size = min(max_samples_per_language, len(texts))
        for text in rng.sample(texts, sample_size):
            rows.append({"text": text, "lang": language, "source": source})
    return rows


def split_rows(rows, test_ratio=0.2, seed=42):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["lang"], []).append(row)

    train_rows = []
    test_rows = []
    rng = random.Random(seed)
    for language, language_rows in sorted(grouped.items()):
        rng.shuffle(language_rows)
        if len(language_rows) <= 1:
            train_rows.extend(language_rows)
            continue

        test_size = max(1, round(len(language_rows) * test_ratio))
        test_size = min(test_size, len(language_rows) - 1)
        test_rows.extend(language_rows[:test_size])
        train_rows.extend(language_rows[test_size:])

    rng.shuffle(train_rows)
    rng.shuffle(test_rows)
    return train_rows, test_rows


def build_dataset(max_samples_per_language=5000, test_ratio=0.2, seed=42):
    if not RAW_DATA_DIR.exists():
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Created raw data directory: {RAW_DATA_DIR}")
        print(
            "Add reviewed files like data/raw/uk.txt, data/raw/fr.txt, data/raw/de.txt and run again."
        )
        return []

    rng = random.Random(seed)
    base_rows = _sample_rows_from_dir(
        RAW_DATA_DIR, max_samples_per_language, rng, source="raw"
    )
    train_only_rows = _sample_rows_from_dir(
        CLOSE_PACK_DIR, max_samples_per_language, rng, source="close_pack"
    )
    rng.shuffle(base_rows)

    if not base_rows:
        print(f"No reviewed rows found in {RAW_DATA_DIR}.")
        print("Dataset was not changed.")
        print(
            "Add files like data/raw/uk.txt, data/raw/fr.txt, data/raw/de.txt and run again."
        )
        return []

    train_rows, test_rows = split_rows(base_rows, test_ratio=test_ratio, seed=seed)
    train_rows.extend(train_only_rows)
    rng.shuffle(train_rows)
    output_rows = list(base_rows) + list(train_only_rows)

    write_jsonl(DATASET_PATH, output_rows)
    write_jsonl(TRAIN_DATASET_PATH, train_rows)
    write_jsonl(TEST_DATASET_PATH, test_rows)

    print(f"Dataset built: {len(output_rows)} rows")
    if train_only_rows:
        print(f"Train-only close-pack rows: {len(train_only_rows)}")
    print(f"Train split: {len(train_rows)} rows -> {TRAIN_DATASET_PATH}")
    print(f"Test split: {len(test_rows)} rows -> {TEST_DATASET_PATH}")
    return output_rows


def main():
    parser = argparse.ArgumentParser(
        description="Build reviewed dataset and train/test split."
    )
    parser.add_argument("--max-samples-per-language", type=int, default=5000)
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    build_dataset(
        max_samples_per_language=max(1, args.max_samples_per_language),
        test_ratio=max(0.0, min(0.8, args.test_ratio)),
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
