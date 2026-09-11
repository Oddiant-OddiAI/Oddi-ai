import json
import logging
import os
import sqlite3
from datetime import datetime

logger = logging.getLogger("oddi.persistence")


class _DBConnection:
    """Small compatibility wrapper for SQLite/Postgres with ? placeholders."""

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


# ---------------------------------------------------------------------------
# THREE-DATABASE STORAGE ARCHITECTURE
# ---------------------------------------------------------------------------
# Existing DATABASE_URL remains supported as a migration/development fallback.
# Production should set all three dedicated URLs:
#   DATABASE_URL_CHAT
#   DATABASE_URL_FILES
#   DATABASE_URL_ARCHIVE_MEMORY
#
# Mapping:
#   CHAT            -> users + active chats/messages
#   FILES           -> file metadata/references
#   ARCHIVE_MEMORY  -> archived/bin chats + long-term memory + vector-store IDs
# ---------------------------------------------------------------------------

LEGACY_DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
CHAT_DATABASE_URL = os.getenv("DATABASE_URL_CHAT", "").strip() or LEGACY_DATABASE_URL
FILES_DATABASE_URL = os.getenv("DATABASE_URL_FILES", "").strip() or LEGACY_DATABASE_URL
ARCHIVE_MEMORY_DATABASE_URL = (
    os.getenv("DATABASE_URL_ARCHIVE_MEMORY", "").strip() or LEGACY_DATABASE_URL
)

REQUIRE_THREE_DATABASES = os.getenv("ODDI_REQUIRE_THREE_DATABASES", "0").strip().lower() in {
    "1", "true", "yes", "on"
}

if REQUIRE_THREE_DATABASES:
    missing = []
    if not os.getenv("DATABASE_URL_CHAT", "").strip():
        missing.append("DATABASE_URL_CHAT")
    if not os.getenv("DATABASE_URL_FILES", "").strip():
        missing.append("DATABASE_URL_FILES")
    if not os.getenv("DATABASE_URL_ARCHIVE_MEMORY", "").strip():
        missing.append("DATABASE_URL_ARCHIVE_MEMORY")
    if missing:
        raise RuntimeError(
            "ODDI_REQUIRE_THREE_DATABASES is enabled but these production database "
            f"URLs are missing: {', '.join(missing)}"
        )

USE_POSTGRES = bool(CHAT_DATABASE_URL or FILES_DATABASE_URL or ARCHIVE_MEMORY_DATABASE_URL)

DATABASE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "users.db",
)


def _database_url(kind):
    if kind == "chat":
        return CHAT_DATABASE_URL
    if kind == "files":
        return FILES_DATABASE_URL
    if kind == "archive_memory":
        return ARCHIVE_MEMORY_DATABASE_URL
    raise ValueError(f"Unknown database kind: {kind}")


def _use_postgres(kind):
    return bool(_database_url(kind))


def get_db(kind="chat"):
    url = _database_url(kind)

    if url:
        try:
            import psycopg  # type: ignore[import-not-found]
            from psycopg.rows import dict_row  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "A PostgreSQL DATABASE_URL is configured but psycopg is not installed. "
                "Add psycopg[binary] to requirements.txt."
            ) from exc

        conn = psycopg.connect(url, row_factory=dict_row)
        return _DBConnection(conn, postgres=True)

    # Local development fallback. All three logical stores use the same local
    # SQLite file so developers do not need three local Postgres projects.
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.DatabaseError:
        pass
    return _DBConnection(conn, postgres=False)


def _backend_label(kind):
    url = _database_url(kind)
    return "postgres" if url else os.path.abspath(DATABASE)


def _fetchone(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()


def _fetchall(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


def _begin_write(conn, kind):
    if not _use_postgres(kind):
        conn.execute("BEGIN IMMEDIATE")


# ---------------------------------------------------------------------------
# SCHEMA INITIALIZATION
# ---------------------------------------------------------------------------

def create_tables():
    _create_chat_tables()
    _create_archive_memory_tables()
    _create_files_tables()
    _migrate_legacy_archived_conversations()
    logger.info(
        "Three-database schema ready chat=%s files=%s archive_memory=%s",
        _backend_label("chat"),
        _backend_label("files"),
        _backend_label("archive_memory"),
    )


def _migrate_legacy_archived_conversations():
    """Move old archived/bin rows out of the original chat database once."""
    if not _database_url("chat") or not _database_url("archive_memory"):
        return
    if _database_url("chat") == _database_url("archive_memory"):
        return

    chat_conn = get_db("chat")
    try:
        rows = _fetchall(
            chat_conn,
            _chat_conversation_select()
            + "WHERE archived = 1 OR deleted_at IS NOT NULL ORDER BY id ASC",
        )
        legacy = [_conversation_dict(row) for row in rows]
    finally:
        chat_conn.close()

    if not legacy:
        return

    archive_conn = get_db("archive_memory")
    moved_ids = []
    try:
        for conversation in legacy:
            _insert_archive_conversation(archive_conn, conversation)
            moved_ids.append(conversation["id"])
        archive_conn.commit()
    except Exception:
        archive_conn.rollback()
        raise
    finally:
        archive_conn.close()

    chat_conn = get_db("chat")
    try:
        for conversation_id in moved_ids:
            chat_conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        chat_conn.commit()
    finally:
        chat_conn.close()

    logger.info(
        "Migrated %s legacy archived/bin conversations from chat DB to archive DB",
        len(moved_ids),
    )


def _create_chat_tables():
    conn = get_db("chat")
    try:
        if _use_postgres("chat"):
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
            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(conversations)").fetchall()
            }
            if "updated_at" not in columns:
                conn.execute("ALTER TABLE conversations ADD COLUMN updated_at TIMESTAMP")
                conn.execute(
                    "UPDATE conversations SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP) "
                    "WHERE updated_at IS NULL"
                )
            if "revision" not in columns:
                conn.execute("ALTER TABLE conversations ADD COLUMN revision INTEGER NOT NULL DEFAULT 0")
            if "pinned" not in columns:
                conn.execute("ALTER TABLE conversations ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
            if "archived" not in columns:
                conn.execute("ALTER TABLE conversations ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")
            if "deleted_at" not in columns:
                conn.execute("ALTER TABLE conversations ADD COLUMN deleted_at TIMESTAMP NULL")
        conn.commit()
    finally:
        conn.close()


def _create_archive_memory_tables():
    conn = get_db("archive_memory")
    try:
        if _use_postgres("archive_memory"):
            conn.execute("""
                CREATE TABLE IF NOT EXISTS archived_conversations (
                    conversation_id BIGINT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    title TEXT NOT NULL DEFAULT 'New Chat',
                    messages TEXT NOT NULL DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    revision BIGINT NOT NULL DEFAULT 0,
                    pinned INTEGER NOT NULL DEFAULT 0,
                    archived INTEGER NOT NULL DEFAULT 1,
                    deleted_at TIMESTAMP NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    memory_key TEXT NOT NULL,
                    memory_value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, memory_key)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_knowledge (
                    user_id BIGINT PRIMARY KEY,
                    vector_store_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS archived_conversations (
                    conversation_id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL DEFAULT 'New Chat',
                    messages TEXT NOT NULL DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    revision INTEGER NOT NULL DEFAULT 0,
                    pinned INTEGER NOT NULL DEFAULT 0,
                    archived INTEGER NOT NULL DEFAULT 1,
                    deleted_at TIMESTAMP NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    memory_key TEXT NOT NULL,
                    memory_value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, memory_key)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_knowledge (
                    user_id INTEGER PRIMARY KEY,
                    vector_store_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        conn.commit()
    finally:
        conn.close()


def _create_files_tables():
    conn = get_db("files")
    try:
        if _use_postgres("files"):
            conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    conversation_id BIGINT NULL,
                    filename TEXT NOT NULL,
                    mime_type TEXT,
                    extension TEXT,
                    size_bytes BIGINT NOT NULL DEFAULT 0,
                    storage_backend TEXT NOT NULL DEFAULT 'metadata-only',
                    storage_key TEXT,
                    external_file_id TEXT,
                    status TEXT NOT NULL DEFAULT 'received',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_files_user_created ON files(user_id, created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_files_user_conversation ON files(user_id, conversation_id)")
        else:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    conversation_id INTEGER NULL,
                    filename TEXT NOT NULL,
                    mime_type TEXT,
                    extension TEXT,
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    storage_backend TEXT NOT NULL DEFAULT 'metadata-only',
                    storage_key TEXT,
                    external_file_id TEXT,
                    status TEXT NOT NULL DEFAULT 'received',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_files_user_created ON files(user_id, created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_files_user_conversation ON files(user_id, conversation_id)")
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# USERS (CHAT DB)
# ---------------------------------------------------------------------------

def create_user(username, email, password_hash):
    conn = get_db("chat")
    try:
        conn.execute(
            "INSERT INTO users(username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, password_hash),
        )
        conn.commit()
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_db("chat")
    try:
        return _fetchone(conn, "SELECT * FROM users WHERE email = ?", (email,))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CONVERSATION HELPERS
# ---------------------------------------------------------------------------

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


def _row_value(row, key, default=None):
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


def _conversation_dict(row):
    conversation_id = _row_value(row, "id", _row_value(row, "conversation_id"))
    messages = _row_value(row, "messages", "[]")
    if isinstance(messages, str):
        messages = json.loads(messages)
    return {
        "id": conversation_id,
        "user_id": _row_value(row, "user_id"),
        "title": _row_value(row, "title"),
        "messages": _normalize_messages_for_storage(messages, conversation_id),
        "created_at": _row_value(row, "created_at"),
        "updated_at": _row_value(row, "updated_at"),
        "revision": int(_row_value(row, "revision", 0) or 0),
        "pinned": bool(_row_value(row, "pinned", 0)),
        "archived": bool(_row_value(row, "archived", 0)),
        "deleted": bool(_row_value(row, "deleted_at")),
        "deleted_at": _row_value(row, "deleted_at"),
    }


def _chat_conversation_select():
    return """
        SELECT id, user_id, title, messages, created_at, updated_at,
               revision, pinned, archived, deleted_at
        FROM conversations
    """


def _archive_conversation_select():
    return """
        SELECT conversation_id AS id, user_id, title, messages, created_at, updated_at,
               revision, pinned, archived, deleted_at
        FROM archived_conversations
    """


def create_conversation(user_id, title="New Chat"):
    conn = get_db("chat")
    try:
        if _use_postgres("chat"):
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
    logger.info(
        "PERSIST CREATE COMMIT pid=%s backend=%s user=%s conversation=%s",
        os.getpid(), _backend_label("chat"), user_id, conversation_id,
    )
    return conversation_id


def get_conversations(user_id):
    # The API continues to return one unified list so the existing frontend
    # does not need to know which physical database owns a conversation.
    chat_conn = get_db("chat")
    try:
        active_rows = _fetchall(
            chat_conn,
            _chat_conversation_select() + "WHERE user_id = ? AND deleted_at IS NULL ORDER BY id DESC",
            (user_id,),
        )
        active = [_conversation_dict(row) for row in active_rows]
    finally:
        chat_conn.close()

    archive_conn = get_db("archive_memory")
    try:
        archived_rows = _fetchall(
            archive_conn,
            _archive_conversation_select() + "WHERE user_id = ? AND deleted_at IS NULL ORDER BY id DESC",
            (user_id,),
        )
        archived = [_conversation_dict(row) for row in archived_rows]
    finally:
        archive_conn.close()

    result = active + archived
    result.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
    logger.info(
        "PERSIST GET user=%s chat=%s archive=%s total=%s",
        user_id, len(active), len(archived), len(result),
    )
    return result


def get_deleted_conversations(user_id):
    conn = get_db("archive_memory")
    try:
        rows = _fetchall(
            conn,
            _archive_conversation_select() + "WHERE user_id = ? AND deleted_at IS NOT NULL ORDER BY deleted_at DESC, id DESC",
            (user_id,),
        )
        return [_conversation_dict(row) for row in rows]
    finally:
        conn.close()


def _find_conversation(conversation_id, user_id, include_deleted=True):
    conn = get_db("chat")
    try:
        row = _fetchone(
            conn,
            _chat_conversation_select() + "WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
        if row:
            return "chat", _conversation_dict(row)
    finally:
        conn.close()

    conn = get_db("archive_memory")
    try:
        sql = _archive_conversation_select() + "WHERE conversation_id = ? AND user_id = ?"
        if not include_deleted:
            sql += " AND deleted_at IS NULL"
        row = _fetchone(conn, sql, (conversation_id, user_id))
        if row:
            return "archive_memory", _conversation_dict(row)
    finally:
        conn.close()
    return None, None


def get_conversation(conversation_id, user_id):
    _, conversation = _find_conversation(conversation_id, user_id, include_deleted=True)
    return conversation


def _insert_archive_conversation(conn, conversation):
    data = (
        conversation["id"],
        conversation["user_id"],
        conversation.get("title") or "New Chat",
        json.dumps(_normalize_messages_for_storage(conversation.get("messages", []), conversation["id"])),
        conversation.get("created_at"),
        conversation.get("updated_at"),
        int(conversation.get("revision", 0) or 0),
        int(bool(conversation.get("pinned"))),
        int(bool(conversation.get("archived"))),
        conversation.get("deleted_at"),
    )
    if _use_postgres("archive_memory"):
        conn.execute(
            """
            INSERT INTO archived_conversations
            (conversation_id, user_id, title, messages, created_at, updated_at,
             revision, pinned, archived, deleted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(conversation_id) DO UPDATE SET
                user_id = excluded.user_id,
                title = excluded.title,
                messages = excluded.messages,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at,
                revision = excluded.revision,
                pinned = excluded.pinned,
                archived = excluded.archived,
                deleted_at = excluded.deleted_at
            """,
            data,
        )
    else:
        conn.execute(
            """
            INSERT OR REPLACE INTO archived_conversations
            (conversation_id, user_id, title, messages, created_at, updated_at,
             revision, pinned, archived, deleted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            data,
        )


def _insert_chat_conversation(conn, conversation):
    data = (
        conversation["id"],
        conversation["user_id"],
        conversation.get("title") or "New Chat",
        json.dumps(_normalize_messages_for_storage(conversation.get("messages", []), conversation["id"])),
        conversation.get("created_at"),
        conversation.get("updated_at"),
        int(conversation.get("revision", 0) or 0),
        int(bool(conversation.get("pinned"))),
        0,
        conversation.get("deleted_at"),
    )
    if _use_postgres("chat"):
        conn.execute(
            """
            INSERT INTO conversations
            (id, user_id, title, messages, created_at, updated_at, revision, pinned, archived, deleted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                user_id = excluded.user_id,
                title = excluded.title,
                messages = excluded.messages,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at,
                revision = excluded.revision,
                pinned = excluded.pinned,
                archived = excluded.archived,
                deleted_at = excluded.deleted_at
            """,
            data,
        )
    else:
        conn.execute(
            """
            INSERT OR REPLACE INTO conversations
            (id, user_id, title, messages, created_at, updated_at, revision, pinned, archived, deleted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            data,
        )


def _move_chat_to_archive(conversation, deleted=False):
    archive_conn = get_db("archive_memory")
    try:
        item = dict(conversation)
        item["archived"] = not deleted
        if deleted:
            item["deleted_at"] = datetime.utcnow()
            item["pinned"] = False
            item["archived"] = False
        _insert_archive_conversation(archive_conn, item)
        archive_conn.commit()
    finally:
        archive_conn.close()

    chat_conn = get_db("chat")
    try:
        chat_conn.execute(
            "DELETE FROM conversations WHERE id = ? AND user_id = ?",
            (conversation["id"], conversation["user_id"]),
        )
        chat_conn.commit()
    finally:
        chat_conn.close()


def _move_archive_to_chat(conversation):
    chat_conn = get_db("chat")
    try:
        item = dict(conversation)
        item["archived"] = False
        item["deleted_at"] = None
        _insert_chat_conversation(chat_conn, item)
        chat_conn.commit()
    finally:
        chat_conn.close()

    archive_conn = get_db("archive_memory")
    try:
        archive_conn.execute(
            "DELETE FROM archived_conversations WHERE conversation_id = ? AND user_id = ?",
            (conversation["id"], conversation["user_id"]),
        )
        archive_conn.commit()
    finally:
        archive_conn.close()


def update_conversation(conversation_id, user_id, title, messages, expected_revision=None):
    owner, conversation = _find_conversation(conversation_id, user_id, include_deleted=False)
    if not conversation:
        return {"ok": False, "found": False, "conflict": False, "conversation": None}

    current_revision = int(conversation.get("revision", 0) or 0)
    if expected_revision is not None and int(expected_revision) != current_revision:
        return {"ok": False, "found": True, "conflict": True, "conversation": conversation}

    normalized = _normalize_messages_for_storage(messages, conversation_id)
    next_revision = current_revision + 1

    conn = get_db(owner)
    try:
        _begin_write(conn, owner)
        table = "conversations" if owner == "chat" else "archived_conversations"
        id_col = "id" if owner == "chat" else "conversation_id"
        conn.execute(
            f"""
            UPDATE {table}
            SET title = ?, messages = ?, updated_at = CURRENT_TIMESTAMP, revision = ?
            WHERE {id_col} = ? AND user_id = ?
            """,
            (title or "New Chat", json.dumps(normalized), next_revision, conversation_id, user_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {"ok": True, "found": True, "conflict": False, "conversation": get_conversation(conversation_id, user_id)}


def append_conversation_message(conversation_id, user_id, message):
    owner, conversation = _find_conversation(conversation_id, user_id, include_deleted=False)
    if not conversation:
        return None

    messages = _normalize_messages_for_storage(conversation.get("messages", []), conversation_id)
    item = dict(message) if isinstance(message, dict) else {"role": "assistant", "text": str(message)}
    if not item.get("id"):
        item["id"] = f"legacy-{conversation_id}-{len(messages)}"
    if str(item["id"]) in {str(m.get("id")) for m in messages if m.get("id")}:
        return conversation
    messages.append(item)

    return update_conversation(
        conversation_id,
        user_id,
        conversation.get("title") or "New Chat",
        messages,
        expected_revision=conversation.get("revision", 0),
    ).get("conversation")


def update_conversation_message(conversation_id, user_id, message_id, patch):
    conversation = get_conversation(conversation_id, user_id)
    if not conversation or conversation.get("deleted"):
        return None
    messages = _normalize_messages_for_storage(conversation.get("messages", []), conversation_id)
    found = False
    for message in messages:
        if str(message.get("id")) == str(message_id):
            for key, value in (patch or {}).items():
                if key in {"text", "content", "pinned", "feedback", "stopped"}:
                    message[key] = value
            found = True
            break
    if not found:
        return None
    result = update_conversation(
        conversation_id,
        user_id,
        conversation.get("title") or "New Chat",
        messages,
        expected_revision=conversation.get("revision", 0),
    )
    return result.get("conversation") if result.get("ok") else None


def delete_conversation_message(conversation_id, user_id, message_id):
    conversation = get_conversation(conversation_id, user_id)
    if not conversation or conversation.get("deleted"):
        return None
    messages = [
        m for m in _normalize_messages_for_storage(conversation.get("messages", []), conversation_id)
        if str(m.get("id")) != str(message_id)
    ]
    if len(messages) == len(conversation.get("messages", [])):
        return None
    result = update_conversation(
        conversation_id,
        user_id,
        conversation.get("title") or "New Chat",
        messages,
        expected_revision=conversation.get("revision", 0),
    )
    return result.get("conversation") if result.get("ok") else None


def update_conversation_metadata(conversation_id, user_id, pinned=None, archived=None, deleted=None):
    owner, conversation = _find_conversation(conversation_id, user_id, include_deleted=True)
    if not conversation:
        return None

    current_pinned = bool(conversation.get("pinned"))
    current_archived = bool(conversation.get("archived"))
    current_deleted = bool(conversation.get("deleted"))

    next_pinned = current_pinned if pinned is None else bool(pinned)
    next_archived = current_archived if archived is None else bool(archived)
    next_deleted = current_deleted if deleted is None else bool(deleted)

    # Deleted chats live in the low-use archive/memory database (Bin).
    if next_deleted:
        if owner == "chat":
            _move_chat_to_archive(conversation, deleted=True)
        else:
            conn = get_db("archive_memory")
            try:
                conn.execute(
                    """
                    UPDATE archived_conversations
                    SET deleted_at = CURRENT_TIMESTAMP, pinned = 0, archived = 0,
                        updated_at = CURRENT_TIMESTAMP, revision = revision + 1
                    WHERE conversation_id = ? AND user_id = ?
                    """,
                    (conversation_id, user_id),
                )
                conn.commit()
            finally:
                conn.close()
        return get_conversation(conversation_id, user_id)

    # Restore from Bin -> active chat DB.
    if owner == "archive_memory" and current_deleted and not next_deleted:
        _move_archive_to_chat(conversation)
        return get_conversation(conversation_id, user_id)

    # Archive active chat -> archive/memory DB.
    if owner == "chat" and next_archived:
        conversation["pinned"] = next_pinned
        _move_chat_to_archive(conversation, deleted=False)
        return get_conversation(conversation_id, user_id)

    # Unarchive -> active chat DB.
    if owner == "archive_memory" and current_archived and not next_archived and not current_deleted:
        _move_archive_to_chat(conversation)
        return get_conversation(conversation_id, user_id)

    # Metadata-only update within whichever database currently owns the chat.
    conn = get_db(owner)
    try:
        table = "conversations" if owner == "chat" else "archived_conversations"
        id_col = "id" if owner == "chat" else "conversation_id"
        conn.execute(
            f"""
            UPDATE {table}
            SET pinned = ?, archived = ?, updated_at = CURRENT_TIMESTAMP, revision = revision + 1
            WHERE {id_col} = ? AND user_id = ?
            """,
            (int(next_pinned), int(next_archived), conversation_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_conversation(conversation_id, user_id)


def delete_conversation(conversation_id, user_id):
    owner, conversation = _find_conversation(conversation_id, user_id, include_deleted=True)
    if not conversation:
        return False
    conn = get_db(owner)
    try:
        table = "conversations" if owner == "chat" else "archived_conversations"
        id_col = "id" if owner == "chat" else "conversation_id"
        conn.execute(
            f"DELETE FROM {table} WHERE {id_col} = ? AND user_id = ?",
            (conversation_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()
    return True


def delete_all_conversations(user_id):
    # Clear active chats and archived/bin chats. Memory is intentionally not
    # touched; "clear chats" must not erase long-term user memory.
    chat_conn = get_db("chat")
    try:
        chat_conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        chat_conn.commit()
    finally:
        chat_conn.close()

    archive_conn = get_db("archive_memory")
    try:
        archive_conn.execute("DELETE FROM archived_conversations WHERE user_id = ?", (user_id,))
        archive_conn.commit()
    finally:
        archive_conn.close()


# ---------------------------------------------------------------------------
# MEMORY + KNOWLEDGE (ARCHIVE/MEMORY DB)
# ---------------------------------------------------------------------------

def _get_legacy_memory(user_id, key=None):
    """Read memories from the old chat DB during the one-time migration window."""
    if not _database_url("chat") or _database_url("chat") == _database_url("archive_memory"):
        return None if key else {}
    conn = get_db("chat")
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
    except Exception:
        return None if key else {}
    finally:
        conn.close()


def get_memory(user_id, key=None):
    conn = get_db("archive_memory")
    try:
        if key:
            row = _fetchone(
                conn,
                "SELECT memory_key, memory_value FROM memories WHERE user_id = ? AND memory_key = ?",
                (user_id, key),
            )
            if row:
                return row["memory_value"]
        else:
            rows = _fetchall(conn, "SELECT memory_key, memory_value FROM memories WHERE user_id = ?", (user_id,))
            result = {row["memory_key"]: row["memory_value"] for row in rows}
            if result:
                return result
    finally:
        conn.close()

    legacy = _get_legacy_memory(user_id, key)
    if key:
        if legacy:
            save_memory(user_id, key, legacy)
        return legacy
    if legacy:
        for legacy_key, legacy_value in legacy.items():
            save_memory(user_id, legacy_key, legacy_value)
    return legacy or {}


def save_memory(user_id, key, value):
    conn = get_db("archive_memory")
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
    conn = get_db("archive_memory")
    try:
        conn.execute("DELETE FROM memories WHERE user_id = ? AND memory_key = ?", (user_id, key))
        conn.commit()
    finally:
        conn.close()


def clear_memory(user_id):
    conn = get_db("archive_memory")
    try:
        conn.execute("DELETE FROM memories WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def create_knowledge_table():
    _create_archive_memory_tables()


def get_vector_store_id(user_id):
    conn = get_db("archive_memory")
    try:
        row = _fetchone(conn, "SELECT vector_store_id FROM user_knowledge WHERE user_id = ?", (user_id,))
        if row:
            return row["vector_store_id"]
    finally:
        conn.close()

    # Seamless migration from the old single-DB layout.
    if _database_url("chat") and _database_url("chat") != _database_url("archive_memory"):
        conn = get_db("chat")
        try:
            row = _fetchone(conn, "SELECT vector_store_id FROM user_knowledge WHERE user_id = ?", (user_id,))
        except Exception:
            row = None
        finally:
            conn.close()
        if row and row["vector_store_id"]:
            save_vector_store_id(user_id, row["vector_store_id"])
            return row["vector_store_id"]

    return None


def save_vector_store_id(user_id, vector_store_id):
    conn = get_db("archive_memory")
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


# ---------------------------------------------------------------------------
# FILE METADATA (FILES DB)
# ---------------------------------------------------------------------------

def register_file(
    user_id,
    filename,
    mime_type=None,
    size_bytes=0,
    conversation_id=None,
    storage_backend="metadata-only",
    storage_key=None,
    external_file_id=None,
    status="received",
):
    extension = os.path.splitext(filename or "")[1].lower().lstrip(".") or None
    conn = get_db("files")
    try:
        if _use_postgres("files"):
            row = _fetchone(
                conn,
                """
                INSERT INTO files
                (user_id, conversation_id, filename, mime_type, extension, size_bytes,
                 storage_backend, storage_key, external_file_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (
                    user_id, conversation_id, filename or "", mime_type, extension,
                    int(size_bytes or 0), storage_backend, storage_key,
                    external_file_id, status,
                ),
            )
            file_id = row["id"]
        else:
            cursor = conn.execute(
                """
                INSERT INTO files
                (user_id, conversation_id, filename, mime_type, extension, size_bytes,
                 storage_backend, storage_key, external_file_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id, conversation_id, filename or "", mime_type, extension,
                    int(size_bytes or 0), storage_backend, storage_key,
                    external_file_id, status,
                ),
            )
            file_id = cursor.lastrowid
        conn.commit()
        return file_id
    finally:
        conn.close()


def update_file_record(file_id, user_id, **patch):
    allowed = {
        "storage_backend", "storage_key", "external_file_id", "status",
        "conversation_id", "size_bytes", "filename", "mime_type"
    }
    patch = {k: v for k, v in patch.items() if k in allowed}
    if not patch:
        return False

    conn = get_db("files")
    try:
        assignments = ", ".join(f"{key} = ?" for key in patch)
        values = list(patch.values()) + [file_id, user_id]
        conn.execute(
            f"UPDATE files SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
            values,
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_files(user_id, conversation_id=None):
    conn = get_db("files")
    try:
        if conversation_id is None:
            rows = _fetchall(
                conn,
                "SELECT * FROM files WHERE user_id = ? ORDER BY created_at DESC, id DESC",
                (user_id,),
            )
        else:
            rows = _fetchall(
                conn,
                "SELECT * FROM files WHERE user_id = ? AND conversation_id = ? ORDER BY created_at DESC, id DESC",
                (user_id, conversation_id),
            )
        return [dict(row) for row in rows]
    finally:
        conn.close()


if __name__ == "__main__":
    create_tables()
    print("ODDI three-database schema is ready.")
