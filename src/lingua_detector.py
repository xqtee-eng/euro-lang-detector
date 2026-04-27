from functools import lru_cache

from src.config import LINGUA_MINIMUM_RELATIVE_DISTANCE
from src.european_languages import LINGUA_ENUM_BY_CODE, SUPPORTED_LANGUAGE_CODES

try:
    from lingua import Language, LanguageDetectorBuilder
except ImportError:  # pragma: no cover - handled via runtime fallback
    Language = None
    LanguageDetectorBuilder = None


def lingua_available():
    return Language is not None and LanguageDetectorBuilder is not None


def _language_to_code(language):
    try:
        return language.iso_code_639_1.name.lower()
    except AttributeError:
        name = getattr(language, "name", None)
        if not name:
            return None
        for code, enum_name in LINGUA_ENUM_BY_CODE.items():
            if enum_name == name:
                return code
    return None


@lru_cache(maxsize=1)
def get_detector():
    if not lingua_available():
        return None

    languages = []
    for code in SUPPORTED_LANGUAGE_CODES:
        enum_name = LINGUA_ENUM_BY_CODE[code]
        languages.append(getattr(Language, enum_name))

    builder = LanguageDetectorBuilder.from_languages(*languages)
    if LINGUA_MINIMUM_RELATIVE_DISTANCE > 0:
        builder = builder.with_minimum_relative_distance(
            LINGUA_MINIMUM_RELATIVE_DISTANCE
        )
    return builder.build()


def detect_with_lingua(text, top_k=3):
    detector = get_detector()
    if detector is None:
        return None, 0.0, []

    confidence_values = detector.compute_language_confidence_values(text)
    candidates = []
    for value in confidence_values[: max(1, top_k)]:
        code = _language_to_code(value.language)
        if code:
            candidates.append(
                {"language": code, "confidence": round(float(value.value), 4)}
            )

    language = detector.detect_language_of(text)
    if language is None:
        return None, 0.0, candidates

    code = _language_to_code(language)
    confidence = candidates[0]["confidence"] if candidates else 0.0
    return code, float(confidence), candidates
