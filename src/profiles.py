import json

from src.config import MODEL_PATH


def save_profiles(profiles):
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "w", encoding="utf-8") as handle:
        json.dump(profiles, handle, ensure_ascii=False, indent=2)


def load_profiles():
    try:
        with open(MODEL_PATH, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return {}
