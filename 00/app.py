from flask import Flask, request
import os

app = Flask(__name__)


@app.route("/")
def index():
    return "Hi"


@app.route("/get-flag", methods=["POST"])
def get_flag():
    if request.args.get("seriously") != "true":
        return "33", 403
        return "Access denied", 403

    if request.form.get("please") != "pretty please":
        return "Accdess denied", 403

    return os.environ.get("FLAG", "pitfalls{fake_flag}")


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8080)
