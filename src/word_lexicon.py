import json
from functools import lru_cache

from src.config import LEXICON_DIR
from src.rules import WORD_RE
from src.storage import list_lexicon_rows, set_lexicon_word_enabled, upsert_lexicon_word, connect

LEXICON_STARTER_PATH = LEXICON_DIR.parent / "defaults" / "lexicon_starter.json"

@lru_cache(maxsize=1)
def load_starter_words():
    if not LEXICON_STARTER_PATH.exists():
        return {}
    try:
        with open(LEXICON_STARTER_PATH, "r", encoding="utf-8") as h:
            data = json.load(h)
            return {lang: set(words) for lang, words in data.items()}
    except (OSError, json.JSONDecodeError):
        return {}

STARTER_WORDS = load_starter_words()

def _normalize_word(word):
    return str(word or "").strip().lower()

@lru_cache(maxsize=1)
def load_lexicons():
    """
    Loads all enabled lexicon words from the database.
    This is the single source of truth for the detector.
    """
    index = {}
    # Fetch all enabled words from DB
    rows = list_lexicon_rows(enabled_only=True)
    for row in rows:
        word = row["word"]
        language = row["language"]
        index.setdefault(word, set()).add(language)
    
    # Optional: If DB is empty, we could fallback to STARTER_WORDS, 
    # but it's better to force a Seed/Import.
    return index

def clear_lexicon_cache():
    load_lexicons.cache_clear()

def list_lexicon_words(query="", language=None):
    query = _normalize_word(query)
    language = str(language or "").strip().lower()
    words_by_language = {}
    index = load_lexicons()
    for word, languages in index.items():
        if query and query not in word:
            continue
        for item_language in languages:
            if language and item_language != language:
                continue
            words_by_language.setdefault(item_language, set()).add(word)

    return {
        item_language: sorted(words)
        for item_language, words in sorted(words_by_language.items())
    }

def list_lexicon_entries(query="", language=None):
    query = _normalize_word(query)
    language = str(language or "").strip().lower()
    
    rows = list_lexicon_rows(
        query=query, language=language or None, enabled_only=True
    )
    
    entries = []
    for row in rows:
        entries.append({
            "word": row["word"],
            "language": row["language"],
            "frequency": row.get("frequency", 1),
            "source": row.get("source", "db"),
            "notes": row.get("notes", ""),
            "ambiguous": False, # Could be determined by checking index
        })
    return entries

def analyze_word_knowledge(word):
    value = _normalize_word(word)
    if not value:
        return {"word": "", "known": False, "ambiguous": False, "languages": [], "entries": []}
    
    index = load_lexicons()
    languages = sorted(list(index.get(value, [])))
    
    entries = []
    if languages:
        with connect() as db:
            rows = db.execute(
                "SELECT language, frequency, source, enabled FROM lexicon_words WHERE word = ?",
                (value,)
            ).fetchall()
            for row in rows:
                entries.append({
                    "language": row["language"],
                    "frequency": row["frequency"],
                    "source": row["source"],
                    "enabled": bool(row["enabled"])
                })
    
    return {
        "word": value,
        "known": bool(languages),
        "ambiguous": len(languages) > 1,
        "languages": languages,
        "entries": entries,
    }

def detect_word(text):
    value = _normalize_word(text)
    words = WORD_RE.findall(value)
    if not words:
        return None

    index = load_lexicons()
    scores = {}
    for word in words:
        langs = index.get(word, [])
        for lang in langs:
            scores[lang] = scores.get(lang, 0) + 1
    
    if not scores:
        return None
        
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_lang, top_score = sorted_scores[0]
    ambiguous_top_score = (
        len(sorted_scores) > 1 and sorted_scores[0][1] == sorted_scores[1][1]
    )

    if ambiguous_top_score and len(words) > 1:
        return None
    
    return {
        "language": "unknown" if ambiguous_top_score else top_lang,
        "confidence": (
            0.0 if ambiguous_top_score else min(0.99, 0.4 + (top_score * 0.1))
        ),
        "source": "lexicon",
        "reason": "ambiguous_word" if ambiguous_top_score else f"matched_{top_score}_words",
        "entity_type": "word",
        "scores": scores
    }

def add_lexicon_word(language, word, frequency=1, notes=""):
    language = str(language or "").strip().lower()
    word = _normalize_word(word)
    if not language or not word:
        raise ValueError("Language and word are required.")

    upsert_lexicon_word(
        language,
        word,
        enabled=True,
        source="user",
        frequency=frequency,
        notes=notes,
    )
    clear_lexicon_cache()
    return {
        "language": language,
        "word": word,
        "frequency": max(1, int(frequency or 1)),
    }

def delete_lexicon_word(language, word):
    language = str(language or "").strip().lower()
    word = _normalize_word(word)
    set_lexicon_word_enabled(language, word, enabled=False)
    clear_lexicon_cache()
    return {"language": language, "word": word}

def import_lexicon_words(language, words_text):
    words = [
        _normalize_word(match.group(0))
        for match in WORD_RE.finditer(words_text)
        if _normalize_word(match.group(0))
    ]
    unique_words = sorted(list(set(words)))
    
    from src.storage import bulk_upsert_lexicon_words
    rows = [{"language": language, "word": w, "source": "import"} for w in unique_words]
    bulk_upsert_lexicon_words(rows)
    
    clear_lexicon_cache()
    return [{"word": w, "language": language} for w in unique_words]
