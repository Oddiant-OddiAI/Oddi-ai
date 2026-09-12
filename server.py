import json
import logging
import os
import secrets
from datetime import timedelta

from dotenv import load_dotenv
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from authlib.integrations.base_client import OAuthError
from authlib.integrations.flask_client import OAuth

from werkzeug.security import generate_password_hash, check_password_hash
from app.database import (
    create_tables,
    create_user,
    get_user_by_email,
    create_conversation,
    get_conversations,
    get_conversation,
    update_conversation,
    delete_conversation,
    delete_all_conversations,
    get_deleted_conversations,
    update_conversation_metadata,
    append_conversation_message,
    update_conversation_message,
    delete_conversation_message,
    get_memory,
    save_memory,
    delete_memory,
    register_file,
    update_file_record,
    get_files
)

from app.engine import process_message

load_dotenv()

app = Flask(__name__)

# Keep the secret server-side. In production, set FLASK_SECRET_KEY in .env
# rather than hard-coding it in source control.
app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "Oddi-AI_AI_2026_SuperSecretKey",
)

app.permanent_session_lifetime = timedelta(days=30)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("oddi.persistence")

oauth = OAuth(app)

google_client_id = os.getenv("GOOGLE_CLIENT_ID")
google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

if google_client_id and google_client_secret:
    oauth.register(
        name="google",
        server_metadata_url=(
            "https://accounts.google.com/"
            ".well-known/openid-configuration"
        ),
        client_id=google_client_id,
        client_secret=google_client_secret,
        client_kwargs={
            "scope": "openid profile email",
        },
    )
else:
    logger.warning(
        "Google OAuth is not configured. Set "
        "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env."
    )

create_tables()


@app.route("/")
def home():

    response = render_template(
        "index.html",
        logged_in=("user_id" in session),
        username=session.get("username"),
        user_id=session.get("user_id")
    )
    # The page contains the live conversation-sync JavaScript inline. Never
    # serve an older cached copy after a deployment, especially on mobile.
    rendered = app.make_response(response)
    rendered.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    rendered.headers["Pragma"] = "no-cache"
    rendered.headers["Expires"] = "0"
    return rendered

@app.route("/login")
def login_page():
    return render_template("login.html")
@app.route("/login", methods=["POST"])
def login():

    email = request.form["email"]
    password = request.form["password"]

    user = get_user_by_email(email)

    if not user:
        return "Email not found."

    if check_password_hash(user["password_hash"], password):
        session.permanent = True
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["email"] = user["email"]
        return redirect("/")

    return "Incorrect password."

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")
@app.route("/profile")
def profile():

    if "user_id" not in session:
        return "Not logged in."

    return f"""
    User ID: {session['user_id']}<br>
    Username: {session['username']}<br>
    Email: {session['email']}
    """

@app.route("/signup")
def signup_page():
    return render_template("signup.html")

@app.route("/signup", methods=["POST"])
def signup():

    username = request.form["username"]
    email = request.form["email"]
    password = request.form["password"]

    # Check if email already exists
    if get_user_by_email(email):
        return "Email already exists."

    # Hash password
    password_hash = generate_password_hash(password)

    # Save user
    create_user(username, email, password_hash)

    user = get_user_by_email(email)
    session.permanent = True
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["email"] = user["email"]

    return redirect("/")


# =========================
# React / Next.js Auth API
# =========================

@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}

    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({
            "success": False,
            "error": "Email and password are required."
        }), 400

    user = get_user_by_email(email)

    if user is None:
        return jsonify({
            "success": False,
            "error": "Email not found."
        }), 401

    if not check_password_hash(user["password_hash"], password):
        return jsonify({
            "success": False,
            "error": "Incorrect password."
        }), 401

    session.permanent = True
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["email"] = user["email"]

    return jsonify({
        "success": True,
        "user": {
            "id": user["id"],
            "name": user["username"],
            "email": user["email"]
        }
    })


@app.route("/api/auth/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or {}

    username = data.get("name", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not username or not email or not password:
        return jsonify({
            "success": False,
            "error": "Name, email and password are required."
        }), 400

    existing_user = get_user_by_email(email)

    if existing_user:
        return jsonify({
            "success": False,
            "error": "An account with this email already exists."
        }), 409

    password_hash = generate_password_hash(password)

    create_user(
        username,
        email,
        password_hash
    )

    user = get_user_by_email(email)

    if user is None:
        return jsonify({
            "success": False,
            "error": "Account was created but could not be loaded."
        }), 500

    session.permanent = True
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["email"] = user["email"]

    return jsonify({
        "success": True,
        "user": {
            "id": user["id"],
            "name": user["username"],
            "email": user["email"]
        }
    })

# =========================================================
# GOOGLE OAUTH
# =========================================================

@app.route("/auth/google")
def google_login():
    if not google_client_id or not google_client_secret:
        logger.error("Google OAuth requested but credentials are missing.")
        return (
            "Google sign-in is not configured. "
            "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env."
        ), 503

    redirect_uri = url_for(
        "google_callback",
        _external=True,
    )

    return oauth.google.authorize_redirect(
        redirect_uri,
    )


@app.route("/auth/google/callback")
def google_callback():
    try:
        token = oauth.google.authorize_access_token()
    except OAuthError as error:
        logger.warning("Google OAuth failed: %s", error)
        return redirect("/login")

    # With Google's OpenID Connect discovery, Authlib normally
    # places the verified identity data in token["userinfo"].
    userinfo = token.get("userinfo")

    # Be defensive: if userinfo was not included, fetch it from
    # Google's userinfo endpoint using the returned token.
    if not userinfo:
        try:
            response = oauth.google.userinfo(token=token)
            userinfo = response
        except Exception as error:
            logger.exception(
                "Unable to retrieve Google user information: %s",
                error,
            )
            return "Google account information could not be retrieved.", 502

    email = str(
        userinfo.get("email") or ""
    ).strip().lower()

    name = str(
        userinfo.get("name") or ""
    ).strip()

    email_verified = userinfo.get(
        "email_verified",
        False,
    )

    if not email:
        return "Google did not provide an email address.", 400

    if email_verified is not True:
        return "Google email is not verified.", 403

    # ODDI currently accepts Gmail accounts only.
    if not email.endswith("@gmail.com"):
        return (
            "Please use a Gmail account to sign in to ODDI."
        ), 403

    if not name:
        name = email.split("@")[0]

    # -----------------------------------------------------
    # Find existing ODDI account
    # -----------------------------------------------------
    user = get_user_by_email(email)

    # -----------------------------------------------------
    # First Google login:
    # create an ODDI account automatically.
    # -----------------------------------------------------
    if user is None:
        temporary_password = secrets.token_urlsafe(32)

        password_hash = generate_password_hash(
            temporary_password
        )

        create_user(
            name,
            email,
            password_hash,
        )

        user = get_user_by_email(email)

    if user is None:
        return (
            "Google login succeeded, "
            "but the ODDI account could not be created."
        ), 500

    # -----------------------------------------------------
    # Use the same Flask session as normal ODDI login.
    # -----------------------------------------------------
    session.permanent = True
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["email"] = user["email"]
    session["auth_provider"] = "google"

    return redirect("/")

@app.route("/api/auth/me", methods=["GET"])
def api_auth_me():
    user_id = session.get("user_id")

    if not user_id:
        return jsonify({
            "authenticated": False
        }), 401

    return jsonify({
        "authenticated": True,
        "user": {
            "id": session.get("user_id"),
            "name": session.get("username"),
            "email": session.get("email"),
        },
        "auth_provider": session.get("auth_provider", "password"),
    })


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.clear()

    return jsonify({
        "success": True
    })

@app.route("/api/conversations", methods=["GET"])
def api_get_conversations():

    logger.info("HTTP GET /api/conversations pid=%s user=%s", os.getpid(), session.get("user_id"))
    if "user_id" not in session:
        return jsonify({
            "error": "Not logged in."
        }), 401

    conversations = get_conversations(session["user_id"])

    return jsonify(conversations)


@app.route("/api/conversations", methods=["POST"])
def api_create_conversation():

    logger.info("HTTP POST /api/conversations pid=%s user=%s", os.getpid(), session.get("user_id"))
    if "user_id" not in session:
        return jsonify({
            "error": "Not logged in."
        }), 401

    data = request.get_json(silent=True) or {}

    title = data.get("title", "New Chat")

    conversation_id = create_conversation(
        session["user_id"],
        title
    )

    conversation = get_conversation(
        conversation_id,
        session["user_id"]
    )

    return jsonify({
        "success": True,
        **(conversation or {"id": conversation_id, "title": title, "messages": [], "revision": 0})
    }), 201


@app.route("/api/conversations/bin", methods=["GET"])
def api_get_deleted_conversations():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in."}), 401
    return jsonify(get_deleted_conversations(session["user_id"]))


@app.route("/api/conversations/<int:conversation_id>/metadata", methods=["PUT"])
def api_update_conversation_metadata(conversation_id):
    logger.info("HTTP PUT /api/conversations/%s/metadata pid=%s user=%s", conversation_id, os.getpid(), session.get("user_id"))
    if "user_id" not in session:
        return jsonify({"error": "Not logged in."}), 401
    data = request.get_json(silent=True) or {}
    allowed = {"pinned", "archived", "deleted"}
    patch = {key: data[key] for key in allowed if key in data}
    if not patch:
        return jsonify({"error": "No metadata changes supplied."}), 400
    updated = update_conversation_metadata(
        conversation_id, session["user_id"],
        pinned=patch.get("pinned"),
        archived=patch.get("archived"),
        deleted=patch.get("deleted")
    )
    if not updated:
        return jsonify({"error": "Conversation not found."}), 404
    return jsonify({"success": True, "conversation": updated})


@app.route("/api/conversations/<int:conversation_id>", methods=["GET"])
def api_get_conversation(conversation_id):

    if "user_id" not in session:
        return jsonify({
            "error": "Not logged in."
        }), 401

    conversation = get_conversation(
        conversation_id,
        session["user_id"]
    )

    if not conversation:
        return jsonify({
            "error": "Conversation not found."
        }), 404

    return jsonify(conversation)


@app.route("/api/conversations/<int:conversation_id>", methods=["PUT"])
def api_update_conversation(conversation_id):

    logger.info("HTTP PUT /api/conversations/%s pid=%s user=%s", conversation_id, os.getpid(), session.get("user_id"))
    if "user_id" not in session:
        return jsonify({
            "error": "Not logged in."
        }), 401

    data = request.get_json(silent=True) or {}

    title = data.get("title", "New Chat")
    messages = data.get("messages", [])
    expected_revision = data.get("expected_revision")

    result = update_conversation(
        conversation_id,
        session["user_id"],
        title,
        messages,
        expected_revision=expected_revision
    )

    if not result.get("found"):
        return jsonify({
            "error": "Conversation not found."
        }), 404

    if result.get("conflict"):
        return jsonify({
            "success": False,
            "conflict": True,
            "conversation": result["conversation"]
        }), 409

    return jsonify({
        "success": True,
        "conversation": result["conversation"]
    })


@app.route("/api/conversations/<int:conversation_id>/messages", methods=["POST"])
def api_append_conversation_message(conversation_id):

    logger.info("HTTP POST /api/conversations/%s/messages pid=%s user=%s", conversation_id, os.getpid(), session.get("user_id"))
    if "user_id" not in session:
        return jsonify({"error": "Not logged in."}), 401

    data = request.get_json(silent=True) or {}
    message = data.get("message")

    if not isinstance(message, dict):
        return jsonify({"error": "Message object is required."}), 400

    conversation = append_conversation_message(
        conversation_id,
        session["user_id"],
        message
    )

    if not conversation:
        return jsonify({"error": "Conversation not found."}), 404

    return jsonify({
        "success": True,
        "conversation": conversation
    })


@app.route("/api/conversations/<int:conversation_id>/messages/<message_id>", methods=["PUT"])
def api_update_conversation_message(conversation_id, message_id):

    logger.info("HTTP PUT /api/conversations/%s/messages/%s pid=%s user=%s", conversation_id, message_id, os.getpid(), session.get("user_id"))
    if "user_id" not in session:
        return jsonify({"error": "Not logged in."}), 401

    data = request.get_json(silent=True) or {}
    patch = data.get("patch", data)

    if not isinstance(patch, dict):
        return jsonify({"error": "Message patch must be an object."}), 400

    conversation = update_conversation_message(
        conversation_id,
        session["user_id"],
        message_id,
        patch
    )

    if not conversation:
        return jsonify({"error": "Conversation or message not found."}), 404

    return jsonify({
        "success": True,
        "conversation": conversation
    })


@app.route("/api/conversations/<int:conversation_id>/messages/<message_id>", methods=["DELETE"])
def api_delete_conversation_message(conversation_id, message_id):

    logger.warning("HTTP DELETE /api/conversations/%s/messages/%s pid=%s user=%s", conversation_id, message_id, os.getpid(), session.get("user_id"))
    if "user_id" not in session:
        return jsonify({"error": "Not logged in."}), 401

    conversation = delete_conversation_message(
        conversation_id,
        session["user_id"],
        message_id
    )

    if not conversation:
        return jsonify({"error": "Conversation or message not found."}), 404

    return jsonify({
        "success": True,
        "conversation": conversation
    })


@app.route("/api/conversations/<int:conversation_id>", methods=["DELETE"])
def api_delete_conversation(conversation_id):

    logger.warning("HTTP DELETE /api/conversations/%s pid=%s user=%s", conversation_id, os.getpid(), session.get("user_id"))
    if "user_id" not in session:
        return jsonify({
            "error": "Not logged in."
        }), 401

    conversation = get_conversation(
        conversation_id,
        session["user_id"]
    )

    if not conversation:
        return jsonify({
            "error": "Conversation not found."
        }), 404

    delete_conversation(
        conversation_id,
        session["user_id"]
    )

    return jsonify({
        "success": True
    })


@app.route("/api/conversations/clear", methods=["DELETE"])
def api_clear_conversations():

    logger.warning("HTTP DELETE /api/conversations/clear pid=%s user=%s", os.getpid(), session.get("user_id"))
    if "user_id" not in session:
        return jsonify({
            "error": "Not logged in."
        }), 401

    delete_all_conversations(
        session["user_id"]
    )

    return jsonify({
        "success": True
    })
# =========================================================
# MEMORY CONTROLS
# =========================================================
@app.route("/api/memory", methods=["GET"])
def api_get_memory():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in."}), 401

    memories = get_memory(session["user_id"]) or {}

    return jsonify({
        "memories": [
            {"category": key, "memory": value}
            for key, value in memories.items()
        ]
    })


@app.route("/api/memory", methods=["PUT"])
def api_update_memory():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in."}), 401

    data = request.get_json(silent=True) or {}
    key = str(data.get("key") or data.get("category") or "").strip()
    memory = str(data.get("memory") or data.get("value") or "").strip()

    if not key:
        return jsonify({"error": "Memory key is required."}), 400
    if not memory:
        return jsonify({"error": "Memory cannot be empty."}), 400

    existing = get_memory(session["user_id"], key)
    if existing is None:
        return jsonify({"error": "Memory not found."}), 404

    save_memory(session["user_id"], key, memory)

    return jsonify({
        "success": True,
        "category": key,
        "memory": memory
    })


@app.route("/api/memory", methods=["DELETE"])
def api_delete_memory():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in."}), 401

    data = request.get_json(silent=True) or {}
    key = str(data.get("key") or data.get("category") or "").strip()

    if not key:
        return jsonify({"error": "Memory key is required."}), 400

    existing = get_memory(session["user_id"], key)
    if existing is None:
        return jsonify({"error": "Memory not found."}), 404

    delete_memory(session["user_id"], key)

    return jsonify({
        "success": True,
        "deleted": key
    })


def _uploaded_file_size(uploaded_file):
    """Return upload size without consuming the Flask file stream."""
    try:
        current = uploaded_file.stream.tell()
        uploaded_file.stream.seek(0, 2)
        size = uploaded_file.stream.tell()
        uploaded_file.stream.seek(current)
        return int(size or 0)
    except Exception:
        return int(getattr(uploaded_file, "content_length", 0) or 0)


@app.route("/api/files", methods=["GET"])
def api_get_files():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in."}), 401

    conversation_id = request.args.get("conversation_id", type=int)
    return jsonify(get_files(session["user_id"], conversation_id=conversation_id))


@app.route("/chat", methods=["POST"])
def chat():

    message = request.form["message"]

    uploaded_files = request.files.getlist("files")
    conversation_id = request.form.get("conversation_id", type=int)

    # Record file metadata in the dedicated Files Neon database. The actual
    # binary file remains in the existing upload/processing pipeline for now;
    # this separation keeps chat PostgreSQL storage free of file metadata.
    file_record_ids = []
    if uploaded_files and session.get("user_id") is not None:
        for uploaded_file in uploaded_files:
            try:
                file_record_id = register_file(
                    user_id=session["user_id"],
                    filename=uploaded_file.filename or "unnamed-file",
                    mime_type=uploaded_file.mimetype,
                    size_bytes=_uploaded_file_size(uploaded_file),
                    conversation_id=conversation_id,
                    status="received",
                )
                file_record_ids.append(file_record_id)
            except Exception as file_db_error:
                # File metadata persistence must never prevent the user from
                # chatting or analyzing the upload.
                logger.warning("File metadata save failed: %s", file_db_error)

    # Get conversation history from frontend
    history_json = request.form.get("history", "[]")

    try:
        conversation_history = json.loads(history_json)
    except (json.JSONDecodeError, TypeError):
        conversation_history = []

    # Keep only the latest 100 messages
    conversation_history = conversation_history[-100:]

    if uploaded_files:
        print("Files received:")
        for file in uploaded_files:
            print(file.filename)
    else:
        print("No files uploaded")

    reply = process_message(
        message,
        uploaded_files,
        conversation_history,
        session.get("user_id")
    )

    # Mark successfully handed-off uploads as processed. If ODDI raises before
    # this point, their records intentionally remain "received" for diagnosis.
    if file_record_ids:
        for file_record_id in file_record_ids:
            try:
                update_file_record(
                    file_record_id,
                    session["user_id"],
                    status="processed",
                )
            except Exception as file_db_error:
                logger.warning("File metadata status update failed: %s", file_db_error)

    return reply


if __name__ == "__main__":
    app.run(debug=True)