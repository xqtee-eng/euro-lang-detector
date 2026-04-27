from src.config import PROFILE_MIN_CONFIDENCE, UNKNOWN_LANGUAGE
from src.detector import detect as detect_with_profile
from src.detector import rank_languages
from src.lingua_detector import detect_with_lingua, lingua_available
from src.name_detector import detect_name
from src.preprocessing import clean_text
from src.related_classifier import refine_related_language_result
from src.related_languages import enrich_related_language_result
from src.rules import (
    detect_by_rules,
    has_mixed_latin_cyrillic,
    is_command_like,
    is_short_ambiguous_cyrillic,
    is_single_cyrillic_proper_name,
)
from src.self_learning import queue_unknown
from src.storage import add_active_learning_item
from src.word_lexicon import detect_word


def _quality_label(language, confidence, source):
    if language == UNKNOWN_LANGUAGE:
        return "unknown"
    if source == "rule" and confidence >= 0.95:
        return "high"
    if confidence >= 0.75:
        return "high"
    if confidence >= 0.45:
        return "medium"
    return "low"


def _finalize_result(result):
    reliability = _quality_label(
        result.get("language", UNKNOWN_LANGUAGE),
        float(result.get("confidence", 0.0)),
        result.get("source", "unknown"),
    )
    result["reliability"] = reliability
    if reliability == "low":
        result["warning"] = "Low-confidence result. Add feedback if the label is wrong."
    return enrich_related_language_result(result)


def _unknown_result(text, candidates=None):
    result = {
        "text": text,
        "language": UNKNOWN_LANGUAGE,
        "confidence": 0.0,
        "source": "unknown",
        "candidates": candidates or [],
    }
    if not lingua_available():
        result["warning"] = (
            "Install lingua-language-detector for full European language coverage."
        )
    return _finalize_result(result)


def _track_learning(result, record_unknown):
    if record_unknown and not is_command_like(result.get("text", "")):
        add_active_learning_item(result.get("text", ""), result)
    return result


def smart_detect_details(text, top_k=3, record_unknown=True):
    original_text = text or ""
    normalized = clean_text(original_text)
    if not normalized:
        return _unknown_result(original_text)

    if is_command_like(original_text):
        result = _unknown_result(original_text)
        result["source"] = "rule"
        result["reason"] = "command_like_text"
        return result

    if has_mixed_latin_cyrillic(original_text):
        result = _unknown_result(original_text)
        result["source"] = "rule"
        result["reason"] = "mixed_latin_cyrillic"
        if record_unknown:
            queue_unknown(original_text, details={"reason": "mixed_latin_cyrillic"})
        return _track_learning(result, record_unknown)

    rule_result = detect_by_rules(original_text)
    if rule_result:
        return _finalize_result(
            {
                "text": original_text,
                "language": rule_result["language"],
                "confidence": rule_result["confidence"],
                "source": rule_result["source"],
                "reason": rule_result["reason"],
                "candidates": [
                    {
                        "language": rule_result["language"],
                        "confidence": rule_result["confidence"],
                    }
                ],
            }
        )

    name_result = detect_name(original_text)
    if name_result:
        result = _finalize_result({"text": original_text, **name_result})
        if record_unknown and result["language"] == UNKNOWN_LANGUAGE:
            queue_unknown(original_text, details={"reason": result["reason"]})
        return _track_learning(result, record_unknown)

    word_result = detect_word(original_text)
    if word_result:
        result = _finalize_result({"text": original_text, **word_result})
        if record_unknown and result["language"] == UNKNOWN_LANGUAGE:
            queue_unknown(original_text, details={"reason": result["reason"]})
        return _track_learning(result, record_unknown)

    if is_short_ambiguous_cyrillic(original_text):
        result = _unknown_result(original_text)
        result["source"] = "rule"
        result["reason"] = "short_ambiguous_cyrillic"
        if record_unknown:
            queue_unknown(original_text, details={"reason": "short_ambiguous_cyrillic"})
        return _track_learning(result, record_unknown)

    if is_single_cyrillic_proper_name(original_text):
        result = _unknown_result(original_text)
        result["source"] = "rule"
        result["reason"] = "single_cyrillic_proper_name"
        result["entity_type"] = "person_name"
        if record_unknown:
            queue_unknown(
                original_text,
                details={
                    "reason": "single_cyrillic_proper_name",
                    "entity_type": "person_name",
                },
            )
        return _track_learning(result, record_unknown)

    language, confidence, candidates = detect_with_lingua(normalized, top_k=top_k)
    if language:
        result = {
            "text": original_text,
            "language": language,
            "confidence": round(confidence, 4),
            "source": "lingua",
            "candidates": candidates,
        }
        return _track_learning(
            _finalize_result(refine_related_language_result(result, normalized)),
            record_unknown,
        )

    profile_language, profile_confidence = detect_with_profile(normalized)
    profile_candidates = rank_languages(normalized, top_k=top_k)
    if profile_language and profile_confidence >= PROFILE_MIN_CONFIDENCE:
        result = {
            "text": original_text,
            "language": profile_language,
            "confidence": round(profile_confidence, 4),
            "source": "profile",
            "candidates": profile_candidates,
        }
        return _track_learning(
            _finalize_result(refine_related_language_result(result, normalized)),
            record_unknown,
        )

    unknown = _unknown_result(original_text, candidates or profile_candidates)
    if record_unknown:
        queue_unknown(
            original_text,
            details={
                "lingua_candidates": candidates,
                "profile_candidates": profile_candidates,
            },
        )
    return _track_learning(unknown, record_unknown)


def smart_detect(text):
    return smart_detect_details(text)["language"]
