import json
from collections import Counter

from src.benchmark import run_benchmark
from src.config import EVALUATION_REPORT_PATH
from src.related_classifier import load_related_profiles
from src.related_languages import RELATED_LANGUAGE_GROUPS


def _load_json(path):
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _group_stats_from_languages(by_language, language_codes):
    languages = [code for code in language_codes if code in by_language]
    samples = sum(int(by_language[code].get("samples", 0) or 0) for code in languages)
    correct = sum(int(by_language[code].get("correct", 0) or 0) for code in languages)
    group_correct = sum(int(by_language[code].get("group_correct", by_language[code].get("correct", 0)) or 0) for code in languages)
    unknown = sum(int(by_language[code].get("unknown", 0) or 0) for code in languages)
    exact_accuracy = round(correct / samples, 4) if samples else 0.0
    group_accuracy = round(group_correct / samples, 4) if samples else 0.0
    return {
        "languages": languages,
        "samples": samples,
        "correct": correct,
        "group_correct": group_correct,
        "unknown": unknown,
        "accuracy": exact_accuracy,
        "group_accuracy": group_accuracy,
    }


def _group_confusions_from_evaluation(confusion, language_codes, group_id, limit=8):
    counts = Counter()
    language_set = set(language_codes)
    for expected in language_codes:
        for predicted, count in (confusion.get(expected, {}) or {}).items():
            if predicted == expected:
                continue
            if predicted in language_set:
                counts[(expected, predicted)] += int(count or 0)
            elif count:
                counts[(expected, predicted)] += int(count)
    rows = [
        {
            "group": group_id,
            "expected": expected,
            "predicted": predicted,
            "count": count,
        }
        for (expected, predicted), count in counts.most_common(limit)
    ]
    return rows


def _split_confusions(confusions, language_codes):
    language_set = set(language_codes)
    internal = []
    external = []
    for row in confusions:
        if row["predicted"] in language_set:
            internal.append(row)
        else:
            external.append(row)
    return internal, external


def _group_confusions_from_rows(rows, language_codes, group_id, limit=8):
    counts = Counter()
    language_set = set(language_codes)
    for row in rows:
        expected = row.get("expected")
        predicted = row.get("predicted")
        if expected not in language_set or predicted == expected:
            continue
        if predicted in language_set or predicted != expected:
            counts[(expected, predicted)] += 1
    return [
        {
            "group": group_id,
            "expected": expected,
            "predicted": predicted,
            "count": count,
        }
        for (expected, predicted), count in counts.most_common(limit)
    ]


def _group_markers(group_id, profiles, limit=8):
    group_profiles = profiles.get(group_id, {}) or {}
    markers = {}
    for language in RELATED_LANGUAGE_GROUPS[group_id]["languages"]:
        profile = group_profiles.get(language, {}) or {}
        marker_rows = profile.get("markers", []) or []
        tokens = []
        for item in marker_rows[:limit]:
            if isinstance(item, dict):
                label = item.get("label") or item.get("value") or item.get("token", "")
                tokens.append(str(label))
            else:
                tokens.append(str(item))
        markers[language] = [token for token in tokens if token]
    return markers


def _group_low_margin_cases(low_confidence_rows, language_codes, group_id, limit=8):
    cases = []
    language_set = set(language_codes)
    for row in low_confidence_rows or []:
        expected = row.get("expected")
        predicted = row.get("predicted")
        language_group = row.get("language_group")
        if expected not in language_set and predicted not in language_set and language_group != group_id:
            continue
        cases.append(
            {
                "group": group_id,
                "expected": expected,
                "predicted": predicted,
                "confidence": row.get("confidence", 0.0),
                "related_margin": row.get("related_margin"),
                "related_suggested_language": row.get("related_suggested_language", ""),
                "text": row.get("text", ""),
            }
        )

    cases.sort(
        key=lambda item: (
            item["related_margin"] is None,
            item["related_margin"] if item["related_margin"] is not None else 999.0,
            item["confidence"],
        )
    )
    return cases[:limit]


def related_language_report():
    evaluation = _load_json(EVALUATION_REPORT_PATH)
    profiles = load_related_profiles()
    source = "evaluation" if evaluation else "benchmark"
    if evaluation:
        by_language = evaluation.get("by_language", {})
        confusion = evaluation.get("confusion", {})
        low_confidence_rows = evaluation.get("low_confidence", [])
        group_summary = {}
        for group_id, group in RELATED_LANGUAGE_GROUPS.items():
            confusions = _group_confusions_from_evaluation(confusion, group["languages"], group_id)
            internal_confusions, external_confusions = _split_confusions(confusions, group["languages"])
            summary = _group_stats_from_languages(by_language, group["languages"])
            summary.update(
                {
                    "group": group_id,
                    "name": group["name"],
                    "note": group["note"],
                    "markers": _group_markers(group_id, profiles),
                    "confusions": confusions,
                    "internal_confusions": internal_confusions,
                    "external_confusions": external_confusions,
                    "low_margin_cases": _group_low_margin_cases(low_confidence_rows, group["languages"], group_id),
                }
            )
            group_summary[group_id] = summary
        total = {
            "samples": evaluation.get("samples", 0),
            "correct": evaluation.get("correct", 0),
            "group_correct": evaluation.get("group_correct", evaluation.get("correct", 0)),
            "unknown": evaluation.get("unknown", 0),
            "accuracy": evaluation.get("accuracy", 0),
            "group_accuracy": evaluation.get("group_accuracy", evaluation.get("accuracy", 0)),
        }
    else:
        benchmark = run_benchmark()
        by_group = {}
        for group_id, group in RELATED_LANGUAGE_GROUPS.items():
            confusions = _group_confusions_from_rows(benchmark.get("rows", []), group["languages"], group_id)
            internal_confusions, external_confusions = _split_confusions(confusions, group["languages"])
            by_group[group_id] = {
                "group": group_id,
                "name": group["name"],
                "note": group["note"],
                "languages": list(group["languages"]),
                "samples": 0,
                "correct": 0,
                "group_correct": 0,
                "unknown": 0,
                "accuracy": 0.0,
                "group_accuracy": 0.0,
                "markers": _group_markers(group_id, profiles),
                "confusions": confusions,
                "internal_confusions": internal_confusions,
                "external_confusions": external_confusions,
                "low_margin_cases": [],
            }
        for row in benchmark.get("rows", []):
            for group_id, group in RELATED_LANGUAGE_GROUPS.items():
                if row["expected"] in group["languages"]:
                    group_row = by_group[group_id]
                    group_row["samples"] += 1
                    group_row["correct"] += int(bool(row.get("correct")))
                    group_row["group_correct"] += int(bool(row.get("group_correct")))
                    group_row["unknown"] += int(row.get("predicted") == "unknown")
        for group_row in by_group.values():
            samples = group_row["samples"]
            group_row["accuracy"] = round(group_row["correct"] / samples, 4) if samples else 0.0
            group_row["group_accuracy"] = round(group_row["group_correct"] / samples, 4) if samples else 0.0
        group_summary = by_group
        total = {
            "samples": benchmark.get("samples", 0),
            "correct": benchmark.get("correct", 0),
            "group_correct": benchmark.get("group_correct", benchmark.get("correct", 0)),
            "unknown": benchmark.get("rows", 0) and sum(1 for row in benchmark.get("rows", []) if row.get("predicted") == "unknown"),
            "accuracy": benchmark.get("accuracy", 0),
            "group_accuracy": benchmark.get("group_accuracy", benchmark.get("accuracy", 0)),
        }

    ordered_groups = sorted(group_summary.values(), key=lambda item: (item["group"], item["name"]))
    return {
        "source": source,
        "total": total,
        "groups": ordered_groups,
        "confusions": [
            item
            for group in ordered_groups
            for item in group.get("confusions", [])
        ],
        "internal_confusions": [
            item
            for group in ordered_groups
            for item in group.get("internal_confusions", [])
        ],
        "external_confusions": [
            item
            for group in ordered_groups
            for item in group.get("external_confusions", [])
        ],
        "low_margin_cases": [
            item
            for group in ordered_groups
            for item in group.get("low_margin_cases", [])
        ],
    }
