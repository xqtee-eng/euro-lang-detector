import json
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from src.config import (
    DATABASE_PATH,
    DATASET_PATH,
    EVALUATION_REPORT_PATH,
    FEEDBACK_PATH,
    LEXICON_DIR,
    MODEL_PATH,
    MODEL_SNAPSHOT_DIR,
    NAME_DIR,
    RESOLVED_UNKNOWN_PATH,
    TEST_DATASET_PATH,
    TRAIN_DATASET_PATH,
    UNKNOWN_PATH,
)
from src.utils import fast_count_lines, read_jsonl_gen, write_jsonl


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db():
    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL DEFAULT 'reviewer',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS unknown_texts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL UNIQUE,
                count INTEGER NOT NULL DEFAULT 1,
                details_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'active',
                action TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                resolved_at TEXT
            );

            CREATE TABLE IF NOT EXISTS feedback_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                lang TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual',
                promoted INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                promoted_at TEXT
            );

            CREATE TABLE IF NOT EXISTS lexicon_words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                language TEXT NOT NULL,
                word TEXT NOT NULL,
                frequency INTEGER NOT NULL DEFAULT 1,
                enabled INTEGER NOT NULL DEFAULT 1,
                source TEXT NOT NULL DEFAULT 'user',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(language, word)
            );

            CREATE TABLE IF NOT EXISTS name_hints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                language TEXT NOT NULL,
                country TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0.9,
                name_type TEXT NOT NULL DEFAULT 'person',
                enabled INTEGER NOT NULL DEFAULT 1,
                source TEXT NOT NULL DEFAULT 'user',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(name, language)
            );

            CREATE TABLE IF NOT EXISTS training_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL DEFAULT 'evaluate',
                samples INTEGER NOT NULL DEFAULT 0,
                correct INTEGER NOT NULL DEFAULT 0,
                unknown INTEGER NOT NULL DEFAULT 0,
                accuracy REAL NOT NULL DEFAULT 0,
                report_path TEXT,
                model_snapshot_path TEXT,
                notes TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS active_learning_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL UNIQUE,
                suggested_language TEXT NOT NULL DEFAULT 'unknown',
                confidence REAL NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT 'unknown',
                reason TEXT,
                candidates_json TEXT NOT NULL DEFAULT '[]',
                priority INTEGER NOT NULL DEFAULT 0,
                count INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'active',
                action TEXT,
                resolved_language TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                resolved_at TEXT
            );

            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """)
        db.execute(
            """
            INSERT OR IGNORE INTO users(username, role, created_at)
            VALUES (?, ?, ?)
            """,
            ("local-admin", "admin", utc_now()),
        )
        _ensure_column(db, "training_runs", "model_snapshot_path", "TEXT")
        _ensure_column(db, "lexicon_words", "frequency", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(db, "lexicon_words", "notes", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "name_hints", "name_type", "TEXT NOT NULL DEFAULT 'person'")
        _ensure_column(db, "name_hints", "notes", "TEXT NOT NULL DEFAULT ''")


def _ensure_column(db, table, column, definition):
    rows = db.execute(f"PRAGMA table_info({table})").fetchall()
    if column not in {row["name"] for row in rows}:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def add_unknown(text, details=None):
    init_db()
    value = str(text or "").strip()
    if not value or is_unknown_resolved(value):
        return False

    now = utc_now()
    details_json = json.dumps(details or {}, ensure_ascii=False)
    with connect() as db:
        db.execute(
            """
            INSERT INTO unknown_texts(text, count, details_json, status, created_at, updated_at)
            VALUES (?, 1, ?, 'active', ?, ?)
            ON CONFLICT(text) DO UPDATE SET
                count = count + 1,
                details_json = excluded.details_json,
                status = 'active',
                updated_at = excluded.updated_at
            """,
            (value, details_json, now, now),
        )
    return True


def is_unknown_resolved(text):
    init_db()
    value = str(text or "").strip()
    if not value:
        return True
    with connect() as db:
        row = db.execute(
            "SELECT status FROM unknown_texts WHERE text = ?",
            (value,),
        ).fetchone()
    return bool(row and row["status"] != "active")


def list_unknowns(limit=100):
    init_db()
    with connect() as db:
        rows = db.execute(
            """
            SELECT text, count, details_json
            FROM unknown_texts
            WHERE status = 'active'
            ORDER BY count DESC, text ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "text": row["text"],
            "count": row["count"],
            "details": json.loads(row["details_json"] or "{}"),
        }
        for row in rows
    ]


def resolve_unknowns(texts=None, action="resolved"):
    init_db()
    now = utc_now()
    with connect() as db:
        if texts is None:
            cursor = db.execute(
                """
                UPDATE unknown_texts
                SET status = 'resolved', action = ?, resolved_at = ?, updated_at = ?
                WHERE status = 'active'
                """,
                (action, now, now),
            )
            return cursor.rowcount

        normalized = [
            str(text or "").strip() for text in texts if str(text or "").strip()
        ]
        removed = 0
        for text in normalized:
            cursor = db.execute(
                """
                UPDATE unknown_texts
                SET status = 'resolved', action = ?, resolved_at = ?, updated_at = ?
                WHERE text = ? AND status = 'active'
                """,
                (action, now, now, text),
            )
            if cursor.rowcount == 0:
                db.execute(
                    """
                    INSERT OR IGNORE INTO unknown_texts(
                        text, count, details_json, status, action, created_at, updated_at, resolved_at
                    )
                    VALUES (?, 0, '{}', 'resolved', ?, ?, ?, ?)
                    """,
                    (text, action, now, now, now),
                )
            removed += cursor.rowcount
        return removed


def add_feedback(text, lang, source="manual"):
    init_db()
    with connect() as db:
        db.execute(
            """
            INSERT INTO feedback_samples(text, lang, source, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                str(text or "").strip(),
                str(lang or "").strip().lower(),
                source,
                utc_now(),
            ),
        )


def list_feedback(unpromoted_only=False):
    init_db()
    query = "SELECT id, text, lang, source, promoted, created_at FROM feedback_samples"
    params = ()
    if unpromoted_only:
        query += " WHERE promoted = 0"
    query += " ORDER BY id ASC"
    with connect() as db:
        rows = db.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def mark_feedback_promoted(ids):
    if not ids:
        return 0
    init_db()
    now = utc_now()
    with connect() as db:
        cursor = db.executemany(
            "UPDATE feedback_samples SET promoted = 1, promoted_at = ? WHERE id = ?",
            [(now, item_id) for item_id in ids],
        )
    return cursor.rowcount


def upsert_lexicon_word(
    language, word, enabled=True, source="user", frequency=1, notes=""
):
    init_db()
    language = str(language or "").strip().lower()
    word = str(word or "").strip().lower()
    if not language or not word:
        raise ValueError("Language and word are required.")
    frequency = max(1, int(frequency or 1))
    now = utc_now()
    with connect() as db:
        db.execute(
            """
            INSERT INTO lexicon_words(language, word, frequency, enabled, source, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(language, word) DO UPDATE SET
                frequency = MAX(lexicon_words.frequency, excluded.frequency),
                enabled = excluded.enabled,
                source = excluded.source,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                language,
                word,
                frequency,
                int(enabled),
                source,
                str(notes or "").strip(),
                now,
                now,
            ),
        )
    return {"language": language, "word": word, "frequency": frequency}


def bulk_upsert_lexicon_words(rows):
    init_db()
    now = utc_now()
    prepared = []
    for row in rows:
        language = str(row.get("language") or "").strip().lower()
        word = str(row.get("word") or "").strip().lower()
        if not language or not word:
            continue
        prepared.append(
            (
                language,
                word,
                max(1, int(row.get("frequency") or 1)),
                int(bool(row.get("enabled", True))),
                str(row.get("source") or "user").strip(),
                str(row.get("notes") or "").strip(),
                now,
                now,
            )
        )

    if not prepared:
        return 0

    with connect() as db:
        db.executemany(
            """
            INSERT INTO lexicon_words(language, word, frequency, enabled, source, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(language, word) DO UPDATE SET
                frequency = MAX(lexicon_words.frequency, excluded.frequency),
                enabled = excluded.enabled,
                source = excluded.source,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            prepared,
        )
    return len(prepared)


def set_lexicon_word_enabled(language, word, enabled):
    return upsert_lexicon_word(language, word, enabled=enabled, source="user")


def list_lexicon_rows(query="", language=None, enabled_only=True):
    init_db()
    clauses = []
    params = []
    if enabled_only:
        clauses.append("enabled = 1")
    if language:
        clauses.append("language = ?")
        params.append(str(language).strip().lower())
    if query:
        clauses.append("word LIKE ?")
        params.append(f"%{str(query).strip().lower()}%")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as db:
        rows = db.execute(
            f"""
            SELECT language, word, frequency, enabled, source, notes
            FROM lexicon_words
            {where}
            ORDER BY language, word
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def upsert_name_hint(
    name,
    language,
    country="",
    confidence=0.9,
    enabled=True,
    source="user",
    name_type="person",
    notes="",
):
    init_db()
    name = str(name or "").strip().lower()
    language = str(language or "").strip().lower()
    if not name or not language:
        raise ValueError("Name and language are required.")
    name_type = str(name_type or "person").strip().lower() or "person"
    now = utc_now()
    with connect() as db:
        db.execute(
            """
            INSERT INTO name_hints(name, language, country, confidence, name_type, enabled, source, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name, language) DO UPDATE SET
                country = excluded.country,
                confidence = excluded.confidence,
                name_type = excluded.name_type,
                enabled = excluded.enabled,
                source = excluded.source,
                notes = excluded.notes,
                updated_at = excluded.updated_at
            """,
            (
                name,
                language,
                str(country or "").strip(),
                float(confidence or 0.9),
                name_type,
                int(enabled),
                source,
                str(notes or "").strip(),
                now,
                now,
            ),
        )
    return {
        "name": name,
        "language": language,
        "country": country,
        "confidence": float(confidence or 0.9),
        "name_type": name_type,
    }


def set_name_hint_enabled(name, language, enabled):
    init_db()
    name = str(name or "").strip().lower()
    language = str(language or "").strip().lower()
    now = utc_now()
    with connect() as db:
        cursor = db.execute(
            """
            UPDATE name_hints
            SET enabled = ?, updated_at = ?
            WHERE name = ? AND language = ?
            """,
            (int(enabled), now, name, language),
        )
        if cursor.rowcount == 0:
            db.execute(
                """
                INSERT INTO name_hints(name, language, enabled, source, created_at, updated_at)
                VALUES (?, ?, ?, 'user', ?, ?)
                """,
                (name, language, int(enabled), now, now),
            )
    return {"name": name, "language": language}


def list_name_rows(query="", language=None, enabled_only=True):
    init_db()
    clauses = []
    params = []
    if enabled_only:
        clauses.append("enabled = 1")
    if language:
        clauses.append("language = ?")
        params.append(str(language).strip().lower())
    if query:
        clauses.append("name LIKE ?")
        params.append(f"%{str(query).strip().lower()}%")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as db:
        rows = db.execute(
            f"""
            SELECT name, language, country, confidence, name_type, enabled, source, notes
            FROM name_hints
            {where}
            ORDER BY name, language
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def _safe_timestamp():
    return utc_now().replace(":", "").replace("-", "").replace("+", "Z")


def create_model_snapshot(label="model"):
    if not MODEL_PATH.exists():
        return ""
    MODEL_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    safe_label = "".join(
        char if char.isalnum() or char in ("-", "_") else "_" for char in label
    )
    snapshot_path = (
        MODEL_SNAPSHOT_DIR / f"{_safe_timestamp()}_{safe_label}.profiles.json"
    )
    shutil.copy2(MODEL_PATH, snapshot_path)
    return str(snapshot_path)


def record_training_run(
    kind,
    samples,
    correct,
    unknown,
    accuracy,
    report_path="",
    model_snapshot_path="",
    notes="",
):
    init_db()
    with connect() as db:
        cursor = db.execute(
            """
            INSERT INTO training_runs(
                kind, samples, correct, unknown, accuracy, report_path,
                model_snapshot_path, notes, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                kind,
                int(samples or 0),
                int(correct or 0),
                int(unknown or 0),
                float(accuracy or 0),
                str(report_path or ""),
                str(model_snapshot_path or ""),
                str(notes or ""),
                utc_now(),
            ),
        )
        return cursor.lastrowid


def list_training_runs(limit=100):
    init_db()
    with connect() as db:
        rows = db.execute(
            """
            SELECT id, kind, samples, correct, unknown, accuracy, report_path,
                   model_snapshot_path, notes, created_at
            FROM training_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        snapshot_path = item.get("model_snapshot_path") or ""
        item["rollback_available"] = bool(
            snapshot_path and Path(snapshot_path).exists()
        )
        result.append(item)
    return result


def rollback_model_to_run(run_id):
    init_db()
    with connect() as db:
        row = db.execute(
            """
            SELECT id, model_snapshot_path
            FROM training_runs
            WHERE id = ?
            """,
            (int(run_id),),
        ).fetchone()
    if not row:
        raise ValueError(f"Training run not found: {run_id}")

    snapshot_path = Path(row["model_snapshot_path"] or "")
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Snapshot not found for run {run_id}: {snapshot_path}")

    backup_path = create_model_snapshot(label="before_rollback")
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(snapshot_path, MODEL_PATH)
    record_training_run(
        kind="rollback",
        samples=0,
        correct=0,
        unknown=0,
        accuracy=0,
        model_snapshot_path=str(snapshot_path),
        notes=f"Rolled back to run {run_id}. Previous model backup: {backup_path}",
    )
    return {
        "run_id": int(run_id),
        "snapshot": str(snapshot_path),
        "backup": backup_path,
    }


def _candidate_gap(candidates):
    if not candidates or len(candidates) < 2:
        return None
    ordered = sorted(
        candidates,
        key=lambda item: float(item.get("confidence", 0.0)),
        reverse=True,
    )
    return float(ordered[0].get("confidence", 0.0)) - float(
        ordered[1].get("confidence", 0.0)
    )


def active_learning_priority(result):
    language = result.get("language", "unknown")
    confidence = float(result.get("confidence", 0.0))
    reason = result.get("reason", "")
    reliability = result.get("reliability", "")
    candidates = result.get("name_candidates") or result.get("candidates") or []
    gap = _candidate_gap(candidates)

    if language == "unknown":
        return 95
    if "ambiguous" in str(reason):
        return 90
    if reliability == "low" or confidence < 0.45:
        return 80
    if gap is not None and gap <= 0.10:
        return 70
    if reliability == "medium" and gap is not None and gap <= 0.20:
        return 55
    return 0


def add_active_learning_item(text, result):
    init_db()
    value = str(text or "").strip()
    if not value:
        return False

    priority = active_learning_priority(result)
    if priority <= 0:
        return False

    now = utc_now()
    candidates = result.get("name_candidates") or result.get("candidates") or []
    with connect() as db:
        db.execute(
            """
            INSERT INTO active_learning_items(
                text, suggested_language, confidence, source, reason, candidates_json,
                priority, count, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'active', ?, ?)
            ON CONFLICT(text) DO UPDATE SET
                suggested_language = excluded.suggested_language,
                confidence = excluded.confidence,
                source = excluded.source,
                reason = excluded.reason,
                candidates_json = excluded.candidates_json,
                priority = MAX(active_learning_items.priority, excluded.priority),
                count = active_learning_items.count + 1,
                status = 'active',
                updated_at = excluded.updated_at
            """,
            (
                value,
                result.get("language", "unknown"),
                float(result.get("confidence", 0.0)),
                result.get("source", "unknown"),
                result.get("reason"),
                json.dumps(candidates, ensure_ascii=False),
                priority,
                now,
                now,
            ),
        )
    return True


def list_active_learning_items(limit=100):
    init_db()
    with connect() as db:
        rows = db.execute(
            """
            SELECT id, text, suggested_language, confidence, source, reason,
                   candidates_json, priority, count, updated_at
            FROM active_learning_items
            WHERE status = 'active'
            ORDER BY priority DESC, count DESC, updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            **dict(row),
            "candidates": json.loads(row["candidates_json"] or "[]"),
        }
        for row in rows
    ]


def resolve_active_learning_item(item_id, action="resolved", language=None):
    init_db()
    now = utc_now()
    with connect() as db:
        row = db.execute(
            "SELECT id, text FROM active_learning_items WHERE id = ?",
            (int(item_id),),
        ).fetchone()
        if not row:
            return None
        db.execute(
            """
            UPDATE active_learning_items
            SET status = 'resolved',
                action = ?,
                resolved_language = ?,
                resolved_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (action, language, now, now, int(item_id)),
        )
    return dict(row)


def clear_active_learning_items(include_resolved=False):
    init_db()
    with connect() as db:
        if include_resolved:
            cursor = db.execute("DELETE FROM active_learning_items")
        else:
            cursor = db.execute(
                "DELETE FROM active_learning_items WHERE status = 'active'"
            )
    return cursor.rowcount


def storage_summary():
    init_db()
    with connect() as db:
        return {
            "database": str(DATABASE_PATH),
            "unknown": db.execute(
                "SELECT COALESCE(SUM(count), 0) FROM unknown_texts WHERE status = 'active'"
            ).fetchone()[0],
            "resolved_unknown": db.execute(
                "SELECT COUNT(*) FROM unknown_texts WHERE status != 'active'"
            ).fetchone()[0],
            "feedback": db.execute(
                "SELECT COUNT(*) FROM feedback_samples WHERE promoted = 0"
            ).fetchone()[0],
            "feedback_total": db.execute(
                "SELECT COUNT(*) FROM feedback_samples"
            ).fetchone()[0],
            "active_learning": db.execute(
                "SELECT COUNT(*) FROM active_learning_items WHERE status = 'active'"
            ).fetchone()[0],
            "lexicon_words": db.execute(
                "SELECT COUNT(*) FROM lexicon_words WHERE enabled = 1"
            ).fetchone()[0],
            "name_hints": db.execute(
                "SELECT COUNT(*) FROM name_hints WHERE enabled = 1"
            ).fetchone()[0],
            "training_runs": db.execute(
                "SELECT COUNT(*) FROM training_runs"
            ).fetchone()[0],
            "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        }


def _latest_evaluation_report():
    if not EVALUATION_REPORT_PATH.exists():
        return {}
    with open(EVALUATION_REPORT_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def admin_dashboard_stats():
    init_db()
    summary = storage_summary()
    evaluation = _latest_evaluation_report()

    with connect() as db:
        recent_feedback = [dict(row) for row in db.execute("""
                SELECT id, text, lang, source, promoted, created_at
                FROM feedback_samples
                ORDER BY id DESC
                LIMIT 10
                """)]
        recent_unknowns = [
            {
                **dict(row),
                "details": json.loads(row["details_json"] or "{}"),
            }
            for row in db.execute("""
                SELECT text, count, details_json, status, action, updated_at
                FROM unknown_texts
                ORDER BY updated_at DESC
                LIMIT 10
                """)
        ]
        recent_training_runs = list_training_runs(limit=10)
        recent_learning_items = [
            {
                **dict(row),
                "candidates": json.loads(row["candidates_json"] or "[]"),
            }
            for row in db.execute("""
                SELECT id, text, suggested_language, confidence, source, reason,
                       candidates_json, priority, count, updated_at
                FROM active_learning_items
                WHERE status = 'active'
                ORDER BY priority DESC, count DESC, updated_at DESC
                LIMIT 10
                """)
        ]
        lexicon_by_language = [dict(row) for row in db.execute("""
                SELECT language, COUNT(*) AS count
                FROM lexicon_words
                WHERE enabled = 1
                GROUP BY language
                ORDER BY language
                """)]
        names_by_language = [dict(row) for row in db.execute("""
                SELECT language, COUNT(*) AS count
                FROM name_hints
                WHERE enabled = 1
                GROUP BY language
                ORDER BY language
                """)]

    dataset = {
        "dataset_rows": fast_count_lines(DATASET_PATH),
        "train_rows": fast_count_lines(TRAIN_DATASET_PATH),
        "test_rows": fast_count_lines(TEST_DATASET_PATH),
        "raw_language_files": (
            len(list((DATABASE_PATH.parent / "raw").glob("*.txt")))
            if (DATABASE_PATH.parent / "raw").exists()
            else 0
        ),
    }

    files = {
        "database": {
            "path": str(DATABASE_PATH),
            "exists": DATABASE_PATH.exists(),
            "size_bytes": DATABASE_PATH.stat().st_size if DATABASE_PATH.exists() else 0,
        },
        "profiles": {
            "path": str(MODEL_PATH),
            "exists": MODEL_PATH.exists(),
            "size_bytes": MODEL_PATH.stat().st_size if MODEL_PATH.exists() else 0,
        },
        "evaluation_report": {
            "path": str(EVALUATION_REPORT_PATH),
            "exists": EVALUATION_REPORT_PATH.exists(),
            "size_bytes": (
                EVALUATION_REPORT_PATH.stat().st_size
                if EVALUATION_REPORT_PATH.exists()
                else 0
            ),
        },
        "dataset": {
            "path": str(DATASET_PATH),
            "exists": DATASET_PATH.exists(),
            "size_bytes": DATASET_PATH.stat().st_size if DATASET_PATH.exists() else 0,
        },
        "train": {
            "path": str(TRAIN_DATASET_PATH),
            "exists": TRAIN_DATASET_PATH.exists(),
            "size_bytes": (
                TRAIN_DATASET_PATH.stat().st_size if TRAIN_DATASET_PATH.exists() else 0
            ),
        },
        "test": {
            "path": str(TEST_DATASET_PATH),
            "exists": TEST_DATASET_PATH.exists(),
            "size_bytes": (
                TEST_DATASET_PATH.stat().st_size if TEST_DATASET_PATH.exists() else 0
            ),
        },
    }

    latest_accuracy = evaluation.get("accuracy")
    latest_samples = evaluation.get("samples")
    latest_unknown = evaluation.get("unknown")

    return {
        "summary": summary,
        "dataset": dataset,
        "latest_evaluation": {
            "accuracy": latest_accuracy,
            "samples": latest_samples,
            "unknown": latest_unknown,
            "report_path": str(EVALUATION_REPORT_PATH),
        },
        "files": files,
        "recent_feedback": recent_feedback,
        "recent_unknowns": recent_unknowns,
        "recent_training_runs": recent_training_runs,
        "recent_learning_items": recent_learning_items,
        "lexicon_by_language": lexicon_by_language,
        "names_by_language": names_by_language,
    }


def clear_review_storage(
    include_resolved=False, include_feedback=False, include_learning=False
):
    init_db()
    before = storage_summary()
    with connect() as db:
        db.execute("DELETE FROM unknown_texts WHERE status = 'active'")
        if include_resolved:
            db.execute("DELETE FROM unknown_texts WHERE status != 'active'")
        if include_feedback:
            db.execute("DELETE FROM feedback_samples")
        if include_learning:
            if include_resolved:
                db.execute("DELETE FROM active_learning_items")
            else:
                db.execute("DELETE FROM active_learning_items WHERE status = 'active'")
    after = storage_summary()
    return {"before": before, "after": after}


def _get_meta(key):
    with connect() as db:
        row = db.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _set_meta(key, value):
    with connect() as db:
        db.execute(
            """
            INSERT INTO app_meta(key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def import_jsonl_backup(force=False):
    init_db()
    if not force and _get_meta("jsonl_imported_v1") == "1":
        return {"skipped": True, **storage_summary()}

    for row in read_jsonl_gen(UNKNOWN_PATH):
        add_unknown(row.get("text", ""), details=row.get("details", {}))

    for row in read_jsonl_gen(RESOLVED_UNKNOWN_PATH):
        text = row.get("text", "")
        if text:
            resolve_unknowns([text], action=row.get("action", "resolved"))

    for row in read_jsonl_gen(FEEDBACK_PATH):
        text = row.get("text", "")
        lang = row.get("lang", "")
        if text and lang:
            add_feedback(text, lang, source=row.get("source", "jsonl"))

    if LEXICON_DIR.exists():
        for path in LEXICON_DIR.glob("*.txt"):
            if path.name.startswith("_"):
                continue
            language = path.stem.lower()
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle:
                    word = line.strip().lower()
                    if word and not word.startswith("#"):
                        upsert_lexicon_word(
                            language, word, enabled=True, source="jsonl"
                        )

    if NAME_DIR.exists():
        for path in NAME_DIR.glob("*.jsonl"):
            if path.name.startswith("_"):
                continue
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    upsert_name_hint(
                        row.get("name", ""),
                        row.get("language", path.stem),
                        country=row.get("country", ""),
                        confidence=row.get("confidence", 0.9),
                        enabled=True,
                        source="jsonl",
                    )
    _set_meta("jsonl_imported_v1", "1")
    return {"skipped": False, **storage_summary()}


def export_jsonl_backup():
    init_db()
    unknown_rows = []
    resolved_rows = []
    with connect() as db:
        for row in db.execute(
            "SELECT text, count, details_json, status, action FROM unknown_texts ORDER BY text"
        ):
            if row["status"] == "active":
                for _ in range(max(1, int(row["count"]))):
                    unknown_rows.append(
                        {
                            "text": row["text"],
                            "details": json.loads(row["details_json"] or "{}"),
                        }
                    )
            else:
                resolved_rows.append(
                    {"text": row["text"], "action": row["action"] or "resolved"}
                )

        feedback_rows = [
            {
                "text": row["text"],
                "lang": row["lang"],
                "source": row["source"],
            }
            for row in db.execute(
                "SELECT text, lang, source FROM feedback_samples WHERE promoted = 0 ORDER BY id"
            )
        ]

    write_jsonl(UNKNOWN_PATH, unknown_rows)
    write_jsonl(RESOLVED_UNKNOWN_PATH, resolved_rows)
    write_jsonl(FEEDBACK_PATH, feedback_rows)
    return {
        "unknown": len(unknown_rows),
        "resolved_unknown": len(resolved_rows),
        "feedback": len(feedback_rows),
    }


def reset_application_data():
    """
    Destructive action: Clears all dynamic application data except for the core datasets.
    """
    from src.config import (
        DATABASE_PATH,
        MODEL_PATH,
        RELATED_MODEL_PATH,
        EVALUATION_REPORT_PATH,
        LOG_DIR,
        UNKNOWN_PATH,
        FEEDBACK_PATH,
        RESOLVED_UNKNOWN_PATH,
        BENCHMARK_PATH,
        LEXICON_DIR,
        NAME_DIR,
        MODEL_SNAPSHOT_DIR,
    )

    # 1. Database
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    # 2. Models
    if MODEL_PATH.exists():
        MODEL_PATH.unlink()
    if RELATED_MODEL_PATH.exists():
        RELATED_MODEL_PATH.unlink()
    if EVALUATION_REPORT_PATH.exists():
        EVALUATION_REPORT_PATH.unlink()
    if MODEL_SNAPSHOT_DIR.exists():
        shutil.rmtree(MODEL_SNAPSHOT_DIR)
        MODEL_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    # 3. JSONL files (non-dataset)
    paths_to_clear = [
        UNKNOWN_PATH,
        FEEDBACK_PATH,
        RESOLVED_UNKNOWN_PATH,
        BENCHMARK_PATH,
    ]
    for p in paths_to_clear:
        if p.exists():
            p.unlink()

    # 4. User-added files in Lexicon and Names
    if LEXICON_DIR.exists():
        for path in LEXICON_DIR.glob("*.txt"):
            if not path.name.startswith("_"):
                path.unlink()

    if NAME_DIR.exists():
        for path in NAME_DIR.glob("*.jsonl"):
            path.unlink()

    # 5. Logs
    if LOG_DIR.exists():
        for path in LOG_DIR.glob("*.log"):
            try:
                path.write_text("")
            except Exception:
                pass

    # Re-initialize DB
    init_db()
    return {"ok": True, "message": "Application data has been reset."}
