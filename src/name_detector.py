import json
from functools import lru_cache

from src.config import NAME_DIR
from src.rules import WORD_RE
from src.storage import list_name_rows, set_name_hint_enabled, upsert_name_hint

DISABLED_PATH = NAME_DIR / "_disabled.jsonl"

STARTER_NAMES = {
    "анастасія": [
        {"language": "uk", "country": "Ukraine", "confidence": 0.55},
        {"language": "be", "country": "Belarus", "confidence": 0.45},
    ],
    "настасія": [
        {"language": "uk", "country": "Ukraine", "confidence": 0.55},
        {"language": "be", "country": "Belarus", "confidence": 0.45},
    ],
    "іван": [
        {"language": "uk", "country": "Ukraine", "confidence": 0.7},
        {"language": "be", "country": "Belarus", "confidence": 0.3},
    ],
    "иван": [
        {"language": "ru", "country": "Russia", "confidence": 0.5},
        {"language": "bg", "country": "Bulgaria", "confidence": 0.3},
        {"language": "sr", "country": "Serbia", "confidence": 0.2},
    ],
    "георгій": [
        {"language": "uk", "country": "Ukraine", "confidence": 0.75},
        {"language": "be", "country": "Belarus", "confidence": 0.25},
    ],
    "георгий": [
        {"language": "ru", "country": "Russia", "confidence": 0.7},
        {"language": "bg", "country": "Bulgaria", "confidence": 0.3},
    ],
    "остап": [
        {"language": "uk", "country": "Ukraine", "confidence": 0.95},
    ],
    "тарас": [
        {"language": "uk", "country": "Ukraine", "confidence": 0.95},
    ],
    "оксана": [
        {"language": "uk", "country": "Ukraine", "confidence": 0.8},
        {"language": "ru", "country": "Russia", "confidence": 0.2},
    ],
    "олександр": [
        {"language": "uk", "country": "Ukraine", "confidence": 0.95},
    ],
    "александр": [
        {"language": "ru", "country": "Russia", "confidence": 0.8},
        {"language": "bg", "country": "Bulgaria", "confidence": 0.2},
    ],
    "марія": [
        {"language": "uk", "country": "Ukraine", "confidence": 0.55},
        {"language": "be", "country": "Belarus", "confidence": 0.45},
    ],
}


def _normalize_name(name):
    return str(name or "").strip().lower()


def _hint_key(name, language):
    return (language, _normalize_name(name))


def _read_disabled():
    if not DISABLED_PATH.exists():
        return set()

    disabled = set()
    with open(DISABLED_PATH, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            language = str(row.get("language", "")).strip().lower()
            name = _normalize_name(row.get("name", ""))
            if language and name:
                disabled.add((language, name))
    return disabled


def _write_disabled(disabled):
    NAME_DIR.mkdir(parents=True, exist_ok=True)
    with open(DISABLED_PATH, "w", encoding="utf-8") as handle:
        for language, name in sorted(disabled):
            handle.write(json.dumps({"language": language, "name": name}, ensure_ascii=False) + "\n")


def _read_user_hints():
    hints = {}
    if not NAME_DIR.exists():
        return hints

    for path in NAME_DIR.glob("*.jsonl"):
        if path.name.startswith("_"):
            continue
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                name = _normalize_name(row.get("name", ""))
                language = str(row.get("language", path.stem)).strip().lower()
                if not name or not language:
                    continue
                hints.setdefault(name, []).append(
                    {
                        "language": language,
                        "country": str(row.get("country", "")).strip(),
                        "confidence": float(row.get("confidence", 0.9)),
                    }
                )
    return hints


def _write_user_hints(hints):
    NAME_DIR.mkdir(parents=True, exist_ok=True)
    by_language = {}
    for name, candidates in hints.items():
        for candidate in candidates:
            language = candidate["language"]
            by_language.setdefault(language, []).append(
                {
                    "name": name,
                    "language": language,
                    "country": candidate.get("country", ""),
                    "confidence": candidate.get("confidence", 0.9),
                }
            )

    for path in NAME_DIR.glob("*.jsonl"):
        if not path.name.startswith("_"):
            path.unlink()

    for language, rows in by_language.items():
        with open(NAME_DIR / f"{language}.jsonl", "w", encoding="utf-8") as handle:
            for row in sorted(rows, key=lambda item: item["name"]):
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")


@lru_cache(maxsize=1)
def load_name_hints():
    disabled = _read_disabled()
    hints = {}

    for name, candidates in STARTER_NAMES.items():
        for candidate in candidates:
            language = candidate["language"]
            if (language, name) in disabled:
                continue
            hints.setdefault(name, []).append(dict(candidate))

    for name, candidates in _read_user_hints().items():
        for candidate in candidates:
            language = candidate["language"]
            if (language, name) in disabled:
                continue
            hints.setdefault(name, [])
            hints[name] = [
                item for item in hints[name] if item["language"] != language
            ]
            hints[name].append(candidate)

    for row in list_name_rows(enabled_only=False):
        name = row["name"]
        language = row["language"]
        if row["enabled"]:
            hints.setdefault(name, [])
            hints[name] = [
                item for item in hints[name] if item["language"] != language
            ]
            hints[name].append(
                {
                    "language": language,
                    "country": row.get("country", ""),
                    "confidence": float(row.get("confidence", 0.9)),
                    "name_type": row.get("name_type", "person"),
                }
            )
        elif name in hints:
            hints[name] = [
                item for item in hints[name] if item["language"] != language
            ]
            if not hints[name]:
                del hints[name]

    return hints


def clear_name_cache():
    load_name_hints.cache_clear()


def list_name_hints(query="", language=None):
    query = _normalize_name(query)
    language = str(language or "").strip().lower()
    rows = []
    for name, candidates in sorted(load_name_hints().items()):
        if query and query not in name:
            continue
        for candidate in sorted(candidates, key=lambda item: item["language"]):
            if language and candidate["language"] != language:
                continue
            rows.append(
                {
                    "name": name,
                    "language": candidate["language"],
                    "country": candidate.get("country", ""),
                    "confidence": candidate.get("confidence", 0.0),
                    "name_type": candidate.get("name_type", "person"),
                }
            )
    return rows


def add_name_hint(name, language, country="", confidence=0.9, name_type="person", notes=""):
    name = _normalize_name(name)
    language = str(language or "").strip().lower()
    country = str(country or "").strip()
    name_type = str(name_type or "person").strip().lower() or "person"
    confidence = max(0.01, min(1.0, float(confidence or 0.9)))
    if not name or not language:
        raise ValueError("Name and language are required.")

    user_hints = _read_user_hints()
    candidates = [
        candidate
        for candidate in user_hints.get(name, [])
        if candidate["language"] != language
    ]
    candidates.append(
        {
            "language": language,
            "country": country,
            "confidence": round(confidence, 4),
            "name_type": name_type,
        }
    )
    user_hints[name] = candidates
    _write_user_hints(user_hints)

    disabled = _read_disabled()
    disabled.discard((language, name))
    _write_disabled(disabled)
    upsert_name_hint(
        name,
        language,
        country=country,
        confidence=confidence,
        enabled=True,
        source="user",
        name_type=name_type,
        notes=notes,
    )
    clear_name_cache()
    return {
        "name": name,
        "language": language,
        "country": country,
        "confidence": round(confidence, 4),
        "name_type": name_type,
    }


def delete_name_hint(name, language):
    name = _normalize_name(name)
    language = str(language or "").strip().lower()
    if not name or not language:
        raise ValueError("Name and language are required.")

    user_hints = _read_user_hints()
    if name in user_hints:
        user_hints[name] = [
            candidate
            for candidate in user_hints[name]
            if candidate["language"] != language
        ]
        if not user_hints[name]:
            del user_hints[name]
        _write_user_hints(user_hints)

    disabled = _read_disabled()
    disabled.add((language, name))
    _write_disabled(disabled)
    set_name_hint_enabled(name, language, enabled=False)
    clear_name_cache()
    return {"name": name, "language": language}


def detect_name(text):
    value = _normalize_name(text)
    words = WORD_RE.findall(value)
    if len(words) != 1:
        return None

    candidates = load_name_hints().get(words[0])
    if not candidates:
        return None

    candidates = sorted(candidates, key=lambda item: item["confidence"], reverse=True)
    if len(candidates) == 1:
        candidate = candidates[0]
        return {
            "language": candidate["language"],
            "confidence": candidate["confidence"],
            "source": "name",
            "reason": "name_hint",
            "entity_type": "person_name",
            "name_candidates": candidates,
            "candidates": [
                {
                    "language": candidate["language"],
                    "confidence": candidate["confidence"],
                }
            ],
        }

    return {
        "language": "unknown",
        "confidence": max(candidate["confidence"] for candidate in candidates),
        "source": "name",
        "reason": "ambiguous_name",
        "entity_type": "person_name",
        "name_candidates": candidates,
        "candidates": [
            {
                "language": candidate["language"],
                "confidence": candidate["confidence"],
            }
            for candidate in candidates
        ],
    }
