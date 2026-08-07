from flask import Flask, render_template, request

from app.engine import process_message

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")


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