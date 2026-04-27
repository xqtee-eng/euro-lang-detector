import math

from src.ngram import generate_ngrams
from src.preprocessing import clean_text
from src.profiles import load_profiles


def cosine_similarity(left, right):
    overlap = set(left) & set(right)
    numerator = sum(left[key] * right[key] for key in overlap)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return numerator / (left_norm * right_norm + 1e-9)


def _build_input_profile(text):
    grams = generate_ngrams(clean_text(text))
    counts = {}
    for gram in grams:
        counts[gram] = counts.get(gram, 0) + 1

    total = sum(counts.values())
    if total == 0:
        return {}
    return {key: value / total for key, value in counts.items()}


def rank_languages(text, top_k=3):
    profiles = load_profiles()
    input_profile = _build_input_profile(text)
    if not profiles or not input_profile:
        return []

    ranked = []
    for language, profile in profiles.items():
        ranked.append(
            {
                "language": language,
                "confidence": round(cosine_similarity(input_profile, profile), 4),
            }
        )

    ranked.sort(key=lambda item: item["confidence"], reverse=True)
    return ranked[: max(1, top_k)]


def detect(text):
    ranked = rank_languages(text, top_k=1)
    if not ranked:
        return None, 0.0
    best = ranked[0]
    return best["language"], float(best["confidence"])
