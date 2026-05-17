import json
from collections import Counter

from src.build_dataset import RAW_DATA_DIR
from src.config import MODELS_DIR
from src.european_languages import SUPPORTED_LANGUAGE_CODES, get_language_name
from src.preprocessing import clean_text

CHARACTER_PROFILE_PATH = MODELS_DIR / "character_profiles.json"


def _letters(text):
    for char in clean_text(text):
        if char.isalpha():
            yield char.lower()


def _count_raw_language(language):
    path = RAW_DATA_DIR / f"{language}.txt"
    counts = Counter()
    if not path.exists():
        return counts
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            counts.update(_letters(line))
    return counts


def generate_character_profiles(top_n=30):
    language_counts = {
        language: _count_raw_language(language) for language in SUPPORTED_LANGUAGE_CODES
    }
    global_presence = Counter()
    for counts in language_counts.values():
        for char in counts:
            global_presence[char] += 1

    profiles = {}
    for language, counts in language_counts.items():
        total = sum(counts.values())
        unique_chars = sorted(char for char in counts if global_presence[char] == 1)
        profiles[language] = {
            "language": language,
            "name": get_language_name(language),
            "total_letters": total,
            "alphabet_size": len(counts),
            "top_characters": [
                {
                    "char": char,
                    "count": count,
                    "share": round(count / total, 4) if total else 0,
                }
                for char, count in counts.most_common(max(1, int(top_n or 30)))
            ],
            "unique_characters": unique_chars,
            "signature": "".join(unique_chars[:20]),
        }

    CHARACTER_PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CHARACTER_PROFILE_PATH, "w", encoding="utf-8") as handle:
        json.dump(profiles, handle, ensure_ascii=False, indent=2)
    return profiles


_CHARACTER_PROFILES_CACHE = None

def load_character_profiles():
    global _CHARACTER_PROFILES_CACHE
    if _CHARACTER_PROFILES_CACHE is not None:
        return _CHARACTER_PROFILES_CACHE
    if not CHARACTER_PROFILE_PATH.exists():
        _CHARACTER_PROFILES_CACHE = generate_character_profiles()
        return _CHARACTER_PROFILES_CACHE
    with open(CHARACTER_PROFILE_PATH, "r", encoding="utf-8") as handle:
        _CHARACTER_PROFILES_CACHE = json.load(handle)
        return _CHARACTER_PROFILES_CACHE

def clear_character_profiles_cache():
    global _CHARACTER_PROFILES_CACHE
    _CHARACTER_PROFILES_CACHE = None


def character_profile_summary():
    profiles = load_character_profiles()
    rows = []
    for language in SUPPORTED_LANGUAGE_CODES:
        profile = profiles.get(language, {})
        rows.append(
            {
                "language": language,
                "name": profile.get("name", get_language_name(language)),
                "total_letters": profile.get("total_letters", 0),
                "alphabet_size": profile.get("alphabet_size", 0),
                "unique_characters": profile.get("unique_characters", []),
                "signature": profile.get("signature", ""),
            }
        )
    return {
        "path": str(CHARACTER_PROFILE_PATH),
        "languages": len(profiles),
        "profiles": rows,
    }


def character_candidates(text, top_k=5):
    value_chars = Counter(_letters(text))
    if not value_chars:
        return []
    profiles = load_character_profiles()
    candidates = []
    for language, profile in profiles.items():
        signature = set(profile.get("unique_characters", []))
        top_chars = {item["char"] for item in profile.get("top_characters", [])[:15]}
        signature_hits = sum(value_chars[char] for char in signature)
        top_hits = sum(value_chars[char] for char in top_chars)
        score = signature_hits * 3 + top_hits
        if score:
            candidates.append(
                {
                    "language": language,
                    "score": score,
                    "signature_hits": signature_hits,
                    "top_character_hits": top_hits,
                }
            )
    return sorted(candidates, key=lambda item: item["score"], reverse=True)[
        : max(1, int(top_k or 5))
    ]


if __name__ == "__main__":
    print("[*] Generating character profiles...")
    generate_character_profiles()
    print("[*] Done.")
