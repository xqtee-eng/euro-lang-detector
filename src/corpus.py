from src.build_dataset import RAW_DATA_DIR, build_dataset
from src.close_language_pack import apply_close_language_pack
from src.config import CLOSE_PACK_DIR, DATASET_PATH, TEST_DATASET_PATH, TRAIN_DATASET_PATH
from src.european_languages import SUPPORTED_LANGUAGE_CODES, get_language_name
from src.utils import ensure_dir, fast_count_lines


def dataset_stats():
    return {
        "dataset_rows": fast_count_lines(DATASET_PATH),
        "train_rows": fast_count_lines(TRAIN_DATASET_PATH),
        "test_rows": fast_count_lines(TEST_DATASET_PATH),
        "close_pack_dir": str(CLOSE_PACK_DIR),
        "dataset_path": str(DATASET_PATH),
        "train_path": str(TRAIN_DATASET_PATH),
        "test_path": str(TEST_DATASET_PATH),
    }


def list_corpus_files():
    ensure_dir(RAW_DATA_DIR)
    rows = []
    for language in SUPPORTED_LANGUAGE_CODES:
        path = RAW_DATA_DIR / f"{language}.txt"
        count = fast_count_lines(path)
        rows.append(
            {
                "language": language,
                "name": get_language_name(language),
                "path": str(path),
                "exists": path.exists(),
                "size": path.stat().st_size if path.exists() else 0,
                "modified_at": path.stat().st_mtime if path.exists() else None,
                "lines": count,
                "non_empty_lines": count,
            }
        )
    return rows


def save_corpus_text(language, text, mode="append"):
    language = str(language or "").strip().lower()
    if language not in SUPPORTED_LANGUAGE_CODES:
        raise ValueError(f"Unsupported language code: {language}")

    cleaned_lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not cleaned_lines:
        raise ValueError("Text file has no reviewed non-empty lines.")

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DATA_DIR / f"{language}.txt"
    mode = "replace" if mode == "replace" else "append"
    previous = []
    if mode == "append" and path.exists():
        with open(path, "r", encoding="utf-8") as handle:
            previous = [line.strip() for line in handle if line.strip()]

    merged = list(dict.fromkeys(previous + cleaned_lines))
    with open(path, "w", encoding="utf-8") as handle:
        for line in merged:
            handle.write(line + "\n")

    return {
        "language": language,
        "path": str(path),
        "mode": mode,
        "added_lines": len(cleaned_lines),
        "total_lines": len(merged),
    }


def rebuild_corpus_dataset(max_samples_per_language=5000, test_ratio=0.2, seed=42):
    rows = build_dataset(
        max_samples_per_language=max(1, int(max_samples_per_language or 5000)),
        test_ratio=max(0.0, min(0.8, float(test_ratio or 0.2))),
        seed=int(seed or 42),
    )
    return {"built_rows": len(rows), **dataset_stats()}


def apply_curated_close_language_pack(mode="append", languages=None):
    result = apply_close_language_pack(mode=mode, output_dir=CLOSE_PACK_DIR, languages=languages)
    return {**result, **dataset_stats()}


def preview_corpus_file(language, limit=20):
    language = str(language or "").strip().lower()
    if language not in SUPPORTED_LANGUAGE_CODES:
        raise ValueError(f"Unsupported language code: {language}")
    path = RAW_DATA_DIR / f"{language}.txt"
    if not path.exists():
        return {"language": language, "path": str(path), "lines": []}
    lines = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            value = line.strip()
            if value:
                lines.append(value)
            if len(lines) >= limit:
                break
    return {"language": language, "path": str(path), "lines": lines}
