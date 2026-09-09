import sqlite3
import json
import os
import uuid

DATABASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "users.db")


def get_db():
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.DatabaseError:
        pass
    return conn


def create_tables():

    conn = get_db()

    # Users table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Conversations table
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

            FOREIGN KEY (user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
        )
    """)

    # Safe migrations for databases created by older ODDI versions.
    columns = {row[1] for row in conn.execute("PRAGMA table_info(conversations)").fetchall()}
    if "updated_at" not in columns:
        conn.execute("ALTER TABLE conversations ADD COLUMN updated_at TIMESTAMP")
        conn.execute("UPDATE conversations SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP) WHERE updated_at IS NULL")
    if "revision" not in columns:
        conn.execute("ALTER TABLE conversations ADD COLUMN revision INTEGER NOT NULL DEFAULT 0")
    if "pinned" not in columns:
        conn.execute("ALTER TABLE conversations ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")
    if "deleted_at" not in columns:
        conn.execute("ALTER TABLE conversations ADD COLUMN deleted_at TIMESTAMP NULL")

    # Memories table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            memory_key TEXT NOT NULL,
            memory_value TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (user_id)
            REFERENCES users(id)
            ON DELETE CASCADE,

            UNIQUE(user_id, memory_key)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_knowledge (
            user_id INTEGER PRIMARY KEY,
            vector_store_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

    print("Database tables ready.")


def create_user(username, email, password_hash):

    conn = get_db()

    conn.execute(
        """
        INSERT INTO users(username, email, password_hash)
        VALUES (?, ?, ?)
        """,
        (username, email, password_hash)
    )

    conn.commit()
    conn.close()


def get_user_by_email(email):

    conn = get_db()

    user = conn.execute(
        """
        SELECT * FROM users
        WHERE email = ?
        """,
        (email,)
    ).fetchone()

    conn.close()

    return user


def create_conversation(user_id, title="New Chat"):

    conn = get_db()

    cursor = conn.execute(
        """
        INSERT INTO conversations
        (user_id, title, messages, revision)
        VALUES (?, ?, ?, 0)
        """,
        (user_id, title, json.dumps([]))
    )

    conversation_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return conversation_id


def _normalize_messages_for_storage(messages, conversation_id):
    normalized = []
    for index, message in enumerate(messages if isinstance(messages, list) else []):
        item = dict(message) if isinstance(message, dict) else {
            "role": "assistant",
            "text": str(message)
        }
        if not item.get("id"):
            item["id"] = f"legacy-{conversation_id}-{index}"
        normalized.append(item)
    return normalized


def _conversation_dict(row):
    messages = json.loads(row["messages"])
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
        "deleted_at": row["deleted_at"]
    }


def get_conversations(user_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT id, user_id, title, messages, created_at, updated_at, revision, pinned, archived, deleted_at
        FROM conversations
        WHERE user_id = ? AND deleted_at IS NULL
        ORDER BY id DESC
    """, (user_id,)).fetchall()
    conn.close()
    return [_conversation_dict(row) for row in rows]


def get_deleted_conversations(user_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT id, user_id, title, messages, created_at, updated_at, revision, pinned, archived, deleted_at
        FROM conversations
        WHERE user_id = ? AND deleted_at IS NOT NULL
        ORDER BY deleted_at DESC, id DESC
    """, (user_id,)).fetchall()
    conn.close()
    return [_conversation_dict(row) for row in rows]


def get_conversation(conversation_id, user_id):
    conn = get_db()
    row = conn.execute("""
        SELECT id, user_id, title, messages, created_at, updated_at, revision, pinned, archived, deleted_at
        FROM conversations
        WHERE id = ? AND user_id = ?
    """, (conversation_id, user_id)).fetchone()
    conn.close()
    if not row:
        return None
    return _conversation_dict(row)


def update_conversation(conversation_id, user_id, title, messages, expected_revision=None):
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("""
            SELECT id, user_id, title, messages, created_at, updated_at, revision, pinned, archived, deleted_at
            FROM conversations
            WHERE id = ? AND user_id = ?
        """, (conversation_id, user_id)).fetchone()

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
        conn.execute("""
            UPDATE conversations
            SET title = ?, messages = ?, updated_at = CURRENT_TIMESTAMP, revision = ?
            WHERE id = ? AND user_id = ?
        """, (
            title or "New Chat",
            json.dumps(normalized),
            next_revision,
            conversation_id,
            user_id
        ))
        conn.commit()

        row = conn.execute("""
            SELECT id, user_id, title, messages, created_at, updated_at, revision, pinned, archived, deleted_at
            FROM conversations
            WHERE id = ? AND user_id = ?
        """, (conversation_id, user_id)).fetchone()
        return {"ok": True, "found": True, "conflict": False, "conversation": _conversation_dict(row)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def append_conversation_message(conversation_id, user_id, message):
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("""
            SELECT id, user_id, title, messages, created_at, updated_at, revision, pinned, archived, deleted_at
            FROM conversations
            WHERE id = ? AND user_id = ?
        """, (conversation_id, user_id)).fetchone()
        if not row:
            conn.rollback()
            return None

        current_messages = _normalize_messages_for_storage(json.loads(row["messages"]), conversation_id)
        item = dict(message) if isinstance(message, dict) else {"role": "assistant", "text": str(message)}
        if not item.get("id"):
            item["id"] = str(uuid.uuid4())

        existing_ids = {str(m.get("id")) for m in current_messages if m.get("id")}
        if str(item["id"]) in existing_ids:
            conn.rollback()
            return _conversation_dict(row)

        current_messages.append(item)

        next_revision = int(row["revision"] or 0) + 1
        conn.execute("""
            UPDATE conversations
            SET messages = ?, updated_at = CURRENT_TIMESTAMP, revision = ?
            WHERE id = ? AND user_id = ?
        """, (json.dumps(current_messages), next_revision, conversation_id, user_id))
        conn.commit()

        row = conn.execute("""
            SELECT id, user_id, title, messages, created_at, updated_at, revision, pinned, archived, deleted_at
            FROM conversations
            WHERE id = ? AND user_id = ?
        """, (conversation_id, user_id)).fetchone()
        return _conversation_dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_conversation_message(conversation_id, user_id, message_id, patch):
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("""
            SELECT id, user_id, title, messages, created_at, updated_at, revision, pinned, archived, deleted_at
            FROM conversations
            WHERE id = ? AND user_id = ?
        """, (conversation_id, user_id)).fetchone()
        if not row:
            conn.rollback()
            return None

        messages = _normalize_messages_for_storage(json.loads(row["messages"]), conversation_id)
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
        conn.execute("""
            UPDATE conversations
            SET messages = ?, updated_at = CURRENT_TIMESTAMP, revision = ?
            WHERE id = ? AND user_id = ?
        """, (json.dumps(messages), next_revision, conversation_id, user_id))
        conn.commit()

        row = conn.execute("""
            SELECT id, user_id, title, messages, created_at, updated_at, revision, pinned, archived, deleted_at
            FROM conversations
            WHERE id = ? AND user_id = ?
        """, (conversation_id, user_id)).fetchone()
        return _conversation_dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_conversation_message(conversation_id, user_id, message_id):
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("""
            SELECT id, user_id, title, messages, created_at, updated_at, revision, pinned, archived, deleted_at
            FROM conversations
            WHERE id = ? AND user_id = ?
        """, (conversation_id, user_id)).fetchone()
        if not row:
            conn.rollback()
            return None

        messages = _normalize_messages_for_storage(json.loads(row["messages"]), conversation_id)
        new_messages = [m for m in messages if str(m.get("id")) != str(message_id)]
        if len(new_messages) == len(messages):
            conn.rollback()
            return None

        next_revision = int(row["revision"] or 0) + 1
        conn.execute("""
            UPDATE conversations
            SET messages = ?, updated_at = CURRENT_TIMESTAMP, revision = ?
            WHERE id = ? AND user_id = ?
        """, (json.dumps(new_messages), next_revision, conversation_id, user_id))
        conn.commit()

        row = conn.execute("""
            SELECT id, user_id, title, messages, created_at, updated_at, revision, pinned, archived, deleted_at
            FROM conversations
            WHERE id = ? AND user_id = ?
        """, (conversation_id, user_id)).fetchone()
        return _conversation_dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_conversation_metadata(conversation_id, user_id, pinned=None, archived=None, deleted=None):
    conn = get_db()
    current = conn.execute("SELECT pinned, archived, deleted_at FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id)).fetchone()
    if not current:
        conn.close()
        return None
    next_pinned = int(bool(current["pinned"])) if pinned is None else int(bool(pinned))
    next_archived = int(bool(current["archived"])) if archived is None else int(bool(archived))
    if deleted is None:
        next_deleted = current["deleted_at"]
    else:
        next_deleted = __import__("datetime").datetime.utcnow().isoformat(timespec="seconds") if deleted else None
    if deleted is True:
        next_pinned = 0
        next_archived = 0
    conn.execute("""
        UPDATE conversations
        SET pinned = ?, archived = ?, deleted_at = ?,
            updated_at = CURRENT_TIMESTAMP,
            revision = revision + 1
        WHERE id = ? AND user_id = ?
    """, (next_pinned, next_archived, next_deleted, conversation_id, user_id))
    conn.commit()
    row = conn.execute("""SELECT id, user_id, title, messages, created_at, updated_at, revision, pinned, archived, deleted_at FROM conversations WHERE id = ? AND user_id = ?""", (conversation_id, user_id)).fetchone()
    conn.close()
    return _conversation_dict(row) if row else None


def delete_conversation(conversation_id, user_id):

    conn = get_db()

    conn.execute(
        """
        DELETE FROM conversations
        WHERE id = ? AND user_id = ?
        """,
        (conversation_id, user_id)
    )

    conn.commit()
    conn.close()


def delete_all_conversations(user_id):

    conn = get_db()

    conn.execute(
        """
        DELETE FROM conversations
        WHERE user_id = ?
        """,
        (user_id,)
    )

    conn.commit()
    conn.close()


def get_memory(user_id, key=None):

    conn = get_db()

    if key:
        row = conn.execute(
            """
            SELECT memory_key, memory_value
            FROM memories
            WHERE user_id = ? AND memory_key = ?
            """,
            (user_id, key)
        ).fetchone()

        conn.close()

        if not row:
            return None

        return row["memory_value"]

    rows = conn.execute(
        """
        SELECT memory_key, memory_value
        FROM memories
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchall()

    conn.close()

    return {
        row["memory_key"]: row["memory_value"]
        for row in rows
    }


def save_memory(user_id, key, value):

    conn = get_db()

    conn.execute(
        """
        INSERT INTO memories
        (user_id, memory_key, memory_value)
        VALUES (?, ?, ?)

        ON CONFLICT(user_id, memory_key)
        DO UPDATE SET
            memory_value = excluded.memory_value,
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, key, value)
    )

    conn.commit()
    conn.close()


def delete_memory(user_id, key):

    conn = get_db()

    conn.execute(
        """
        DELETE FROM memories
        WHERE user_id = ? AND memory_key = ?
        """,
        (user_id, key)
    )

    conn.commit()
    conn.close()


def clear_memory(user_id):

    conn = get_db()

    conn.execute(
        """
        DELETE FROM memories
        WHERE user_id = ?
        """,
        (user_id,)
    )

    conn.commit()
    conn.close()


def create_knowledge_table():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_knowledge (
            user_id INTEGER PRIMARY KEY,
            vector_store_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()


def get_vector_store_id(user_id):

    conn = get_db()

    row = conn.execute(
        """
        SELECT vector_store_id
        FROM user_knowledge
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()

    conn.close()

    if not row:
        return None

    return row["vector_store_id"]


def save_vector_store_id(user_id, vector_store_id):

    conn = get_db()

    conn.execute(
        """
        INSERT INTO user_knowledge
        (user_id, vector_store_id)
        VALUES (?, ?)

        ON CONFLICT(user_id)
        DO UPDATE SET
            vector_store_id = excluded.vector_store_id
        """,
        (user_id, vector_store_id)
    )

    conn.commit()
    conn.close()

if __name__ == "__main__":

    create_tables()

    conn = get_db()

    users = conn.execute(
        "SELECT username, email, password_hash FROM users"
    ).fetchall()

    for user in users:
        print(dict(user))

    conn.close()
