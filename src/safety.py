from src.config import DATABASE_PATH, DATASET_PATH, MODEL_PATH

SAFETY_POLICY = {
    "human_approved_learning_only": True,
    "auto_train_on_low_confidence": False,
    "auto_train_on_unknown": False,
    "active_learning_requires_review": True,
    "feedback_required_for_retrain": True,
    "notes": [
        "Low-confidence guesses are queued for review instead of being added to training data.",
        "Only reviewer-approved feedback is promoted during retrain.",
        "Lexicon words and name hints are explicit human edits.",
    ],
}


def safety_status():
    return {
        "policy": SAFETY_POLICY,
        "data_files": {
            "database": str(DATABASE_PATH),
            "dataset": str(DATASET_PATH),
            "model": str(MODEL_PATH),
        },
        "safe_to_train": True,
    }
