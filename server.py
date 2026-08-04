from flask import Flask, render_template, request

from app.engine import process_message

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():

    message = request.form["message"]

    reply = process_message(message)

    return reply


if __name__ == "__main__":
    app.run(debug=True)