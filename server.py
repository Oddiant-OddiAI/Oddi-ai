import json
from flask import (
    Flask,
    render_template,
    request,
    session,
    redirect,
    jsonify
)

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
    delete_all_conversations
)

from app.engine import process_message

app = Flask(__name__)

app.secret_key = "Oddi-AI_AI_2026_SuperSecretKey"

create_tables()


@app.route("/")
def home():

    return render_template(
        "index.html",
        logged_in=("user_id" in session),
        username=session.get("username")
    )

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

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["email"] = user["email"]

    return redirect("/")

# ==========================================
# CONVERSATION API
# ==========================================

@app.route("/api/conversations", methods=["GET"])
def api_get_conversations():

    if "user_id" not in session:
        return jsonify({
            "error": "Not logged in."
        }), 401

    conversations = get_conversations(session["user_id"])

    return jsonify(conversations)


@app.route("/api/conversations", methods=["POST"])
def api_create_conversation():

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

    return jsonify({
        "success": True,
        "id": conversation_id,
        "title": title
    }), 201


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

    if "user_id" not in session:
        return jsonify({
            "error": "Not logged in."
        }), 401

    data = request.get_json(silent=True) or {}

    title = data.get("title", "New Chat")
    messages = data.get("messages", [])

    conversation = get_conversation(
        conversation_id,
        session["user_id"]
    )

    if not conversation:
        return jsonify({
            "error": "Conversation not found."
        }), 404

    update_conversation(
        conversation_id,
        session["user_id"],
        title,
        messages
    )

    return jsonify({
        "success": True
    })


@app.route("/api/conversations/<int:conversation_id>", methods=["DELETE"])
def api_delete_conversation(conversation_id):

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
@app.route("/chat", methods=["POST"])
def chat():

    message = request.form["message"]

    uploaded_files = request.files.getlist("files")

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
    return reply


if __name__ == "__main__":
    app.run(debug=True)