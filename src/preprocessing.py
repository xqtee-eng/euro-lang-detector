import re
import unicodedata

LETTER_OR_MARK_RE = re.compile(r"[^\w\s\-']", re.UNICODE)


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.lower()
    text = re.sub(r"\d+", " ", text)
    text = LETTER_OR_MARK_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
