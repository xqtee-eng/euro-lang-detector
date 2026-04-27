import json
from collections import defaultdict

from src.config import DATASET_PATH, TRAIN_DATASET_PATH
from src.european_languages import SUPPORTED_LANGUAGE_CODES
from src.ngram import build_profile
from src.preprocessing import clean_text
from src.config import MODEL_PATH
from src.profiles import save_profiles
from src.related_classifier import train_related_classifiers
from src.storage import create_model_snapshot, record_training_run


def train(dataset_path=None, kind="train", notes=""):
    dataset_path = dataset_path or (TRAIN_DATASET_PATH if TRAIN_DATASET_PATH.exists() else DATASET_PATH)
    language_texts = defaultdict(list)

    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    with open(dataset_path, "r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            language = row.get("lang", "").lower()
            text = clean_text(row.get("text", ""))
            if language not in SUPPORTED_LANGUAGE_CODES or not text:
                continue
            language_texts[language].append(text)

    profiles = {}
    for language, texts in sorted(language_texts.items()):
        profiles[language] = build_profile(texts)
        print(f"Trained {language}: {len(texts)} samples")

    if not profiles:
        print(f"No valid training samples found in {dataset_path}.")
        print("Profiles were not changed.")
        return {}

    save_profiles(profiles)
    print(f"Saved {len(profiles)} profiles to {MODEL_PATH}")
    snapshot_path = create_model_snapshot(label=kind)
    total_samples = sum(len(texts) for texts in language_texts.values())
    record_training_run(
        kind=kind,
        samples=total_samples,
        correct=0,
        unknown=0,
        accuracy=0,
        model_snapshot_path=snapshot_path,
        notes=notes or f"Trained from {dataset_path}",
    )
    if snapshot_path:
        print(f"Saved model snapshot to {snapshot_path}")
    related_profiles = train_related_classifiers(dataset_path=dataset_path)
    if related_profiles:
        related_languages = sum(len(group) for group in related_profiles.values())
        print(f"Saved related-language profiles for {related_languages} languages")
    return profiles


if __name__ == "__main__":
    train()
