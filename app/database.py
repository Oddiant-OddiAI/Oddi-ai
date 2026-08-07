import sqlite3

DATABASE = "users.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

    print("Users table ready.")


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
if __name__ == "__main__":

    conn = get_db()

    users = conn.execute(
        "SELECT username, email, password_hash FROM users"
    ).fetchall()

    for user in users:
        print(dict(user))

    conn.close()