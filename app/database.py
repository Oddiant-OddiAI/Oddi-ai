import sqlite3
import json

DATABASE = "users.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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


# ==========================================
# CONVERSATION FUNCTIONS
# ==========================================

def create_conversation(user_id, title="New Chat"):

    conn = get_db()

    cursor = conn.execute(
        """
        INSERT INTO conversations
        (user_id, title, messages)
        VALUES (?, ?, ?)
        """,
        (user_id, title, json.dumps([]))
    )

    conversation_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return conversation_id


def get_conversations(user_id):

    conn = get_db()

    rows = conn.execute(
        """
        SELECT id, user_id, title, messages, created_at
        FROM conversations
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,)
    ).fetchall()

    conn.close()

    conversations = []

    for row in rows:
        conversations.append({
            "id": row["id"],
            "user_id": row["user_id"],
            "title": row["title"],
            "messages": json.loads(row["messages"]),
            "created_at": row["created_at"]
        })

    return conversations


def get_conversation(conversation_id, user_id):

    conn = get_db()

    row = conn.execute(
        """
        SELECT id, user_id, title, messages, created_at
        FROM conversations
        WHERE id = ? AND user_id = ?
        """,
        (conversation_id, user_id)
    ).fetchone()

    conn.close()

    if not row:
        return None

    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "title": row["title"],
        "messages": json.loads(row["messages"]),
        "created_at": row["created_at"]
    }


def update_conversation(conversation_id, user_id, title, messages):

    conn = get_db()

    conn.execute(
        """
        UPDATE conversations
        SET title = ?, messages = ?
        WHERE id = ? AND user_id = ?
        """,
        (
            title,
            json.dumps(messages),
            conversation_id,
            user_id
        )
    )

    conn.commit()
    conn.close()


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


# ==========================================
# TEST DATABASE
# ==========================================

if __name__ == "__main__":

    create_tables()

    conn = get_db()

    users = conn.execute(
        "SELECT username, email, password_hash FROM users"
    ).fetchall()

    for user in users:
        print(dict(user))

    conn.close()