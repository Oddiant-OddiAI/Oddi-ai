"""Persistence and validation for in-app Help & Feedback."""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from app import google_drive_storage
from app.database import ODDI_DRIVE_CHAT_STORAGE, _use_postgres, get_db

logger = logging.getLogger("oddi.help_feedback")
ADMIN_EMAIL = "vedansshrajsinha@gmail.com"
QUESTION_KEYS = tuple(f"q{i}" for i in range(1, 11))
TARGET_KEYS = frozenset((*QUESTION_KEYS, "overall"))
COOLDOWN = timedelta(hours=24)
MAX_REASON_LENGTH = 600
MAX_OVERALL_LENGTH = 4000
MAX_REPLY_LENGTH = 2000


class FeedbackCooldownError(Exception):
    def __init__(self, cooldown_until):
        self.cooldown_until = cooldown_until
        super().__init__("You can submit your next feedback after the cooldown ends.")


class FeedbackValidationError(ValueError):
    pass


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(value=None):
    return (value or _now()).isoformat().replace("+00:00", "Z")


def _parse_time(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def is_admin_email(email):
    return str(email or "").strip().casefold() == ADMIN_EMAIL


def clean_submission(ratings, reasons, overall_feedback):
    if not isinstance(ratings, dict):
        raise FeedbackValidationError("Please rate all 10 questions before submitting.")
    cleaned_ratings = {}
    cleaned_reasons = {}
    for key in QUESTION_KEYS:
        raw = ratings.get(key)
        if isinstance(raw, bool):
            raise FeedbackValidationError("Each rating must be from 1 to 5 stars.")
        try:
            value = int(raw)
        except (TypeError, ValueError, OverflowError):
            raise FeedbackValidationError("Please rate all 10 questions before submitting.")
        if value < 1 or value > 5 or str(raw).strip() not in {str(value), f"{value}.0"}:
            raise FeedbackValidationError("Each rating must be from 1 to 5 stars.")
        cleaned_ratings[key] = value

    if not isinstance(reasons, dict):
        reasons = {}
    for key, rating in cleaned_ratings.items():
        reason = str(reasons.get(key) or "").strip()
        if rating <= 3 and not reason:
            raise FeedbackValidationError(f"Please tell us how we can improve for question {key[1:]}.")
        if len(reason) > MAX_REASON_LENGTH:
            raise FeedbackValidationError("An individual explanation is too long.")
        if rating <= 3 and reason:
            cleaned_reasons[key] = reason

    if not isinstance(overall_feedback, str):
        overall_feedback = ""
    overall_feedback = overall_feedback.strip()
    if len(overall_feedback) > MAX_OVERALL_LENGTH:
        raise FeedbackValidationError("Overall feedback must be 4,000 characters or less.")
    return cleaned_ratings, cleaned_reasons, overall_feedback


def _row_value(row, key, default=None):
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


def _decode_json(value, fallback):
    try:
        result = json.loads(value) if isinstance(value, str) else value
        return result if isinstance(result, type(fallback)) else fallback
    except (TypeError, ValueError):
        return fallback


def _reply_dict(reply):
    return {
        "id": str(_row_value(reply, "id", "")),
        "submission_id": str(_row_value(reply, "submission_id", "")),
        "target_key": str(_row_value(reply, "target_key", "")),
        "body": str(_row_value(reply, "body", "")),
        "created_at": str(_row_value(reply, "created_at", "")),
        "read_at": _row_value(reply, "read_at"),
    }


def _submission_dict(row):
    return {
        "id": str(_row_value(row, "id", "")),
        "user_id": str(_row_value(row, "user_id", "")),
        "username": str(_row_value(row, "username", "")),
        "user_email": str(_row_value(row, "user_email", "")),
        "ratings": _decode_json(_row_value(row, "ratings_json", {}), {}),
        "reasons": _decode_json(_row_value(row, "reasons_json", {}), {}),
        "overall_feedback": str(_row_value(row, "overall_feedback", "")),
        "submitted_at": str(_row_value(row, "submitted_at", "")),
        "replies": [],
    }


def _cooldown_until(submissions):
    if not submissions:
        return None
    latest = max(
        (item for item in submissions if isinstance(item, dict)),
        key=lambda item: _parse_time(item.get("submitted_at")) or datetime.min.replace(tzinfo=timezone.utc),
        default=None,
    )
    submitted = _parse_time(latest.get("submitted_at")) if latest else None
    if not submitted:
        return None
    until = submitted + COOLDOWN
    return _iso(until) if _now() < until else None


def _drive_document(user_id):
    return google_drive_storage.read_help_feedback_document(user_id)


def _drive_submissions(user_id):
    document = _drive_document(user_id)
    return [item for item in document.get("submissions", []) if isinstance(item, dict)]


def _drive_submit(user_id, username, email, ratings, reasons, overall_feedback):
    submission = {
        "id": str(uuid.uuid4()),
        "user_id": str(user_id),
        "username": str(username or "")[:200],
        "user_email": str(email or "").strip().casefold()[:320],
        "ratings": ratings,
        "reasons": reasons,
        "overall_feedback": overall_feedback,
        "submitted_at": _iso(),
        "replies": [],
    }

    def mutate(document):
        submissions = [item for item in document.get("submissions", []) if isinstance(item, dict)]
        until = _cooldown_until(submissions)
        if until:
            raise FeedbackCooldownError(until)
        submissions.append(submission)
        return {"submissions": submissions}, submission

    return google_drive_storage.mutate_help_feedback_document(user_id, mutate)


def submit_feedback(user_id, username, email, ratings, reasons, overall_feedback):
    ratings, reasons, overall_feedback = clean_submission(ratings, reasons, overall_feedback)
    if ODDI_DRIVE_CHAT_STORAGE:
        return _drive_submit(user_id, username, email, ratings, reasons, overall_feedback)

    now = _now()
    conn = get_db("chat")
    try:
        if _use_postgres("chat"):
            lock_key = int.from_bytes(
                hashlib.sha256(f"oddi-help-feedback:{user_id}".encode("utf-8")).digest()[:8],
                "big",
                signed=True,
            )
            conn.execute("SELECT pg_advisory_xact_lock(?)", (lock_key,))
        else:
            conn.execute("BEGIN IMMEDIATE")
        latest = conn.execute(
            "SELECT submitted_at FROM help_feedback_submissions WHERE user_id = ? ORDER BY submitted_at DESC, id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        until = _cooldown_until([{"submitted_at": _row_value(latest, "submitted_at")}]) if latest else None
        if until:
            raise FeedbackCooldownError(until)
        values = (
            user_id,
            str(username or "")[:200],
            str(email or "").strip().casefold()[:320],
            json.dumps(ratings, ensure_ascii=False),
            json.dumps(reasons, ensure_ascii=False),
            overall_feedback,
            _iso(now),
        )
        if _use_postgres("chat"):
            row = conn.execute(
                "INSERT INTO help_feedback_submissions (user_id, username, user_email, ratings_json, reasons_json, overall_feedback, submitted_at) VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id",
                values,
            ).fetchone()
            submission_id = _row_value(row, "id")
        else:
            cursor = conn.execute(
                "INSERT INTO help_feedback_submissions (user_id, username, user_email, ratings_json, reasons_json, overall_feedback, submitted_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                values,
            )
            submission_id = cursor.lastrowid
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {
        "id": str(submission_id),
        "user_id": str(user_id),
        "username": str(username or ""),
        "user_email": str(email or "").strip().casefold(),
        "ratings": ratings,
        "reasons": reasons,
        "overall_feedback": overall_feedback,
        "submitted_at": _iso(now),
        "replies": [],
    }


def _load_sql_submissions(user_id=None):
    conn = get_db("chat")
    try:
        if user_id is None:
            rows = conn.execute(
                "SELECT * FROM help_feedback_submissions ORDER BY submitted_at DESC, id DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM help_feedback_submissions WHERE user_id = ? ORDER BY submitted_at DESC, id DESC",
                (user_id,),
            ).fetchall()
        submissions = [_submission_dict(row) for row in rows]
        if not submissions:
            return submissions
        ids = [int(item["id"]) for item in submissions]
        placeholders = ",".join("?" for _ in ids)
        reply_rows = conn.execute(
            f"SELECT * FROM help_feedback_replies WHERE submission_id IN ({placeholders}) ORDER BY created_at ASC, id ASC",
            ids,
        ).fetchall()
        by_id = {item["id"]: item for item in submissions}
        for reply in reply_rows:
            item = by_id.get(str(_row_value(reply, "submission_id", "")))
            if item is not None:
                item["replies"].append(_reply_dict(reply))
        return submissions
    finally:
        conn.close()


def _load_drive_submissions():
    documents = google_drive_storage.list_help_feedback_documents()
    result = []
    for document in documents:
        for raw in document.get("submissions", []):
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            item.setdefault("user_id", str(document.get("user_id") or ""))
            item.setdefault("username", document.get("username") or "")
            item.setdefault("user_email", document.get("user_email") or "")
            item.setdefault("ratings", {})
            item.setdefault("reasons", {})
            item.setdefault("overall_feedback", "")
            item.setdefault("replies", [])
            result.append(item)
    result.sort(key=lambda item: _parse_time(item.get("submitted_at")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return result


def user_feedback_state(user_id):
    submissions = _drive_submissions(user_id) if ODDI_DRIVE_CHAT_STORAGE else _load_sql_submissions(user_id)
    unread = [
        reply
        for submission in submissions
        for reply in submission.get("replies", [])
        if not reply.get("read_at")
    ]
    return {
        "submissions": submissions,
        "cooldown_until": _cooldown_until(submissions),
        "unread_replies": unread,
    }


def unread_feedback_replies(user_id):
    if ODDI_DRIVE_CHAT_STORAGE:
        return [
            reply
            for submission in _drive_submissions(user_id)
            for reply in submission.get("replies", [])
            if not reply.get("read_at")
        ]
    conn = get_db("chat")
    try:
        rows = conn.execute(
            "SELECT * FROM help_feedback_replies WHERE recipient_user_id = ? AND read_at IS NULL ORDER BY created_at DESC, id DESC LIMIT 100",
            (user_id,),
        ).fetchall()
        return [_reply_dict(row) for row in rows]
    finally:
        conn.close()


def _validate_reply_target(submission, target_key):
    if target_key not in TARGET_KEYS:
        raise FeedbackValidationError("Choose one feedback item to reply to.")
    if target_key == "overall":
        if not str(submission.get("overall_feedback") or "").strip():
            raise FeedbackValidationError("This submission has no overall written comment.")
        return
    ratings = submission.get("ratings") if isinstance(submission.get("ratings"), dict) else {}
    reasons = submission.get("reasons") if isinstance(submission.get("reasons"), dict) else {}
    if int(ratings.get(target_key) or 5) > 3 or not str(reasons.get(target_key) or "").strip():
        raise FeedbackValidationError("Replies are available for written comments with ratings of 3 stars or lower.")


def create_admin_reply(submission_id, target_key, body, host_user_id, host_email):
    target_key = str(target_key or "").strip()
    body = str(body or "").strip()
    if not body:
        raise FeedbackValidationError("Write a reply before sending it.")
    if len(body) > MAX_REPLY_LENGTH:
        raise FeedbackValidationError("Replies must be 2,000 characters or less.")
    if ODDI_DRIVE_CHAT_STORAGE:
        documents = google_drive_storage.list_help_feedback_documents()
        for document in documents:
            if not any(str(item.get("id")) == str(submission_id) for item in document.get("submissions", [])):
                continue
            recipient_id = document.get("user_id")
            reply = {
                "id": str(uuid.uuid4()),
                "submission_id": str(submission_id),
                "target_key": target_key,
                "body": body,
                "created_at": _iso(),
                "read_at": None,
            }

            def mutate(current):
                submissions = current.get("submissions", [])
                for submission in submissions:
                    if str(submission.get("id")) == str(submission_id):
                        _validate_reply_target(submission, target_key)
                        submission.setdefault("replies", []).append(reply)
                        return {"submissions": submissions}, reply
                raise LookupError("Feedback was not found.")

            return google_drive_storage.mutate_help_feedback_document(recipient_id, mutate)
        raise LookupError("Feedback was not found.")

    conn = get_db("chat")
    try:
        try:
            numeric_submission_id = int(submission_id)
        except (TypeError, ValueError, OverflowError):
            raise LookupError("Feedback was not found.")
        row = conn.execute(
            "SELECT * FROM help_feedback_submissions WHERE id = ?",
            (numeric_submission_id,),
        ).fetchone()
        if not row:
            raise LookupError("Feedback was not found.")
        submission = _submission_dict(row)
        _validate_reply_target(submission, target_key)
        values = (
            int(submission["id"]),
            int(submission["user_id"]),
            int(host_user_id),
            target_key,
            body,
            _iso(),
        )
        if _use_postgres("chat"):
            inserted = conn.execute(
                "INSERT INTO help_feedback_replies (submission_id, recipient_user_id, host_user_id, target_key, body, created_at) VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
                values,
            ).fetchone()
            reply_id = _row_value(inserted, "id")
        else:
            cursor = conn.execute(
                "INSERT INTO help_feedback_replies (submission_id, recipient_user_id, host_user_id, target_key, body, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                values,
            )
            reply_id = cursor.lastrowid
        conn.commit()
        return {
            "id": str(reply_id),
            "submission_id": str(submission["id"]),
            "target_key": target_key,
            "body": body,
            "created_at": _iso(),
            "read_at": None,
            "host_email": str(host_email or "").casefold(),
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mark_replies_read(user_id, reply_ids):
    ids = {str(value)[:80] for value in (reply_ids or []) if str(value).strip()}
    if not ids:
        return 0
    if ODDI_DRIVE_CHAT_STORAGE:
        count = 0

        def mutate(document):
            nonlocal count
            for submission in document.get("submissions", []):
                for reply in submission.get("replies", []):
                    if str(reply.get("id")) in ids and not reply.get("read_at"):
                        reply["read_at"] = _iso()
                        count += 1
            return document, count

        google_drive_storage.mutate_help_feedback_document(user_id, mutate)
        return count
    conn = get_db("chat")
    try:
        placeholders = ",".join("?" for _ in ids)
        numeric_ids = [int(value) for value in ids if value.isdigit()]
        if not numeric_ids:
            return 0
        placeholders = ",".join("?" for _ in numeric_ids)
        cursor = conn.execute(
            f"UPDATE help_feedback_replies SET read_at = ? WHERE recipient_user_id = ? AND read_at IS NULL AND id IN ({placeholders})",
            [_iso(), user_id, *numeric_ids],
        )
        conn.commit()
        return int(getattr(cursor, "rowcount", 0) or 0)
    finally:
        conn.close()


def admin_feedback_overview():
    submissions = _load_drive_submissions() if ODDI_DRIVE_CHAT_STORAGE else _load_sql_submissions()
    totals = {key: {"sum": 0, "count": 0} for key in QUESTION_KEYS}
    for submission in submissions:
        ratings = submission.get("ratings") if isinstance(submission.get("ratings"), dict) else {}
        for key in QUESTION_KEYS:
            try:
                rating = int(ratings.get(key))
            except (TypeError, ValueError, OverflowError):
                continue
            if 1 <= rating <= 5:
                totals[key]["sum"] += rating
                totals[key]["count"] += 1
    averages = {
        key: {
            "average": round(item["sum"] / item["count"], 2) if item["count"] else None,
            "count": item["count"],
        }
        for key, item in totals.items()
    }
    return {"averages": averages, "submission_count": len(submissions), "submissions": submissions}


def admin_feedback_reply(submission_id, target_key, body, host_user_id, host_email):
    return create_admin_reply(submission_id, target_key, body, host_user_id, host_email)
