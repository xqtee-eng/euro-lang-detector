RELATED_LANGUAGE_GROUPS = {
    "serbo_croatian": {
        "name": "Serbian / Croatian / Bosnian",
        "languages": ("bs", "hr", "sr"),
        "note": "These languages are mutually very close; short Latin-script text can be ambiguous.",
    },
    "norwegian": {
        "name": "Norwegian Bokmal / Nynorsk",
        "languages": ("nb", "nn"),
        "note": "Norwegian Bokmal and Nynorsk share much vocabulary; short text can be ambiguous.",
    },
    "east_slavic": {
        "name": "East Slavic (Belarusian / Ukrainian / Russian)",
        "languages": ("be", "uk", "ru"),
        "note": "Belarusian, Ukrainian, and Russian are related and share many characters; they are frequently confused.",
    },
}

LANGUAGE_TO_GROUP = {
    language: group_id
    for group_id, group in RELATED_LANGUAGE_GROUPS.items()
    for language in group["languages"]
}


def related_group_for(language):
    return LANGUAGE_TO_GROUP.get(str(language or "").lower())


def same_related_group(left, right):
    left_group = related_group_for(left)
    return bool(left_group and left_group == related_group_for(right))


def enrich_related_language_result(result):
    language = str(result.get("language", "")).lower()
    group_id = related_group_for(language)
    if not group_id or result.get("source") == "rule":
        return result

    group = RELATED_LANGUAGE_GROUPS[group_id]
    group_languages = tuple(group["languages"])
    candidates = result.get("candidates") or []
    group_candidates = [
        candidate
        for candidate in candidates
        if candidate.get("language") in group_languages
    ]

    if not group_candidates:
        group_candidates = [
            {
                "language": item,
                "confidence": (
                    result.get("confidence", 0.0) if item == language else 0.0
                ),
            }
            for item in group_languages
        ]

    top_confidence = float(result.get("confidence", 0.0) or 0.0)
    competing = [
        float(candidate.get("confidence", 0.0) or 0.0)
        for candidate in group_candidates
        if candidate.get("language") != language
    ]
    nearest_competitor = max(competing, default=0.0)
    ambiguous = (
        top_confidence < 0.95
        or nearest_competitor >= 0.12
        or (top_confidence - nearest_competitor) <= 0.35
    )

    result["language_group"] = group_id
    result["language_group_name"] = group["name"]
    result["possible_languages"] = list(group_languages)
    result["group_candidates"] = group_candidates
    result["group_reliability"] = "ambiguous" if ambiguous else "specific"
    result["ambiguous_group"] = bool(ambiguous)
    result["group_note"] = group["note"]

    if ambiguous:
        if result.get("reliability") == "high":
            result["reliability"] = "medium"
        result["warning"] = (
            "Closely related languages detected. Treat the exact label as a best guess, "
            "not a fully certain answer."
        )

    return result
