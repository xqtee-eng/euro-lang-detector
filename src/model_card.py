import json

from src.config import EVALUATION_REPORT_PATH, MODEL_PATH
from src.data_quality import data_quality_report
from src.european_languages import EUROPEAN_LANGUAGE_SPECS
from src.safety import safety_status


def _latest_evaluation():
    if not EVALUATION_REPORT_PATH.exists():
        return {}
    with open(EVALUATION_REPORT_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def model_card():
    quality = data_quality_report()
    evaluation = _latest_evaluation()
    return {
        "name": "European Language Detector",
        "version": "local-mvp",
        "model_path": str(MODEL_PATH),
        "task": "Detect popular European languages from words, names, phrases, and short texts.",
        "languages": EUROPEAN_LANGUAGE_SPECS,
        "pipeline": [
            "deterministic character/script rules",
            "name hints",
            "lexicon and frequency lists",
            "Lingua detector",
            "local n-gram profiles",
            "active learning queue for uncertain cases",
        ],
        "quality": quality["scores"],
        "benchmark": quality["benchmark"],
        "data": {
            "dataset": quality["dataset"],
            "train": quality["train"],
            "test": quality["test"],
            "knowledge": quality["knowledge"],
            "character_profiles": quality["character_profiles"],
        },
        "latest_evaluation": {
            "samples": evaluation.get("samples", 0),
            "accuracy": evaluation.get("accuracy", 0),
            "unknown": evaluation.get("unknown", 0),
            "dataset": evaluation.get("dataset", ""),
        },
        "safety": safety_status()["policy"],
        "limitations": [
            "Short single words can be genuinely ambiguous across related languages.",
            "Real-world quality depends on adding larger reviewed corpora and external frequency lists.",
            "The system avoids blind self-training and requires human-approved feedback.",
            "The current benchmark is useful for regression checks, not a replacement for a large independent test set.",
        ],
        "recommended_next_steps": quality["recommendations"],
    }
