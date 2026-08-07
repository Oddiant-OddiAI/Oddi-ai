from flask import (
    Flask,
    render_template,
    request,
    session,
    redirect
)
from werkzeug.security import generate_password_hash, check_password_hash
from app.database import (
    create_tables,
    create_user,
    get_user_by_email
)
from app.engine import process_message

app = Flask(__name__)

app.secret_key = "VedAura_AI_2026_SuperSecretKey"

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

    return "Account created successfully!"

@app.route("/chat", methods=["POST"])
def chat():

    message = request.form["message"]
    uploaded_files = request.files.getlist("files")
    if uploaded_files:
        print("Files received:")
        for file in uploaded_files:
            print(file.filename)
    else:
        print("No files uploaded")
    reply = process_message(message, uploaded_files)

    return reply


if __name__ == "__main__":
    app.run(debug=True)