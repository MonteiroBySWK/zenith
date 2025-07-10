from flask import Flask, render_template, request
from flask.json import jsonify

app = Flask(__name__)


@app.route("/")
def index():
    return "<div style='height: 100vh; width: 100%; display: flex; justify-content: center; align-items: center;'><h1>It's Work!</h1></div>"


@app.route("/predict", methods=["GET", "POST"])
def predict():
    # load predict model

    if request.method == "POST":
        return "<p>POST</p>"
    else:
        return render_template("/predict.html")


@app.route("/dashboard")
def dashboard():
    data = {"algo1": 1}
    return jsonify(data)


app.run("localhost", 8080, debug=True)
