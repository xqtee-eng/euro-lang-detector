import json
import re
from collections import defaultdict

from src.config import FREQUENCY_DIR, RELATED_MODEL_PATH, TRAIN_DATASET_PATH
from src.detector import cosine_similarity
from src.ngram import build_profile, generate_ngrams
from src.preprocessing import clean_text
from src.related_languages import RELATED_LANGUAGE_GROUPS, related_group_for

RELATED_PROFILE_SIZE = 2500
RELATED_TOKEN_PROFILE_SIZE = 800
RELATED_MARKER_LIMIT = 18
RELATED_MARKER_MIN_COUNT = 3
RELATED_MARKER_MIN_LENGTH = 3
MIN_REFINEMENT_MARGIN = 0.05
MIN_REFINEMENT_CONFIDENCE = 0.75
CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
LATIN_RE = re.compile(r"[A-Za-z\u00C0-\u024F]")
TOKEN_RE = re.compile(r"[^\W_]+(?:[-'][^\W_]+)?", flags=re.UNICODE)
MANUAL_GROUP_MARKERS = {
    "serbo_croatian": {
        "hr": [
            {"kind": "token", "value": "ovdje", "weight": 0.09},
            {"kind": "token", "value": "gdje", "weight": 0.09},
            {"kind": "token", "value": "uvijek", "weight": 0.09},
            {"kind": "token", "value": "lijep", "weight": 0.08},
            {"kind": "token", "value": "svijet", "weight": 0.08},
            {"kind": "substring", "value": "rije", "weight": 0.05},
            {"kind": "substring", "value": "mlije", "weight": 0.05},
        ],
        "sr": [
            {"kind": "token", "value": "ovde", "weight": 0.09},
            {"kind": "token", "value": "gde", "weight": 0.09},
            {"kind": "token", "value": "uvek", "weight": 0.09},
            {"kind": "token", "value": "lep", "weight": 0.08},
            {"kind": "token", "value": "svet", "weight": 0.08},
            {"kind": "token", "value": "devojka", "weight": 0.07},
            {"kind": "token", "value": "vreme", "weight": 0.06},
            {"kind": "phrase", "value": "treba da", "weight": 0.08},
        ],
        "bs": [
            {"kind": "token", "value": "hvala", "weight": 0.06},
            {"kind": "token", "value": "molim", "weight": 0.05},
            {"kind": "token", "value": "gdje", "weight": 0.05},
            {"kind": "token", "value": "ovdje", "weight": 0.05},
            {"kind": "token", "value": "kahva", "weight": 0.08},
            {"kind": "token", "value": "hiljada", "weight": 0.06},
            {"kind": "token", "value": "lahko", "weight": 0.07},
        ],
    },
    "norwegian": {
        "nb": [
            {"kind": "token", "value": "ikke", "weight": 0.09},
            {"kind": "token", "value": "jeg", "weight": 0.09},
            {"kind": "token", "value": "hva", "weight": 0.08},
            {"kind": "token", "value": "dere", "weight": 0.07},
            {"kind": "token", "value": "noe", "weight": 0.07},
            {"kind": "token", "value": "hvordan", "weight": 0.06},
        ],
        "nn": [
            {"kind": "token", "value": "ikkje", "weight": 0.09},
            {"kind": "token", "value": "eg", "weight": 0.09},
            {"kind": "token", "value": "kva", "weight": 0.08},
            {"kind": "token", "value": "dykk", "weight": 0.07},
            {"kind": "token", "value": "noko", "weight": 0.07},
            {"kind": "token", "value": "korleis", "weight": 0.06},
            {"kind": "token", "value": "sjølv", "weight": 0.06},
        ],
    },
    "east_slavic": {
        "be": [
            {"kind": "token", "value": "гэта", "weight": 0.08},
            {"kind": "token", "value": "ёсць", "weight": 0.08},
            {"kind": "token", "value": "няма", "weight": 0.06},
            {"kind": "token", "value": "дзякуй", "weight": 0.07},
            {"kind": "token", "value": "калі", "weight": 0.06},
            {"kind": "token", "value": "ласка", "weight": 0.06},
            {"kind": "token", "value": "чалавек", "weight": 0.05},
            {"kind": "substring", "value": "ў", "weight": 0.15},
            {"kind": "substring", "value": "быў", "weight": 0.10},
        ],
        "uk": [
            {"kind": "token", "value": "цього", "weight": 0.08},
            {"kind": "token", "value": "було", "weight": 0.07},
            {"kind": "token", "value": "дякую", "weight": 0.07},
            {"kind": "token", "value": "людина", "weight": 0.06},
            {"kind": "substring", "value": "ї", "weight": 0.12},
            {"kind": "substring", "value": "є", "weight": 0.10},
            {"kind": "substring", "value": "ць", "weight": 0.05},
        ],
        "ru": [
            {"kind": "token", "value": "это", "weight": 0.08},
            {"kind": "token", "value": "было", "weight": 0.07},
            {"kind": "token", "value": "спасибо", "weight": 0.07},
            {"kind": "token", "value": "человек", "weight": 0.06},
            {"kind": "substring", "value": "и", "weight": 0.05},
            {"kind": "substring", "value": "ы", "weight": 0.03},
        ],
    },
}


def _input_profile(text):
    grams = generate_ngrams(clean_text(text))
    counts = {}
    for gram in grams:
        counts[gram] = counts.get(gram, 0) + 1
    total = sum(counts.values())
    if not total:
        return {}
    return {key: value / total for key, value in counts.items()}


def _tokenize(text):
    return [
        token for token in re.findall(r"[\w'-]+", clean_text(text)) if len(token) >= 2
    ]


def _token_profile(texts, size=RELATED_TOKEN_PROFILE_SIZE):
    counts = {}
    for text in texts:
        for token in _tokenize(text):
            counts[token] = counts.get(token, 0) + 1

    total = sum(counts.values())
    if not total:
        return {}

    profile = {key: value / total for key, value in counts.items()}
    return dict(sorted(profile.items(), key=lambda item: item[1], reverse=True)[:size])


def _token_counts(texts):
    counts = {}
    for text in texts:
        for token in _tokenize(text):
            counts[token] = counts.get(token, 0) + 1
    return counts


def _is_marker_candidate(token):
    if len(token) < RELATED_MARKER_MIN_LENGTH:
        return False
    if any(char.isdigit() for char in token):
        return False
    return bool(TOKEN_RE.fullmatch(token))


def _dominant_script(text):
    value = clean_text(text)
    cyr = len(CYRILLIC_RE.findall(value))
    lat = len(LATIN_RE.findall(value))
    if cyr > lat * 1.2 and cyr > 0:
        return "cyrillic"
    if lat > cyr * 1.2 and lat > 0:
        return "latin"
    return None


def _token_markers(text):
    return set(_tokenize(text))


def _load_frequency_tokens(language, limit=600):
    path = FREQUENCY_DIR / f"{language}.tsv"
    if not path.exists():
        return {}

    counts = {}
    with open(path, "r", encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if index >= limit:
                break
            parts = line.rstrip("\n").split("\t")
            if not parts:
                continue
            token = clean_text(parts[0])
            if not _is_marker_candidate(token):
                continue
            counts[token] = counts.get(token, 0) + max(2, limit - index)
    return counts


def _merge_counts(base_counts, extra_counts):
    merged = dict(base_counts)
    for token, count in extra_counts.items():
        merged[token] = merged.get(token, 0) + int(count or 0)
    return merged


def _distinctive_markers(group_token_counts, limit=RELATED_MARKER_LIMIT):
    totals = {
        language: max(1, sum(counts.values()))
        for language, counts in group_token_counts.items()
    }
    results = {}

    for language, counts in group_token_counts.items():
        ranked = []
        own_total = totals[language]
        for token, count in counts.items():
            if count < RELATED_MARKER_MIN_COUNT or not _is_marker_candidate(token):
                continue

            own_freq = count / own_total
            other_freqs = []
            other_count = 0
            for other_language, other_counts in group_token_counts.items():
                if other_language == language:
                    continue
                other_total = totals[other_language]
                value = int(other_counts.get(token, 0) or 0)
                other_count += value
                other_freqs.append(value / other_total if other_total else 0.0)

            max_other_freq = max(other_freqs, default=0.0)
            if own_freq <= max_other_freq:
                continue

            score = (own_freq - max_other_freq) + (0.35 * own_freq)
            if other_count == 0:
                score += 0.01
            weight = min(0.12, 0.025 + score * 18)
            ranked.append(
                {
                    "token": token,
                    "count": int(count),
                    "score": round(score, 5),
                    "weight": round(weight, 4),
                }
            )

        ranked.sort(
            key=lambda item: (item["score"], item["count"], len(item["token"])),
            reverse=True,
        )
        results[language] = ranked[:limit]

    return results


def _profile_markers(profile):
    if not isinstance(profile, dict):
        return []
    markers = profile.get("markers", [])
    if markers and isinstance(markers[0], str):
        return [
            {
                "kind": "token",
                "value": token,
                "label": token,
                "weight": 0.04,
                "source": "legacy",
            }
            for token in markers
        ]
    return markers


def _marker_label(marker):
    if not isinstance(marker, dict):
        return str(marker)
    label = marker.get("label")
    if label:
        return str(label)
    kind = marker.get("kind", "token")
    value = str(marker.get("value", "")).strip()
    if kind == "substring":
        return f"*{value}*"
    if kind == "phrase":
        return f'"{value}"'
    return value


def _manual_markers(group_id, language):
    raw_items = MANUAL_GROUP_MARKERS.get(group_id, {}).get(language, [])
    items = []
    for item in raw_items:
        value = clean_text(item.get("value", ""))
        if not value:
            continue
        kind = item.get("kind", "token")
        items.append(
            {
                "kind": kind,
                "value": value,
                "label": _marker_label({"kind": kind, "value": value}),
                "weight": round(float(item.get("weight", 0.05)), 4),
                "source": "manual",
            }
        )
    return items


def _merge_marker_lists(manual_markers, learned_markers, limit=RELATED_MARKER_LIMIT):
    merged = []
    seen = set()
    for marker in list(manual_markers) + list(learned_markers):
        if isinstance(marker, dict):
            kind = marker.get("kind", "token")
            value = clean_text(marker.get("value", marker.get("token", "")))
            if not value:
                continue
            key = (kind, value)
            if key in seen:
                continue
            merged.append(
                {
                    "kind": kind,
                    "value": value,
                    "label": marker.get("label")
                    or _marker_label({"kind": kind, "value": value}),
                    "weight": round(float(marker.get("weight", 0.04)), 4),
                    "source": marker.get("source", "learned"),
                }
            )
            seen.add(key)
        else:
            value = clean_text(str(marker))
            key = ("token", value)
            if not value or key in seen:
                continue
            merged.append(
                {
                    "kind": "token",
                    "value": value,
                    "label": value,
                    "weight": 0.04,
                    "source": "learned",
                }
            )
            seen.add(key)
        if len(merged) >= limit:
            break
    return merged


def _marker_bonus(language, text, group_id, marker_map=None):
    tokens = _token_markers(text)
    lowered = clean_text(text)
    bonus = 0.0
    marker_map = marker_map or {}

    for marker in marker_map.get(language, []):
        if isinstance(marker, dict):
            kind = marker.get("kind", "token")
            value = clean_text(marker.get("value", marker.get("token", "")))
            weight = float(marker.get("weight", 0.04))
        else:
            kind = "token"
            value = clean_text(str(marker))
            weight = 0.04
        if not value:
            continue
        if kind == "token" and value in tokens:
            bonus += weight
        elif kind in {"substring", "phrase"} and value in lowered:
            bonus += weight

    if group_id == "serbo_croatian":
        if language == "sr" and any(
            char in lowered for char in "\u0459\u045a\u0452\u045b\u045f"
        ):
            bonus += 0.10
        if language == "hr" and "ije" in lowered:
            bonus += 0.01
    elif group_id == "norwegian":
        if language == "nn" and any(char in lowered for char in "\u00e6\u00f8\u00e5"):
            bonus += 0.03
        if language == "nb" and any(char in lowered for char in "\u00e6\u00f8\u00e5"):
            bonus -= 0.01

    return bonus


def save_related_profiles(profiles, path=RELATED_MODEL_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(profiles, handle, ensure_ascii=False, indent=2)


def load_related_profiles(path=RELATED_MODEL_PATH):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return {}


def train_related_classifiers(
    dataset_path=TRAIN_DATASET_PATH, save_path=RELATED_MODEL_PATH
):
    grouped_texts = {
        group_id: defaultdict(list) for group_id in RELATED_LANGUAGE_GROUPS
    }
    grouped_token_counts = {
        group_id: defaultdict(dict) for group_id in RELATED_LANGUAGE_GROUPS
    }

    if not dataset_path.exists():
        return {}

    with open(dataset_path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            language = str(row.get("lang", "")).lower()
            group_id = related_group_for(language)
            text = clean_text(row.get("text", ""))
            if group_id and text:
                grouped_texts[group_id][language].append(text)

    profiles = {}
    for group_id, language_texts in grouped_texts.items():
        group_profiles = {}
        for language, texts in sorted(language_texts.items()):
            if texts:
                token_counts = _merge_counts(
                    _token_counts(texts), _load_frequency_tokens(language)
                )
                grouped_token_counts[group_id][language] = token_counts
                group_profiles[language] = {
                    "char": build_profile(texts, size=RELATED_PROFILE_SIZE),
                    "token": _token_profile(texts, size=RELATED_TOKEN_PROFILE_SIZE),
                    "script": _dominant_script(" ".join(texts)),
                }

        marker_map = (
            _distinctive_markers(grouped_token_counts[group_id])
            if group_profiles
            else {}
        )
        for language, profile in group_profiles.items():
            manual_markers = _manual_markers(group_id, language)
            learned_markers = [
                {
                    "kind": "token",
                    "value": item["token"],
                    "label": item["token"],
                    "weight": item["weight"],
                    "source": "learned",
                }
                for item in marker_map.get(language, [])
            ]
            profile["markers"] = _merge_marker_lists(manual_markers, learned_markers)

        if group_profiles:
            profiles[group_id] = group_profiles

    save_related_profiles(profiles, path=save_path)
    return profiles


def rank_related_languages(text, group_id, top_k=3):
    profiles = load_related_profiles().get(group_id, {})
    input_profile = _input_profile(text)
    input_token_profile = _token_profile([text])
    script = _dominant_script(text)
    if not profiles or not input_profile:
        return []

    marker_map = {
        language: _profile_markers(profile)
        for language, profile in profiles.items()
        if isinstance(profile, dict)
    }
    ranked = []
    for language, profile in profiles.items():
        if "char" in profile:
            char_profile = profile.get("char") or {}
            token_profile = profile.get("token") or {}
            char_score = (
                cosine_similarity(input_profile, char_profile) if char_profile else 0.0
            )
            token_score = (
                cosine_similarity(input_token_profile, token_profile)
                if token_profile
                else 0.0
            )
        else:
            char_profile = profile
            token_profile = {}
            char_score = cosine_similarity(input_profile, char_profile)
            token_score = 0.0

        score = 0.72 * float(char_score) + 0.28 * float(token_score)

        if group_id == "serbo_croatian" and script == "cyrillic":
            if language == "sr":
                score += 0.12
            else:
                score -= 0.04
        elif group_id == "serbo_croatian" and script == "latin":
            if language in {"bs", "hr"}:
                score += 0.02
        elif group_id == "norwegian" and token_profile:
            if language == "nn" and any(
                token in input_token_profile
                for token in {"ikkje", "eg", "kva", "me", "dei"}
            ):
                score += 0.08
            if language == "nb" and any(
                token in input_token_profile
                for token in {"ikke", "jeg", "hva", "vi", "dere"}
            ):
                score += 0.08

        score += _marker_bonus(language, text, group_id, marker_map=marker_map)

        ranked.append(
            {
                "language": language,
                "confidence": round(max(0.0, score), 4),
                "char_confidence": round(float(char_score), 4),
                "token_confidence": round(float(token_score), 4),
                "script": profile.get("script") if isinstance(profile, dict) else None,
                "markers": (
                    _profile_markers(profile)[:6] if isinstance(profile, dict) else []
                ),
                "marker_labels": (
                    [_marker_label(item) for item in _profile_markers(profile)[:6]]
                    if isinstance(profile, dict)
                    else []
                ),
            }
        )
    ranked.sort(key=lambda item: item["confidence"], reverse=True)
    return ranked[: max(1, top_k)]


def refine_related_language_result(result, text):
    language = str(result.get("language", "")).lower()
    group_id = related_group_for(language)
    if not group_id or result.get("source") == "rule":
        return result

    ranked = rank_related_languages(
        text, group_id, top_k=len(RELATED_LANGUAGE_GROUPS[group_id]["languages"])
    )
    if not ranked:
        return result

    best = ranked[0]
    runner_up = ranked[1]["confidence"] if len(ranked) > 1 else 0.0
    margin = float(best["confidence"]) - float(runner_up)
    base_candidates = result.get("candidates") or []
    group_candidates_source = [
        candidate
        for candidate in base_candidates
        if candidate.get("language") in RELATED_LANGUAGE_GROUPS[group_id]["languages"]
    ]

    result["related_classifier"] = {
        "group": group_id,
        "candidates": ranked,
        "margin": round(margin, 4),
        "suggested_language": best["language"],
        "source_candidates": group_candidates_source,
        "applied": False,
    }

    if (
        best["language"] != language
        and margin >= MIN_REFINEMENT_MARGIN
        and float(best["confidence"]) >= MIN_REFINEMENT_CONFIDENCE
    ):
        original_language = language
        result["language"] = best["language"]
        result["confidence"] = max(
            float(result.get("confidence", 0.0) or 0.0), float(best["confidence"])
        )
        result["source"] = f"{result.get('source', 'detector')}+related"
        result["reason"] = "related_classifier_refinement"
        result["original_language"] = original_language
        result["related_classifier"]["applied"] = True

    return result
