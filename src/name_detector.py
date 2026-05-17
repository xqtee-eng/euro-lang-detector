import json
from functools import lru_cache

from src.config import NAME_DIR
from src.rules import WORD_RE
from src.storage import list_name_rows, set_name_hint_enabled, upsert_name_hint

NAMES_STARTER_PATH = NAME_DIR.parent / "defaults" / "names_starter.json"

@lru_cache(maxsize=1)
def load_starter_names():
    if not NAMES_STARTER_PATH.exists():
        return {}
    try:
        with open(NAMES_STARTER_PATH, "r", encoding="utf-8") as h:
            return json.load(h)
    except:
        return {}

STARTER_NAMES = load_starter_names()

def _normalize_name(name):
    return str(name or "").strip().lower()

@lru_cache(maxsize=1)
def load_name_hints():
    """
    Loads all enabled name hints from the database.
    Single source of truth for name-based detection.
    """
    hints = {}
    rows = list_name_rows(enabled_only=True)
    for row in rows:
        name = row["name"]
        language = row["language"]
        hints.setdefault(name, []).append(
            {
                "language": language,
                "country": row.get("country", ""),
                "confidence": float(row.get("confidence", 0.9)),
                "name_type": row.get("name_type", "person"),
            }
        )
    return hints

def clear_name_cache():
    load_name_hints.cache_clear()

def list_name_hints(query="", language=None):
    query = _normalize_name(query)
    language = str(language or "").strip().lower()
    
    all_hints = load_name_hints()
    results = []
    for name, candidates in sorted(all_hints.items()):
        if query and query not in name:
            continue
        for candidate in sorted(candidates, key=lambda item: item["language"]):
            if language and candidate["language"] != language:
                continue
            results.append(
                {
                    "name": name,
                    "language": candidate["language"],
                    "country": candidate.get("country", ""),
                    "confidence": candidate.get("confidence", 0.0),
                    "name_type": candidate.get("name_type", "person"),
                }
            )
    return results

def add_name_hint(
    name, language, country="", confidence=0.9, name_type="person", notes=""
):
    name = _normalize_name(name)
    language = str(language or "").strip().lower()
    if not name or not language:
        raise ValueError("Name and language are required.")

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
        "confidence": round(float(confidence), 4),
        "name_type": name_type,
    }

def delete_name_hint(name, language):
    name = _normalize_name(name)
    language = str(language or "").strip().lower()
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
    top = candidates[0]
    
    return {
        "language": top["language"] if len(candidates) == 1 else "unknown",
        "confidence": max(c["confidence"] for c in candidates),
        "source": "name",
        "reason": "name_hint" if len(candidates) == 1 else "ambiguous_name",
        "entity_type": top["name_type"] if len(candidates) == 1 else "unknown_name",
        "name_candidates": candidates,
    }
