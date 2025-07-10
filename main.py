from flask import Flask
from flask.json import jsonify

app = Flask(__name__)


@app.route("/")
def index():
    return "<h1>Hello World</h1>"


@app.route("/predict", methods=["GET, POST"])
def predict():
    # load predict model

    return """
       <p><p> 
    """


@app.route("/dashboard")
def dashboard():
    data = {"algo1": 1}
    return jsonify(data)


app.run("localhost", 8080, debug=True)
