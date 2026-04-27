import json
from functools import lru_cache

from src.config import LEXICON_DIR
from src.rules import WORD_RE
from src.storage import list_lexicon_rows, set_lexicon_word_enabled, upsert_lexicon_word

DISABLED_PATH = LEXICON_DIR / "_disabled.jsonl"

STARTER_WORDS = {
    "en": {"hello", "friend", "dog", "cat", "house", "world", "language", "word"},
    "uk": {
        "привіт",
        "світ",
        "мова",
        "слово",
        "речення",
        "абетки",
        "козак",
        "коза",
        "собака",
        "паляниця",
    },
    "be": {
        "добры",
        "дзень",
        "мова",
        "слова",
        "гэта",
        "беларускай",
        "вызначэння",
        "коза",
    },
    "ru": {"привет", "мир", "язык", "слово", "предложение", "собака", "коза"},
    "pl": {"dzien", "dzień", "slowo", "słowo", "jezyk", "język"},
    "fr": {"bonjour", "merci", "monde", "langue", "mot"},
    "de": {"hallo", "danke", "sprache", "wort"},
    "it": {"ciao", "grazie", "lingua", "parola"},
    "es": {"hola", "gracias", "idioma", "palabra"},
    "pt": {"ola", "olá", "obrigado", "idioma", "palavra"},
    "tr": {"merhaba", "dil", "kelime"},
}


def _normalize_word(word):
    return str(word or "").strip().lower()


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
            language = str(row.get("lang", "")).strip().lower()
            word = _normalize_word(row.get("word", ""))
            if language and word:
                disabled.add((language, word))
    return disabled


def _write_disabled(disabled):
    LEXICON_DIR.mkdir(parents=True, exist_ok=True)
    with open(DISABLED_PATH, "w", encoding="utf-8") as handle:
        for language, word in sorted(disabled):
            handle.write(
                json.dumps({"lang": language, "word": word}, ensure_ascii=False) + "\n"
            )


def _read_user_words(language):
    path = LEXICON_DIR / f"{language}.txt"
    if not path.exists():
        return set()
    with open(path, "r", encoding="utf-8") as handle:
        return {
            _normalize_word(line)
            for line in handle
            if _normalize_word(line) and not line.strip().startswith("#")
        }


def _write_user_words(language, words):
    LEXICON_DIR.mkdir(parents=True, exist_ok=True)
    path = LEXICON_DIR / f"{language}.txt"
    with open(path, "w", encoding="utf-8") as handle:
        for word in sorted(words):
            handle.write(word + "\n")


@lru_cache(maxsize=1)
def load_lexicons():
    disabled = _read_disabled()
    lexicons = {}

    for language, words in STARTER_WORDS.items():
        lexicons[language] = {
            word for word in words if (language, word) not in disabled
        }

    if LEXICON_DIR.exists():
        for path in LEXICON_DIR.glob("*.txt"):
            if path.name.startswith("_"):
                continue
            language = path.stem.lower()
            words = lexicons.setdefault(language, set())
            for word in _read_user_words(language):
                if (language, word) not in disabled:
                    words.add(word)

    for row in list_lexicon_rows(enabled_only=False):
        language = row["language"]
        word = row["word"]
        if row["enabled"]:
            lexicons.setdefault(language, set()).add(word)
        else:
            lexicons.setdefault(language, set()).discard(word)

    index = {}
    for language, words in lexicons.items():
        for word in words:
            index.setdefault(word, set()).add(language)
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
    index = load_lexicons()
    stored = {
        (row["language"], row["word"]): row
        for row in list_lexicon_rows(
            query=query, language=language or None, enabled_only=True
        )
    }
    entries = []
    for word, languages in sorted(index.items()):
        if query and query not in word:
            continue
        selected_languages = sorted(
            item_language
            for item_language in languages
            if not language or item_language == language
        )
        for item_language in selected_languages:
            meta = stored.get((item_language, word), {})
            entries.append(
                {
                    "word": word,
                    "language": item_language,
                    "frequency": int(meta.get("frequency", 1) or 1),
                    "source": meta.get("source", "starter"),
                    "notes": meta.get("notes", ""),
                    "languages": sorted(languages),
                    "ambiguous": len(languages) > 1,
                }
            )
    return entries


def analyze_word_knowledge(word):
    value = _normalize_word(word)
    if not value:
        return {"word": "", "known": False, "ambiguous": False, "languages": []}
    languages = sorted(load_lexicons().get(value, []))
    entries = list_lexicon_entries(query=value)
    entries = [entry for entry in entries if entry["word"] == value]
    return {
        "word": value,
        "known": bool(languages),
        "ambiguous": len(languages) > 1,
        "languages": languages,
        "entries": entries,
    }


def add_lexicon_word(language, word, frequency=1, notes=""):
    language = str(language or "").strip().lower()
    word = _normalize_word(word)
    if not language or not word:
        raise ValueError("Language and word are required.")

    disabled = _read_disabled()
    disabled.discard((language, word))
    _write_disabled(disabled)
    upsert_lexicon_word(
        language,
        word,
        enabled=True,
        source="user",
        frequency=frequency,
        notes=notes,
    )

    words = _read_user_words(language)
    words.add(word)
    _write_user_words(language, words)

    clear_lexicon_cache()
    return {
        "language": language,
        "word": word,
        "frequency": max(1, int(frequency or 1)),
        "path": str(LEXICON_DIR / f"{language}.txt"),
    }


def import_lexicon_words(language, words_text):
    words = [
        _normalize_word(match.group(0))
        for match in WORD_RE.finditer(str(words_text or ""))
    ]
    saved = []
    for word in dict.fromkeys(words):
        saved.append(add_lexicon_word(language, word))
    return saved


def delete_lexicon_word(language, word):
    language = str(language or "").strip().lower()
    word = _normalize_word(word)
    if not language or not word:
        raise ValueError("Language and word are required.")

    words = _read_user_words(language)
    if word in words:
        words.remove(word)
        _write_user_words(language, words)

    disabled = _read_disabled()
    disabled.add((language, word))
    _write_disabled(disabled)
    set_lexicon_word_enabled(language, word, enabled=False)
    clear_lexicon_cache()
    return {"language": language, "word": word}


def detect_word(text):
    value = _normalize_word(text)
    words = WORD_RE.findall(value)
    if len(words) != 1:
        return None

    languages = sorted(load_lexicons().get(words[0], []))
    if not languages:
        return None

    confidence = round(1 / len(languages), 4)
    candidates = [
        {
            "language": language,
            "confidence": confidence,
        }
        for language in languages
    ]

    if len(languages) == 1:
        return {
            "language": languages[0],
            "confidence": 0.96,
            "source": "lexicon",
            "reason": "exact_word",
            "entity_type": "word",
            "candidates": candidates,
        }

    return {
        "language": "unknown",
        "confidence": confidence,
        "source": "lexicon",
        "reason": "ambiguous_word",
        "entity_type": "word",
        "candidates": candidates,
    }
