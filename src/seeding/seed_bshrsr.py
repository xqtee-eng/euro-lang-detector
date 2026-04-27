import random
import json
from pathlib import Path

from src.config import CLOSE_PACK_DIR

BENCHMARK_PATH = Path("data/benchmark_bshrsr.jsonl")

# Specific markers provided by the user
LANG_DATA = {
    "bs": {
        "coffee": "kahvu",
        "coffee_nom": "kahva",
        "easy": "lahko",
        "thousand": "hiljada",
        "always": "uvijek",
        "world": "svijet",
        "should_go": "trebamo ići",
        "beautiful": "lijep",
    },
    "hr": {
        "coffee": "kavu",
        "coffee_nom": "kava",
        "easy": "lako",
        "thousand": "tisuća",
        "always": "uvijek",
        "world": "svijet",
        "should_go": "trebamo ići",
        "beautiful": "lijep",
    },
    "sr": {
        "coffee": "kafu",
        "coffee_nom": "kafa",
        "easy": "lako",
        "thousand": "hiljadu",
        "always": "uvek",
        "world": "svet",
        "should_go": "treba da idemo",
        "beautiful": "lep",
    },
}

TEMPLATES = [
    "Mislim da je to veoma {easy} za uraditi.",
    "Ovaj zadatak je {easy} ako se potrudimo.",
    (
        "Nije tako {easy} razumeti taj problem."
        if "{easy}" == "lako"
        else "Nije tako {easy} razumjeti taj problem."
    ),
    (
        "Mi {always} pijemo {coffee} pre posla."
        if "{always}" == "uvek"
        else "Mi {always} pijemo {coffee} prije posla."
    ),
    "Ona {always} naručuje {coffee} u ovom kafiću.",
    "Zašto {always} moraš piti {coffee} tako kasno?",
    "Na trgu je bilo više od {thousand} ljudi.",
    (
        "Ovaj projekat košta više od {thousand} evra."
        if "{thousand}" == "hiljadu"
        else "Ovaj projekat košta više od {thousand} eura."
    ),
    (
        "Celi {world} zna za taj događaj."
        if "{world}" == "svet"
        else "Cijeli {world} zna za taj događaj."
    ),
    "Ovo je najbolji {world} koji možemo zamisliti.",
    (
        "Mislim da mi {should_go} kući što pre."
        if "{world}" == "svet"
        else "Mislim da mi {should_go} kući što prije."
    ),
    "Moj prijatelj kaže da je to {easy}.",
    "On {always} misli da je u pravu.",
    (
        "Naš {world} se brzo menja."
        if "{world}" == "svet"
        else "Naš {world} se brzo mijenja."
    ),
    "Ovo je najskuplja {coffee_nom} koju sam ikada pio.",
    "Više od {thousand} studenata je došlo na predavanje.",
    "Tvoja {coffee_nom} se već ohladila.",
    "To je veoma {beautiful} {world}.",
    (
        "Mi {always} verujemo u to."
        if "{always}" == "uvek"
        else "Mi {always} vjerujemo u to."
    ),
    "Misliš da je to {easy}? Nije nimalo {easy}.",
    (
        "{coffee_nom} je spremna, možemo da je pijemo."
        if "{always}" == "uvek"
        else "{coffee_nom} je spremna, možemo je piti."
    ),
]


def generate_sentences(lang_code, count):
    data = LANG_DATA[lang_code]
    generated = set()

    # Simple prefixes to increase entropy
    prefixes = [
        "Znaš da ",
        "Kažu da ",
        "Možda ",
        "Naravno, ",
        "Sigurno ",
        "Vidiš, ",
        "Iskreno, ",
        "Danas ",
        "Juče ",
        "Jucer ",
        "Sutra ",
        "Ujutro ",
        "Opet ",
        "Mislim da ",
        "Zato ",
        "Sada ",
        "Zaista, ",
        "Verovatno " if lang_code == "sr" else "Vjerojatno ",
    ]
    suffixes = [
        " zar ne?",
        " danas.",
        " odmah.",
        " uvek." if lang_code == "sr" else " uvijek.",
        " zar ne misliš tako?",
        " to je sigurno.",
        " bez sumnje.",
    ]

    # Failsafe counter
    attempts = 0
    max_attempts = count * 20

    while len(generated) < count and attempts < max_attempts:
        attempts += 1
        t = random.choice(TEMPLATES)
        sentence = t.format(**data)

        # fix ekavian/ijekavian mismatches from templates manually
        if lang_code == "sr":
            sentence = (
                sentence.replace("razumjeti", "razumeti")
                .replace("Jucer", "Juce")
                .replace("vjerujemo", "verujemo")
            )
        else:
            sentence = (
                sentence.replace("razumeti", "razumjeti")
                .replace("Juce", "Jucer")
                .replace("verujemo", "vjerujemo")
            )

        # Add random prefix
        if random.random() < 0.6:
            prefix = random.choice(prefixes)
            if lang_code == "sr" and prefix == "Jucer ":
                prefix = "Juče "
            elif lang_code != "sr" and prefix == "Juče ":
                prefix = "Jucer "

            sentence = prefix + sentence[0].lower() + sentence[1:]

        # Add random suffix
        if random.random() < 0.4:
            # remove period if exists at the end
            if sentence.endswith("."):
                sentence = sentence[:-1]
            sentence = sentence + random.choice(suffixes)

        generated.add(sentence)

    return list(generated)


def main():
    CLOSE_PACK_DIR.mkdir(parents=True, exist_ok=True)

    train_count = 150
    bench_count = 30

    bench_samples = []

    for lang in ["bs", "hr", "sr"]:
        all_sentences = generate_sentences(lang, train_count + bench_count)

        # If we couldn't generate enough, just use what we have
        actual_train_count = min(
            train_count, len(all_sentences) - 10
        )  # leave at least 10 for bench

        train_sentences = all_sentences[:actual_train_count]
        bench_sentences_lang = all_sentences[actual_train_count:]

        # Write to close pack (replace existing)
        pack_path = CLOSE_PACK_DIR / f"{lang}.txt"
        with open(pack_path, "w", encoding="utf-8") as f:
            for s in train_sentences:
                f.write(s + "\n")
        print(f"Wrote {len(train_sentences)} sentences to {pack_path}")

        # Prepare benchmark
        for s in bench_sentences_lang:
            bench_samples.append(
                {"text": s, "expected": lang, "category": "disambiguation"}
            )

    # Write benchmark
    BENCHMARK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BENCHMARK_PATH, "w", encoding="utf-8") as f:
        for sample in bench_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
    print(f"Wrote {len(bench_samples)} sentences to {BENCHMARK_PATH}")


if __name__ == "__main__":
    main()
