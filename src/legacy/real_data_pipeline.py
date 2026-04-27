import argparse
import json
from collections import Counter
from pathlib import Path

from src.benchmark import run_benchmark
from src.build_dataset import RAW_DATA_DIR, build_dataset
from src.config import BENCHMARK_PATH, DATA_DIR, FREQUENCY_DIR
from src.evaluate import evaluate
from src.external_import import ISO3_TO_CODE, _clean_text, _open_text
from src.frequency import import_frequency_lists
from src.european_languages import SUPPORTED_LANGUAGE_CODES, get_language_name
from src.rules import WORD_RE
from src.train import train
from src.utils import ensure_dir, write_jsonl


REAL_DATA_REPORT_PATH = DATA_DIR / "real_data_report.json"


def _read_existing_lines(path):
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as handle:
        return [_clean_text(line) for line in handle if _clean_text(line)]


def _write_txt(path, lines):
    ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8") as handle:
        for line in lines:
            handle.write(line + "\n")


def _write_json(path, payload):
    ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _tokenize(text):
    for match in WORD_RE.finditer(text.lower()):
        token = match.group(0).strip("'_-").lower()
        if len(token) >= 2 and not token.isdigit():
            yield token


def _write_benchmark(rows, path=BENCHMARK_PATH):
    write_jsonl(path, rows)


def _write_frequency_files(counters, max_words_per_language):
    return write_frequency_files(counters, FREQUENCY_DIR, max_words_per_language)


def write_frequency_files(counters, frequency_dir, max_words_per_language):
    frequency_dir = Path(frequency_dir)
    frequency_dir.mkdir(parents=True, exist_ok=True)
    summary = {}
    for language in SUPPORTED_LANGUAGE_CODES:
        counter = counters[language]
        rows = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
        rows = rows[:max_words_per_language]
        path = frequency_dir / f"{language}.tsv"
        with open(path, "w", encoding="utf-8") as handle:
            for word, frequency in rows:
                handle.write(f"{word}\t{frequency}\n")
        summary[language] = len(rows)
    return summary


def _targets_met(raw_lines, benchmark_lines, frequency_source_counts, args):
    for language in SUPPORTED_LANGUAGE_CODES:
        if len(raw_lines[language]) < args.raw_per_language:
            return False
        if len(benchmark_lines[language]) < args.benchmark_per_language:
            return False
        if frequency_source_counts[language] < args.frequency_source_per_language:
            return False
    return True


def build_real_data_resources(
    input_path,
    raw_per_language=1000,
    benchmark_per_language=15,
    frequency_words_per_language=2000,
    frequency_source_per_language=10000,
    min_length=20,
    mode="append",
    run_model_steps=False,
    raw_dir=RAW_DATA_DIR,
    benchmark_path=BENCHMARK_PATH,
    frequency_dir=FREQUENCY_DIR,
    report_path=REAL_DATA_REPORT_PATH,
):
    input_path = Path(input_path)
    raw_dir = Path(raw_dir)
    benchmark_path = Path(benchmark_path)
    frequency_dir = Path(frequency_dir)
    report_path = Path(report_path)
    raw_per_language = max(1, int(raw_per_language))
    benchmark_per_language = max(1, int(benchmark_per_language))
    frequency_words_per_language = max(1, int(frequency_words_per_language))
    frequency_source_per_language = max(raw_per_language, int(frequency_source_per_language))
    min_length = max(1, int(min_length))
    mode = "replace" if mode == "replace" else "append"

    raw_lines = {language: [] for language in SUPPORTED_LANGUAGE_CODES}
    raw_seen = {language: set() for language in SUPPORTED_LANGUAGE_CODES}
    benchmark_lines = {language: [] for language in SUPPORTED_LANGUAGE_CODES}
    benchmark_seen = {language: set() for language in SUPPORTED_LANGUAGE_CODES}
    frequency_counters = {language: Counter() for language in SUPPORTED_LANGUAGE_CODES}
    frequency_source_counts = {language: 0 for language in SUPPORTED_LANGUAGE_CODES}

    if mode == "append":
        for language in SUPPORTED_LANGUAGE_CODES:
            existing = _read_existing_lines(raw_dir / f"{language}.txt")
            raw_lines[language].extend(existing[:raw_per_language])
            raw_seen[language].update(existing)
            for text in existing:
                for token in _tokenize(text):
                    frequency_counters[language][token] += 1
                frequency_source_counts[language] += 1

    total_lines = 0
    used_lines = 0

    class Args:
        pass

    args = Args()
    args.raw_per_language = raw_per_language
    args.benchmark_per_language = benchmark_per_language
    args.frequency_source_per_language = frequency_source_per_language

    with _open_text(input_path) as handle:
        for line in handle:
            total_lines += 1
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue

            language = ISO3_TO_CODE.get(parts[1].strip().lower())
            if language not in raw_lines:
                continue

            text = _clean_text(parts[2])
            if len(text) < min_length:
                continue

            if len(benchmark_lines[language]) < benchmark_per_language and text not in benchmark_seen[language]:
                benchmark_lines[language].append(text)
                benchmark_seen[language].add(text)
                used_lines += 1
                continue

            if text in benchmark_seen[language]:
                continue

            if len(raw_lines[language]) < raw_per_language and text not in raw_seen[language]:
                raw_lines[language].append(text)
                raw_seen[language].add(text)
                used_lines += 1

            if frequency_source_counts[language] < frequency_source_per_language:
                for token in _tokenize(text):
                    frequency_counters[language][token] += 1
                frequency_source_counts[language] += 1

            if total_lines % 500000 == 0 and _targets_met(raw_lines, benchmark_lines, frequency_source_counts, args):
                break

    for language, lines in raw_lines.items():
        _write_txt(raw_dir / f"{language}.txt", lines[:raw_per_language])

    benchmark_rows = []
    for language in SUPPORTED_LANGUAGE_CODES:
        for text in benchmark_lines[language]:
            benchmark_rows.append(
                {
                    "text": text,
                    "expected": language,
                    "category": "tatoeba_independent",
                    "source": "tatoeba",
                }
            )
    _write_benchmark(benchmark_rows, path=benchmark_path)

    frequency_summary = write_frequency_files(frequency_counters, frequency_dir, frequency_words_per_language)

    report = {
        "input": str(input_path),
        "mode": mode,
        "total_lines_scanned": total_lines,
        "used_lines": used_lines,
        "raw_per_language_target": raw_per_language,
        "benchmark_per_language_target": benchmark_per_language,
        "frequency_words_per_language_target": frequency_words_per_language,
        "languages": len(SUPPORTED_LANGUAGE_CODES),
        "raw": {
            language: {
                "name": get_language_name(language),
                "rows": len(raw_lines[language][:raw_per_language]),
            }
            for language in SUPPORTED_LANGUAGE_CODES
        },
        "benchmark": {
            "path": str(benchmark_path),
            "rows": len(benchmark_rows),
            "by_language": {language: len(benchmark_lines[language]) for language in SUPPORTED_LANGUAGE_CODES},
        },
        "frequency": {
            "directory": str(frequency_dir),
            "by_language": frequency_summary,
        },
    }

    if run_model_steps:
        build_dataset(max_samples_per_language=raw_per_language)
        train()
        evaluate()
        report["benchmark_result"] = run_benchmark()
        report["lexicon_import"] = import_frequency_lists(limit_per_language=frequency_words_per_language)

    _write_json(report_path, report)
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Build real raw corpora, independent benchmark, and frequency TSV files from Tatoeba sentences."
    )
    parser.add_argument("input", help="Path to Tatoeba sentences TSV, .bz2, or .tar.bz2")
    parser.add_argument("--raw-per-language", type=int, default=1000)
    parser.add_argument("--benchmark-per-language", type=int, default=15)
    parser.add_argument("--frequency-words-per-language", type=int, default=2000)
    parser.add_argument("--frequency-source-per-language", type=int, default=10000)
    parser.add_argument("--min-length", type=int, default=20)
    parser.add_argument("--mode", choices=["append", "replace"], default="append")
    parser.add_argument("--run-model-steps", action="store_true")
    args = parser.parse_args()

    report = build_real_data_resources(
        args.input,
        raw_per_language=args.raw_per_language,
        benchmark_per_language=args.benchmark_per_language,
        frequency_words_per_language=args.frequency_words_per_language,
        frequency_source_per_language=args.frequency_source_per_language,
        min_length=args.min_length,
        mode=args.mode,
        run_model_steps=args.run_model_steps,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
