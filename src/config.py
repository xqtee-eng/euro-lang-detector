import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("ELD_DATA_DIR", ROOT_DIR / "data"))
MODELS_DIR = Path(os.environ.get("ELD_MODELS_DIR", ROOT_DIR / "models"))
LOG_DIR = Path(os.environ.get("ELD_LOG_DIR", ROOT_DIR / "logs"))
MODEL_SNAPSHOT_DIR = MODELS_DIR / "snapshots"

APP_ENV = os.environ.get("ELD_ENV", "development").strip().lower()
APP_HOST = os.environ.get("ELD_HOST", "127.0.0.1")
APP_PORT = int(os.environ.get("ELD_PORT", "5000"))
APP_DEBUG = os.environ.get("ELD_DEBUG", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

NGRAM_MIN = 1
NGRAM_MAX = 5
PROFILE_SIZE = 1000

LINGUA_MINIMUM_RELATIVE_DISTANCE = 0.04
PROFILE_MIN_CONFIDENCE = 0.20
UNKNOWN_LANGUAGE = "unknown"

MODEL_PATH = MODELS_DIR / "profiles.json"
RELATED_MODEL_PATH = MODELS_DIR / "related_profiles.json"
DATASET_PATH = DATA_DIR / "dataset.jsonl"
TRAIN_DATASET_PATH = DATA_DIR / "train.jsonl"
TEST_DATASET_PATH = DATA_DIR / "test.jsonl"
UNKNOWN_PATH = DATA_DIR / "unknown.jsonl"
FEEDBACK_PATH = DATA_DIR / "feedback.jsonl"
RESOLVED_UNKNOWN_PATH = DATA_DIR / "resolved_unknown.jsonl"
BENCHMARK_PATH = DATA_DIR / "benchmark.jsonl"
LEXICON_DIR = DATA_DIR / "lexicons"
FREQUENCY_DIR = DATA_DIR / "frequency"
NAME_DIR = DATA_DIR / "names"
CLOSE_PACK_DIR = DATA_DIR / "close_pack"
RAW_DATA_DIR = DATA_DIR / "raw"
EVALUATION_REPORT_PATH = MODELS_DIR / "evaluation_report.json"
DATABASE_PATH = DATA_DIR / "app.db"

DEFAULT_ADMIN_PASSWORD = "admin"
DEFAULT_SECRET_KEY = "y5gX$jL7@mC2*zBq9hWvFpRdS"

ADMIN_USERNAME = os.environ.get("ELD_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ELD_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
SECRET_KEY = os.environ.get("ELD_SECRET_KEY", DEFAULT_SECRET_KEY)


def production_mode():
    return APP_ENV in {"prod", "production"} or not APP_DEBUG


def validate_runtime_config():
    if not production_mode():
        return

    errors = []
    if ADMIN_PASSWORD == DEFAULT_ADMIN_PASSWORD:
        errors.append("set ELD_ADMIN_PASSWORD to a non-default value")
    if SECRET_KEY == DEFAULT_SECRET_KEY or len(SECRET_KEY) < 32:
        errors.append("set ELD_SECRET_KEY to a random value of at least 32 chars")

    if errors:
        raise RuntimeError(
            "Unsafe production configuration: " + "; ".join(errors) + "."
        )


validate_runtime_config()
