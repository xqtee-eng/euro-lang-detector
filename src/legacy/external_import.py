import argparse
import bz2
import io
import tarfile
from pathlib import Path

from src.build_dataset import RAW_DATA_DIR
from src.european_languages import SUPPORTED_LANGUAGE_CODES

ISO3_TO_CODE = {
    "sqi": "sq",
    "alb": "sq",
    "hye": "hy",
    "arm": "hy",
    "aze": "az",
    "eus": "eu",
    "baq": "eu",
    "bel": "be",
    "bos": "bs",
    "bul": "bg",
    "cat": "ca",
    "hrv": "hr",
    "ces": "cs",
    "cze": "cs",
    "dan": "da",
    "nld": "nl",
    "dut": "nl",
    "eng": "en",
    "est": "et",
    "fin": "fi",
    "fra": "fr",
    "fre": "fr",
    "kat": "ka",
    "geo": "ka",
    "deu": "de",
    "ger": "de",
    "ell": "el",
    "gre": "el",
    "hun": "hu",
    "isl": "is",
    "ice": "is",
    "gle": "ga",
    "ita": "it",
    "lav": "lv",
    "lvs": "lv",
    "lit": "lt",
    "mkd": "mk",
    "mac": "mk",
    "nob": "nb",
    "nno": "nn",
    "pol": "pl",
    "por": "pt",
    "ron": "ro",
    "rum": "ro",
    "rus": "ru",
    "srp": "sr",
    "slk": "sk",
    "slo": "sk",
    "slv": "sl",
    "spa": "es",
    "swe": "sv",
    "tur": "tr",
    "ukr": "uk",
    "cym": "cy",
    "wel": "cy",
}


def _open_text(path):
    path = Path(path)
    if path.suffixes[-2:] in ([".tar", ".bz2"], [".tar", ".gz"], [".tar", ".xz"]) or path.suffix == ".tar":
        archive = tarfile.open(path, "r:*")
        for member in archive.getmembers():
            if member.isfile():
                extracted = archive.extractfile(member)
                if extracted:
                    return _ArchiveTextReader(archive, extracted)
        archive.close()
        raise ValueError(f"No regular file found in archive: {path}")
    if path.suffix == ".bz2":
        return bz2.open(path, "rt", encoding="utf-8", errors="ignore")
    return open(path, "r", encoding="utf-8", errors="ignore")


class _ArchiveTextReader:
    def __init__(self, archive, binary_handle):
        self.archive = archive
        self.text_handle = io.TextIOWrapper(binary_handle, encoding="utf-8", errors="ignore")

    def __enter__(self):
        return self.text_handle

    def __exit__(self, exc_type, exc, traceback):
        self.text_handle.close()
        self.archive.close()


def _clean_text(text):
    return " ".join(str(text or "").split())


def _read_existing(path):
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as handle:
        return [_clean_text(line) for line in handle if _clean_text(line)]


def _write_lines(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for line in lines:
            handle.write(line + "\n")


def import_tatoeba_sentences(input_path, output_dir=RAW_DATA_DIR, max_per_language=5000, min_length=12, mode="append"):
    output_dir = Path(output_dir)
    max_per_language = max(1, int(max_per_language or 5000))
    min_length = max(1, int(min_length or 12))
    mode = "replace" if mode == "replace" else "append"

    collected = {code: [] for code in SUPPORTED_LANGUAGE_CODES}
    seen = {code: set() for code in SUPPORTED_LANGUAGE_CODES}

    if mode == "append":
        for code in SUPPORTED_LANGUAGE_CODES:
            path = output_dir / f"{code}.txt"
            existing = _read_existing(path)
            collected[code].extend(existing)
            seen[code].update(existing)

    with _open_text(input_path) as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            iso3 = parts[1].strip().lower()
            code = ISO3_TO_CODE.get(iso3)
            if not code:
                continue
            text = _clean_text(parts[2])
            if len(text) < min_length or text in seen[code]:
                continue
            if len(collected[code]) >= max_per_language:
                continue
            collected[code].append(text)
            seen[code].add(text)

    imported = {}
    for code, lines in collected.items():
        if not lines:
            continue
        _write_lines(output_dir / f"{code}.txt", lines[:max_per_language])
        imported[code] = len(lines[:max_per_language])

    return {
        "input": str(input_path),
        "output_dir": str(output_dir),
        "mode": mode,
        "languages": len(imported),
        "rows": sum(imported.values()),
        "by_language": imported,
    }


def main():
    parser = argparse.ArgumentParser(description="Import real external corpora into data/raw/*.txt.")
    parser.add_argument("input", help="Tatoeba-style TSV or TSV.BZ2: sentence_id<TAB>iso3<TAB>text")
    parser.add_argument("--max-per-language", type=int, default=5000)
    parser.add_argument("--min-length", type=int, default=12)
    parser.add_argument("--mode", choices=["append", "replace"], default="append")
    args = parser.parse_args()

    print(
        import_tatoeba_sentences(
            args.input,
            max_per_language=args.max_per_language,
            min_length=args.min_length,
            mode=args.mode,
        )
    )


if __name__ == "__main__":
    main()
