from src.name_detector import STARTER_NAMES, clear_name_cache
from src.storage import upsert_name_hint


def seed_name_hints(overwrite=True):
    imported = 0
    for name, candidates in STARTER_NAMES.items():
        for candidate in candidates:
            upsert_name_hint(
                name,
                candidate["language"],
                country=candidate.get("country", ""),
                confidence=candidate.get("confidence", 0.9),
                enabled=True,
                source="seed",
                name_type=candidate.get("name_type", "person"),
                notes="Seeded editable name hint.",
            )
            imported += 1
    clear_name_cache()
    return {"imported": imported, "overwrite": overwrite}


def main():
    print(seed_name_hints())


if __name__ == "__main__":
    main()
