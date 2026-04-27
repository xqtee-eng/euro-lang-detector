import logging
from logging.handlers import RotatingFileHandler

from src.config import LOG_DIR

APP_LOG_PATH = LOG_DIR / "app.log"


def get_app_logger():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("euro_lang_detector")
    logger.setLevel(logging.INFO)
    if not any(isinstance(handler, RotatingFileHandler) for handler in logger.handlers):
        handler = RotatingFileHandler(
            APP_LOG_PATH,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logger.addHandler(handler)
    return logger


def tail_log(limit=200):
    if not APP_LOG_PATH.exists():
        return []
    with open(APP_LOG_PATH, "r", encoding="utf-8") as handle:
        lines = handle.readlines()
    return [line.rstrip("\n") for line in lines[-max(1, int(limit or 200)):]]
