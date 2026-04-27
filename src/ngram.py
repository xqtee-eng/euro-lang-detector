from collections import Counter
from src.config import NGRAM_MIN, NGRAM_MAX


def generate_ngrams(text, n_min=NGRAM_MIN, n_max=NGRAM_MAX):
    text = f" {text} "
    grams = []

    for n in range(n_min, n_max + 1):
        for i in range(len(text) - n + 1):
            grams.append(text[i : i + n])

    return grams


def build_profile(texts, size=300):
    counter = Counter()
    for t in texts:
        grams = generate_ngrams(t)
        counter.update(grams)

    total = sum(counter.values())
    profile = {k: v / total for k, v in counter.items()}

    return dict(sorted(profile.items(), key=lambda x: x[1], reverse=True)[:size])
