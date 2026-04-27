from collections import Counter

from src.hybrid import smart_detect_details
from src.rules import WORD_RE


def analyze_words(text, top_k=3):
    tokens = []
    language_counts = Counter()
    known = 0

    for match in WORD_RE.finditer(text or ""):
        token = match.group(0)
        result = smart_detect_details(token, top_k=top_k, record_unknown=False)
        token_info = {
            "text": token,
            "start": match.start(),
            "end": match.end(),
            "language": result.get("language", "unknown"),
            "confidence": result.get("confidence", 0.0),
            "source": result.get("source", "unknown"),
            "reason": result.get("reason"),
            "reliability": result.get("reliability", "unknown"),
            "language_group": result.get("language_group"),
            "group_reliability": result.get("group_reliability"),
            "entity_type": result.get("entity_type", "word"),
            "candidates": result.get("name_candidates") or result.get("candidates", []),
        }
        tokens.append(token_info)

        if token_info["language"] != "unknown":
            known += 1
            language_counts[token_info["language"]] += 1

    if not tokens:
        dominant = "unknown"
    elif len(language_counts) == 1 and known == len(tokens):
        dominant = next(iter(language_counts))
    elif len(language_counts) > 1:
        dominant = "mixed"
    else:
        dominant = "unknown"

    coverage = round(known / len(tokens), 4) if tokens else 0.0
    return {
        "text": text or "",
        "language": dominant,
        "coverage": coverage,
        "token_count": len(tokens),
        "known_token_count": known,
        "language_counts": dict(language_counts),
        "tokens": tokens,
    }
