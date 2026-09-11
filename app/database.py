import json
import logging
import os
import sqlite3
from datetime import datetime

logger = logging.getLogger("oddi.persistence")


class _DBConnection:
    """Small compatibility wrapper so the same ? placeholders work on SQLite and Postgres."""
    def __init__(self, conn, postgres=False):
        self._conn = conn
        self._postgres = postgres

    def execute(self, sql, params=()):
        if self._postgres:
            sql = sql.replace("?", "%s")
        return self._conn.execute(sql, params)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)

# Production on Render: set DATABASE_URL to the Render Postgres internal URL.
# Local development: if DATABASE_URL is absent, ODDI keeps using SQLite.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
REQUIRE_POSTGRES = os.getenv("ODDI_REQUIRE_POSTGRES", "0").strip().lower() in {"1", "true", "yes", "on"}
USE_POSTGRES = bool(DATABASE_URL)
if REQUIRE_POSTGRES and not USE_POSTGRES:
    raise RuntimeError(
        "ODDI_REQUIRE_POSTGRES is enabled but DATABASE_URL is not set. "
        "Configure the production PostgreSQL connection before starting ODDI."
    )
DATABASE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "users.db",
)


def get_db():
    if USE_POSTGRES:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError(
                "DATABASE_URL is set but psycopg is not installed. "
                "Add psycopg[binary] to requirements.txt."
            ) from exc

        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        return _DBConnection(conn, postgres=True)

    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.DatabaseError:
        pass
    return _DBConnection(conn, postgres=False)


def _backend_label():
    return "postgres" if USE_POSTGRES else os.path.abspath(DATABASE)


def _fetchone(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()


def _fetchall(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


def create_tables():
    conn = get_db()
    try:
        if USE_POSTGRES:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    title TEXT NOT NULL DEFAULT 'New Chat',
                    messages TEXT NOT NULL DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    revision BIGINT NOT NULL DEFAULT 0,
                    pinned INTEGER NOT NULL DEFAULT 0,
                    archived INTEGER NOT NULL DEFAULT 0,
                    deleted_at TIMESTAMP NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    memory_key TEXT NOT NULL,
                    memory_value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, memory_key)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_knowledge (
                    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    vector_store_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL DEFAULT 'New Chat',
                    messages TEXT NOT NULL DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    revision INTEGER NOT NULL DEFAULT 0,
                    pinned INTEGER NOT NULL DEFAULT 0,
                    archived INTEGER NOT NULL DEFAULT 0,
                    deleted_at TIMESTAMP NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            columns = {row[1] for row in conn.execute("PRAGMA table_info(conversations)").fetchall()}
            if "updated_at" not in columns:
                conn.execute("ALTER TABLE conversations ADD COLUMN updated_at TIMESTAMP")
                conn.execute("UPDATE conversations SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP) WHERE updated_at IS NULL")
            if "revision" not in columns:
                conn.execute("ALTER TABLE conversations ADD COLUMN revision INTEGER NOT NULL DEFAULT 0")
            if "pinned" not in columns:
                conn.execute("ALTER TABLE conversations ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
            if "archived" not in columns:
                conn.execute("ALTER TABLE conversations ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")
            if "deleted_at" not in columns:
                conn.execute("ALTER TABLE conversations ADD COLUMN deleted_at TIMESTAMP NULL")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    memory_key TEXT NOT NULL,
                    memory_value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, memory_key)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_knowledge (
                    user_id INTEGER PRIMARY KEY,
                    vector_store_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

        conn.commit()
    finally:
        conn.close()

    logger.info("Database tables ready backend=%s", _backend_label())


def create_user(username, email, password_hash):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users(username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, password_hash),
        )
        conn.commit()
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_db()
    try:
        return _fetchone(conn, "SELECT * FROM users WHERE email = ?", (email,))
    finally:
        conn.close()


def create_conversation(user_id, title="New Chat"):
    conn = get_db()
    try:
        if USE_POSTGRES:
            row = _fetchone(
                conn,
                """
                INSERT INTO conversations (user_id, title, messages, revision)
                VALUES (?, ?, ?, 0)
                RETURNING id
                """,
                (user_id, title, json.dumps([])),
            )
            conversation_id = row["id"]
        else:
            cursor = conn.execute(
                """
                INSERT INTO conversations (user_id, title, messages, revision)
                VALUES (?, ?, ?, 0)
                """,
                (user_id, title, json.dumps([])),
            )
            conversation_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    logger.warning(
        "PERSIST CREATE COMMIT pid=%s backend=%s user=%s conversation=%s",
        os.getpid(), _backend_label(), user_id, conversation_id,
    )
    return conversation_id


def _normalize_messages_for_storage(messages, conversation_id):
    normalized = []
    for index, message in enumerate(messages if isinstance(messages, list) else []):
        item = dict(message) if isinstance(message, dict) else {
            "role": "assistant",
            "text": str(message),
        }
        if not item.get("id"):
            item["id"] = f"legacy-{conversation_id}-{index}"
        normalized.append(item)
    return normalized


def _conversation_dict(row):
    messages = row["messages"]
    if isinstance(messages, str):
        messages = json.loads(messages)
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "title": row["title"],
        "messages": _normalize_messages_for_storage(messages, row["id"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "revision": int(row["revision"] or 0),
        "pinned": bool(row["pinned"]),
        "archived": bool(row["archived"]),
        "deleted": bool(row["deleted_at"]),
        "deleted_at": row["deleted_at"],
    }


def _conversation_select():
    return """
        SELECT id, user_id, title, messages, created_at, updated_at,
               revision, pinned, archived, deleted_at
        FROM conversations
    """


def get_conversations(user_id):
    conn = get_db()
    logger.warning("PERSIST GET START pid=%s backend=%s user=%s", os.getpid(), _backend_label(), user_id)
    try:
        rows = _fetchall(
            conn,
            _conversation_select() + "WHERE user_id = ? AND deleted_at IS NULL ORDER BY id DESC",
            (user_id,),
        )
        result = [_conversation_dict(row) for row in rows]
        logger.warning(
            "PERSIST GET RESULT pid=%s backend=%s user=%s count=%s ids=%s",
            os.getpid(), _backend_label(), user_id, len(result), [c["id"] for c in result],
        )
        return result
    finally:
        conn.close()


def get_deleted_conversations(user_id):
    conn = get_db()
    try:
        rows = _fetchall(
            conn,
            _conversation_select() + "WHERE user_id = ? AND deleted_at IS NOT NULL ORDER BY deleted_at DESC, id DESC",
            (user_id,),
        )
        return [_conversation_dict(row) for row in rows]
    finally:
        conn.close()


def get_conversation(conversation_id, user_id):
    conn = get_db()
    try:
        row = _fetchone(
            conn,
            _conversation_select() + "WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
        return _conversation_dict(row) if row else None
    finally:
        conn.close()


def _begin_write(conn):
    if not USE_POSTGRES:
        conn.execute("BEGIN IMMEDIATE")


def update_conversation(conversation_id, user_id, title, messages, expected_revision=None):
    conn = get_db()
    logger.warning(
        "PERSIST UPDATE START pid=%s backend=%s user=%s conversation=%s messages=%s expected_revision=%r",
        os.getpid(), _backend_label(), user_id, conversation_id,
        len(messages) if isinstance(messages, list) else 0, expected_revision,
    )
    try:
        _begin_write(conn)
        select_sql = _conversation_select() + "WHERE id = ? AND user_id = ?"
        if USE_POSTGRES:
            select_sql += " FOR UPDATE"
        row = _fetchone(conn, select_sql, (conversation_id, user_id))
        if not row:
            conn.rollback()
            return {"ok": False, "found": False, "conflict": False, "conversation": None}

        current_revision = int(row["revision"] or 0)
        if expected_revision is not None and int(expected_revision) != current_revision:
            conversation = _conversation_dict(row)
            conn.rollback()
            return {"ok": False, "found": True, "conflict": True, "conversation": conversation}

        normalized = _normalize_messages_for_storage(messages, conversation_id)
        next_revision = current_revision + 1
        conn.execute(
            """
            UPDATE conversations
            SET title = ?, messages = ?, updated_at = CURRENT_TIMESTAMP, revision = ?
            WHERE id = ? AND user_id = ?
            """,
            (title or "New Chat", json.dumps(normalized), next_revision, conversation_id, user_id),
        )
        conn.commit()

        row = _fetchone(conn, _conversation_select() + "WHERE id = ? AND user_id = ?", (conversation_id, user_id))
        result = {"ok": True, "found": True, "conflict": False, "conversation": _conversation_dict(row)}
        logger.warning(
            "PERSIST UPDATE COMMIT pid=%s backend=%s user=%s conversation=%s revision=%s deleted=%s messages=%s",
            os.getpid(), _backend_label(), user_id, conversation_id,
            result["conversation"]["revision"], result["conversation"]["deleted"],
            len(result["conversation"]["messages"]),
        )
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def append_conversation_message(conversation_id, user_id, message):
    conn = get_db()
    try:
        _begin_write(conn)
        select_sql = _conversation_select() + "WHERE id = ? AND user_id = ?"
        if USE_POSTGRES:
            select_sql += " FOR UPDATE"
        row = _fetchone(conn, select_sql, (conversation_id, user_id))
        if not row:
            conn.rollback()
            return None

        current_messages = _normalize_messages_for_storage(row["messages"] if isinstance(row["messages"], list) else json.loads(row["messages"]), conversation_id)
        item = dict(message) if isinstance(message, dict) else {"role": "assistant", "text": str(message)}
        if not item.get("id"):
            item["id"] = f"legacy-{conversation_id}-{len(current_messages)}"
        existing_ids = {str(m.get("id")) for m in current_messages if m.get("id")}
        if str(item["id"]) in existing_ids:
            conn.rollback()
            return _conversation_dict(row)

        current_messages.append(item)
        next_revision = int(row["revision"] or 0) + 1
        conn.execute(
            """
            UPDATE conversations
            SET messages = ?, updated_at = CURRENT_TIMESTAMP, revision = ?
            WHERE id = ? AND user_id = ?
            """,
            (json.dumps(current_messages), next_revision, conversation_id, user_id),
        )
        conn.commit()

        row = _fetchone(conn, _conversation_select() + "WHERE id = ? AND user_id = ?", (conversation_id, user_id))
        return _conversation_dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_conversation_message(conversation_id, user_id, message_id, patch):
    conn = get_db()
    try:
        _begin_write(conn)
        select_sql = _conversation_select() + "WHERE id = ? AND user_id = ?"
        if USE_POSTGRES:
            select_sql += " FOR UPDATE"
        row = _fetchone(conn, select_sql, (conversation_id, user_id))
        if not row:
            conn.rollback()
            return None

        messages = _normalize_messages_for_storage(row["messages"] if isinstance(row["messages"], list) else json.loads(row["messages"]), conversation_id)
        found = False
        for message in messages:
            if str(message.get("id")) == str(message_id):
                for key, value in (patch or {}).items():
                    if key in {"text", "content", "pinned", "feedback", "stopped"}:
                        message[key] = value
                found = True
                break
        if not found:
            conn.rollback()
            return None

        next_revision = int(row["revision"] or 0) + 1
        conn.execute(
            """
            UPDATE conversations
            SET messages = ?, updated_at = CURRENT_TIMESTAMP, revision = ?
            WHERE id = ? AND user_id = ?
            """,
            (json.dumps(messages), next_revision, conversation_id, user_id),
        )
        conn.commit()
        row = _fetchone(conn, _conversation_select() + "WHERE id = ? AND user_id = ?", (conversation_id, user_id))
        return _conversation_dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_conversation_message(conversation_id, user_id, message_id):
    conn = get_db()
    try:
        _begin_write(conn)
        select_sql = _conversation_select() + "WHERE id = ? AND user_id = ?"
        if USE_POSTGRES:
            select_sql += " FOR UPDATE"
        row = _fetchone(conn, select_sql, (conversation_id, user_id))
        if not row:
            conn.rollback()
            return None

        messages = _normalize_messages_for_storage(row["messages"] if isinstance(row["messages"], list) else json.loads(row["messages"]), conversation_id)
        new_messages = [m for m in messages if str(m.get("id")) != str(message_id)]
        if len(new_messages) == len(messages):
            conn.rollback()
            return None

        next_revision = int(row["revision"] or 0) + 1
        conn.execute(
            """
            UPDATE conversations
            SET messages = ?, updated_at = CURRENT_TIMESTAMP, revision = ?
            WHERE id = ? AND user_id = ?
            """,
            (json.dumps(new_messages), next_revision, conversation_id, user_id),
        )
        conn.commit()
        row = _fetchone(conn, _conversation_select() + "WHERE id = ? AND user_id = ?", (conversation_id, user_id))
        return _conversation_dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_conversation_metadata(conversation_id, user_id, pinned=None, archived=None, deleted=None):
    conn = get_db()
    logger.warning(
        "PERSIST META START pid=%s backend=%s user=%s conversation=%s pinned=%r archived=%r deleted=%r",
        os.getpid(), _backend_label(), user_id, conversation_id, pinned, archived, deleted,
    )
    try:
        _begin_write(conn)
        select_sql = "SELECT pinned, archived, deleted_at FROM conversations WHERE id = ? AND user_id = ?"
        if USE_POSTGRES:
            select_sql += " FOR UPDATE"
        current = _fetchone(conn, select_sql, (conversation_id, user_id))
        if not current:
            conn.rollback()
            return None

        next_pinned = int(bool(current["pinned"])) if pinned is None else int(bool(pinned))
        next_archived = int(bool(current["archived"])) if archived is None else int(bool(archived))
        if deleted is None:
            next_deleted = current["deleted_at"]
        else:
            next_deleted = datetime.utcnow() if deleted else None
        if deleted is True:
            next_pinned = 0
            next_archived = 0

        conn.execute(
            """
            UPDATE conversations
            SET pinned = ?, archived = ?, deleted_at = ?,
                updated_at = CURRENT_TIMESTAMP,
                revision = revision + 1
            WHERE id = ? AND user_id = ?
            """,
            (next_pinned, next_archived, next_deleted, conversation_id, user_id),
        )
        conn.commit()
        row = _fetchone(conn, _conversation_select() + "WHERE id = ? AND user_id = ?", (conversation_id, user_id))
        result = _conversation_dict(row) if row else None
        logger.warning(
            "PERSIST META COMMIT pid=%s backend=%s user=%s conversation=%s deleted=%s archived=%s pinned=%s",
            os.getpid(), _backend_label(), user_id, conversation_id,
            result["deleted"] if result else None,
            result["archived"] if result else None,
            result["pinned"] if result else None,
        )
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_conversation(conversation_id, user_id):
    conn = get_db()
    logger.warning("PERSIST HARD DELETE START pid=%s backend=%s user=%s conversation=%s", os.getpid(), _backend_label(), user_id, conversation_id)
    try:
        conn.execute("DELETE FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))
        conn.commit()
        logger.warning("PERSIST HARD DELETE COMMIT pid=%s backend=%s user=%s conversation=%s", os.getpid(), _backend_label(), user_id, conversation_id)
    finally:
        conn.close()


def delete_all_conversations(user_id):
    conn = get_db()
    logger.warning("PERSIST HARD DELETE ALL START pid=%s backend=%s user=%s", os.getpid(), _backend_label(), user_id)
    try:
        conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        conn.commit()
        logger.warning("PERSIST HARD DELETE ALL COMMIT pid=%s backend=%s user=%s", os.getpid(), _backend_label(), user_id)
    finally:
        conn.close()


def get_memory(user_id, key=None):
    conn = get_db()
    try:
        if key:
            row = _fetchone(
                conn,
                "SELECT memory_key, memory_value FROM memories WHERE user_id = ? AND memory_key = ?",
                (user_id, key),
            )
            return row["memory_value"] if row else None

        rows = _fetchall(conn, "SELECT memory_key, memory_value FROM memories WHERE user_id = ?", (user_id,))
        return {row["memory_key"]: row["memory_value"] for row in rows}
    finally:
        conn.close()


def save_memory(user_id, key, value):
    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO memories (user_id, memory_key, memory_value)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, memory_key)
            DO UPDATE SET memory_value = excluded.memory_value, updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, key, value),
        )
        conn.commit()
    finally:
        conn.close()


def delete_memory(user_id, key):
    conn = get_db()
    try:
        conn.execute("DELETE FROM memories WHERE user_id = ? AND memory_key = ?", (user_id, key))
        conn.commit()
    finally:
        conn.close()


def clear_memory(user_id):
    conn = get_db()
    try:
        conn.execute("DELETE FROM memories WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def create_knowledge_table():
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_knowledge (
                user_id BIGINT PRIMARY KEY,
                vector_store_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    finally:
        conn.close()


def get_vector_store_id(user_id):
    conn = get_db()
    try:
        row = _fetchone(conn, "SELECT vector_store_id FROM user_knowledge WHERE user_id = ?", (user_id,))
        return row["vector_store_id"] if row else None
    finally:
        conn.close()


def save_vector_store_id(user_id, vector_store_id):
    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO user_knowledge (user_id, vector_store_id)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET vector_store_id = excluded.vector_store_id
            """,
            (user_id, vector_store_id),
        )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    create_tables()
    conn = get_db()
    try:
        users = conn.execute("SELECT username, email, password_hash FROM users").fetchall()
        for user in users:
            print(dict(user))
    finally:
        conn.close()
