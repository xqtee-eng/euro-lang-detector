import json

from src.config import DATASET_PATH, TRAIN_DATASET_PATH
from src.storage import (
    AUTO_LEARNED_FEEDBACK_SOURCE,
    add_feedback,
    add_unknown,
    clear_review_storage as clear_review_storage_db,
    export_jsonl_backup,
    is_unknown_resolved as is_unknown_resolved_db,
    list_feedback,
    list_unknowns,
    mark_feedback_promoted,
    resolve_unknowns,
    storage_summary,
)


def queue_unknown(text, details=None):
    added = add_unknown(text, details=details)
    if added:
        export_jsonl_backup()


def is_unknown_resolved(text):
    return is_unknown_resolved_db(text)


def mark_unknown_resolved(texts, action="resolved"):
    if isinstance(texts, str):
        texts = [texts]
    removed = resolve_unknowns(texts, action=action)
    export_jsonl_backup()
    return removed


def list_unknown_items(limit=100):
    return list_unknowns(limit=limit)


def clear_unknown_items(texts=None, mark_resolved=True):
    action = "cleared" if texts is None else "resolved"
    if mark_resolved:
        removed = resolve_unknowns(texts, action=action)
    else:
        removed = clear_review_storage_db(include_resolved=False)["before"]["unknown"]
    export_jsonl_backup()
    return removed


def review_storage_summary():
    return storage_summary()


def clear_review_storage(
    include_resolved=False, include_feedback=False, include_learning=False
):
    result = clear_review_storage_db(
        include_resolved=include_resolved,
        include_feedback=include_feedback,
        include_learning=include_learning,
    )
    export_jsonl_backup()
    return result


def add_feedback_sample(text, lang, source="manual"):
    add_feedback(text, lang, source=source)
    export_jsonl_backup()


def promote_feedback_samples():
    rows = [
        row
        for row in list_feedback(unpromoted_only=True)
        if row.get("source") != AUTO_LEARNED_FEEDBACK_SOURCE
    ]
    if not rows:
        return 0

    DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    target_paths = [DATASET_PATH]
    if TRAIN_DATASET_PATH.exists():
        target_paths.append(TRAIN_DATASET_PATH)

    handles = [open(path, "a", encoding="utf-8") for path in target_paths]
    try:
        for row in rows:
            payload = {
                "text": row["text"],
                "lang": row["lang"],
                "source": row["source"],
            }
            line = json.dumps(payload, ensure_ascii=False)
            for handle in handles:
                handle.write(line + "\n")
    finally:
        for handle in handles:
            handle.close()

    mark_feedback_promoted([row["id"] for row in rows])
    export_jsonl_backup()
    return len(rows)
