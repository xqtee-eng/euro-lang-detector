import argparse
from pathlib import Path

from src.config import CLOSE_PACK_DIR
from src.european_languages import SUPPORTED_LANGUAGE_CODES

CLOSE_LANGUAGE_PACK = {
    "bs": [
        "Ovdje uvijek pijemo kahvu prije posla.",
        "Hiljada ljudi ceka autobus u centru grada.",
        "Mozemo lahko zavrsiti ovaj zadatak danas.",
        "Treba nam jos vremena za bosanski izvjestaj.",
        "Gdje si bio kada je poceo sastanak?",
        "Hvala vam na pomoci i razumijevanju.",
        "Molim vas da zapisnik bude spreman odmah.",
        "Bosanski tim koristi rijec lahko svaki dan.",
        "Ovdje se govori bosanski jezik u skoli.",
        "Nemojte kasniti jer sastanak pocinje rano.",
        "Jucer smo gledali film u starom kinu.",
        "Zelim da poruka stigne prije vecere.",
    ],
    "hr": [
        "Ovdje uvijek pijemo kavu prije posla.",
        "Tisuca ljudi ceka autobus u sredis tu grada.",
        "Mozemo brzo dovrsiti ovaj zadatak danas.",
        "Trebamo jos vremena za hrvatsko izvjesce.",
        "Gdje si bio kada je poceo sastanak?",
        "Hvala vam na pomoci i razumijevanju.",
        "Molim vas da zapisnik bude spreman odmah.",
        "Hrvatski tim koristi rijec lijep i svijet.",
        "Ovdje se govori hrvatski jezik u skoli.",
        "Nemojte kasniti jer sastanak pocinje rano.",
        "Jucer smo gledali film u starom kinu.",
        "Uvijek biramo mlijeko i rijecnik iz knjiznice.",
    ],
    "sr": [
        "Ovde uvek pijemo kafu pre posla.",
        "Hiljadu ljudi ceka autobus u centru grada.",
        "Mozemo brzo zavrsiti ovaj zadatak danas.",
        "Treba da imamo jos vremena za srpski izvestaj.",
        "Gde si bio kada je poceo sastanak?",
        "Hvala vam na pomoci i razumevanju.",
        "Molim vas da zapisnik bude spreman odmah.",
        "Srpski tim koristi reci lep i svet.",
        "Ovde se govori srpski jezik u skoli.",
        "Nemojte kasniti jer sastanak pocinje rano.",
        "Juce smo gledali film u starom bioskopu.",
        "Devojka misli da je vreme za odmor.",
    ],
    "nb": [
        "Jeg vet ikke hva dere vil gjore i dag.",
        "Dette er en vanlig setning pa bokmal.",
        "Hvordan kan jeg hjelpe dere med rapporten?",
        "Vi trenger noe mer tid for a fullfore jobben.",
        "Ikke glem at motet starter tidlig i morgen.",
        "Dere sa at denne planen virker ganske bra.",
        "Jeg har ikke sett noe lignende for.",
        "Hva tenker dere om denne losningen?",
        "Bokmal bruker ofte ikke og jeg i korte setninger.",
        "Vi kommer tilbake nar rapporten er ferdig.",
        "Han liker hvordan prosjektet utvikler seg.",
        "Dette huset ligger ikke langt fra stasjonen.",
    ],
    "nn": [
        "Eg veit ikkje kva de vil gjere i dag.",
        "Dette er ei vanleg setning pa nynorsk.",
        "Korleis kan eg hjelpe dykk med rapporten?",
        "Vi treng noko meir tid for a fullfore jobben.",
        "Ikkje gloym at motet startar tidleg i morgon.",
        "Dykk sa at denne planen verkar ganske bra.",
        "Eg har ikkje sett noko liknande for.",
        "Kva tenkjer de om denne loysinga?",
        "Nynorsk brukar ofte ikkje og eg i korte setningar.",
        "Vi kjem tilbake nar rapporten er ferdig.",
        "Han likar korleis prosjektet utviklar seg.",
        "Dette huset ligg ikkje langt fra stasjonen.",
    ],
}


def _normalize_lines(text):
    return [line.strip() for line in text if str(line).strip()]


def _read_existing(path):
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip()]


def apply_close_language_pack(mode="append", output_dir=CLOSE_PACK_DIR, languages=None):
    mode = "replace" if str(mode).strip().lower() == "replace" else "append"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_languages = [
        language
        for language in (languages or CLOSE_LANGUAGE_PACK.keys())
        if language in CLOSE_LANGUAGE_PACK and language in SUPPORTED_LANGUAGE_CODES
    ]

    summary = {
        "mode": mode,
        "output_dir": str(output_dir),
        "languages": {},
        "total_added": 0,
        "total_after": 0,
    }

    for language in selected_languages:
        path = output_dir / f"{language}.txt"
        previous = [] if mode == "replace" else _read_existing(path)
        pack_lines = _normalize_lines(CLOSE_LANGUAGE_PACK[language])
        merged = list(dict.fromkeys(previous + pack_lines))
        with open(path, "w", encoding="utf-8") as handle:
            for line in merged:
                handle.write(line + "\n")

        added = max(0, len(merged) - len(previous))
        summary["languages"][language] = {
            "pack_lines": len(pack_lines),
            "added": added,
            "total_lines": len(merged),
            "path": str(path),
        }
        summary["total_added"] += added
        summary["total_after"] += len(merged)

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Apply curated close-language corpus sentences."
    )
    parser.add_argument("--mode", default="append", choices=("append", "replace"))
    parser.add_argument(
        "--languages",
        nargs="*",
        default=None,
        help="Optional subset, e.g. bs hr sr nb nn",
    )
    args = parser.parse_args()
    result = apply_close_language_pack(mode=args.mode, languages=args.languages)
    print(result)


if __name__ == "__main__":
    main()
