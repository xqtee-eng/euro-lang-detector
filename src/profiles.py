import json

from src.config import MODEL_PATH


def save_profiles(profiles):
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "w", encoding="utf-8") as handle:
        json.dump(profiles, handle, ensure_ascii=False, indent=2)
    clear_profiles_cache()


_PROFILES_CACHE = None

def load_profiles():
    global _PROFILES_CACHE
    if _PROFILES_CACHE is not None:
        return _PROFILES_CACHE
    try:
        if not MODEL_PATH.exists():
            return {}
        with open(MODEL_PATH, "r", encoding="utf-8") as handle:
            _PROFILES_CACHE = json.load(handle)
            return _PROFILES_CACHE
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def clear_profiles_cache():
    global _PROFILES_CACHE
    _PROFILES_CACHE = None
