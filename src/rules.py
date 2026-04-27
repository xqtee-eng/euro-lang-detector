import re

from src.european_languages import (
    EXACT_PHRASE_LANGUAGE_HINTS,
    LEXICAL_LANGUAGE_HINTS,
    SCRIPT_RULES,
    UNIQUE_CHAR_LANGUAGE_HINTS,
)

LATIN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿĀ-ſ]")
CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
WORD_RE = re.compile(r"[\w'-]+", re.UNICODE)
COMMAND_HINTS = (
    "python ",
    "py ",
    "pip ",
    "cd ",
    "curl ",
    "invoke-restmethod",
)


def _contains_script(text, bounds):
    start, end = bounds
    for char in text:
        codepoint = ord(char)
        if start <= codepoint <= end:
            return True
    return False


def detect_by_rules(text):
    lowered = (text or "").lower()
    compact = " ".join(WORD_RE.findall(lowered))

    exact_language = EXACT_PHRASE_LANGUAGE_HINTS.get(compact)
    if exact_language:
        return {
            "language": exact_language,
            "confidence": 0.99,
            "source": "rule",
            "reason": "exact_phrase_hint",
        }

    for lang_code, hints in LEXICAL_LANGUAGE_HINTS.items():
        if any(
            hint == compact or (" " in hint and (hint in lowered or hint in compact))
            for hint in hints
        ):
            return {
                "language": lang_code,
                "confidence": 0.98,
                "source": "rule",
                "reason": "lexical_hint",
            }

    for lang_code, chars in UNIQUE_CHAR_LANGUAGE_HINTS.items():
        if any(char in lowered for char in chars):
            return {
                "language": lang_code,
                "confidence": 1.0,
                "source": "rule",
                "reason": "unique_character",
            }

    for lang_code, (_, bounds) in SCRIPT_RULES.items():
        if _contains_script(lowered, bounds):
            return {
                "language": lang_code,
                "confidence": 1.0,
                "source": "rule",
                "reason": "script",
            }

    return None


def has_mixed_latin_cyrillic(text):
    return bool(LATIN_RE.search(text or "") and CYRILLIC_RE.search(text or ""))


def is_command_like(text):
    lowered = (text or "").strip().lower()
    return (
        lowered.startswith(COMMAND_HINTS)
        or ".py" in lowered
        or "http://" in lowered
        or "https://" in lowered
    )


def is_short_ambiguous_cyrillic(text, max_length=7):
    value = (text or "").strip().lower()
    words = WORD_RE.findall(value)
    if len(words) != 1:
        return False
    word = words[0]
    return bool(CYRILLIC_RE.search(word)) and len(word) <= max_length


def is_single_cyrillic_proper_name(text):
    value = (text or "").strip()
    words = WORD_RE.findall(value)
    if len(words) != 1:
        return False

    word = words[0]
    if not CYRILLIC_RE.search(word):
        return False
    if word.isupper() or word.islower():
        return False
    return word[:1].isupper()
