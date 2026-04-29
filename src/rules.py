import re

from src.european_languages import (
    EXACT_PHRASE_LANGUAGE_HINTS,
    LEXICAL_LANGUAGE_HINTS,
    SCRIPT_RULES,
    UNIQUE_CHAR_LANGUAGE_HINTS,
)
from src.character_profiles import load_character_profiles

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

_DYNAMIC_CHAR_HINTS = None

def _get_dynamic_char_hints():
    global _DYNAMIC_CHAR_HINTS
    if _DYNAMIC_CHAR_HINTS is None:
        _DYNAMIC_CHAR_HINTS = {}
        try:
            profiles = load_character_profiles()
            for lang, data in profiles.items():
                if "unique_characters" in data and data["unique_characters"]:
                    _DYNAMIC_CHAR_HINTS[lang] = data["unique_characters"]
        except Exception:
            pass
    return _DYNAMIC_CHAR_HINTS

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
        matched_hint = None

        for hint in hints:
            if hint == compact or (
                " " in hint and (hint in lowered or hint in compact)
            ):
                matched_hint = hint
                break

        if matched_hint:
            return {
                "language": lang_code,
                "confidence": 0.75 if " " in matched_hint else 0.70,
                "source": "rule",
                "reason": "lexical_hint",
                "matched_hint": matched_hint,
            }

    # 1. Hardcoded high-confidence character hints
    for lang_code, chars in UNIQUE_CHAR_LANGUAGE_HINTS.items():
        if any(char in lowered for char in chars):
            return {
                "language": lang_code,
                "confidence": 1.0,
                "source": "rule",
                "reason": "unique_character",
            }
            
    # 2. Dynamically learned character hints are disabled because small corpora 
    # assign common letters (like ž) to a single language incorrectly.
    # for lang_code, chars in _get_dynamic_char_hints().items():
    #     if any(char in lowered for char in chars):
    #         return {
    #             "language": lang_code,
    #             "confidence": 0.95,
    #             "source": "rule",
    #             "reason": "learned_unique_character",
    #         }

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


def is_keyboard_garbage(text):
    cleaned = (text or "").strip().lower()

    if len(cleaned) >= 6 and " " not in cleaned:
        letters = [char for char in cleaned if char.isalpha()]
        if len(letters) < 6:
            return False

        vowels = sum(1 for char in letters if char in "aeiouyáéíóúýäëïöüâêîôûàèìòùãõåæøœąęėįųūаеєиіїоуюяэыё")
        vowel_ratio = vowels / len(letters)

        keyboard_runs = ("asdf", "qwer", "zxcv", "jkl", "ghj", "dfgh")

        if vowel_ratio <= 0.2:
            return True

        if any(run in cleaned for run in keyboard_runs):
            return True

    return False
