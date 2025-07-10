from flask import Flask, render_template, request
from flask.json import jsonify

import pandas as pd

app = Flask(__name__)


@app.route("/")
def index():
    return "<div style='height: 100vh; width: 100%; display: flex; justify-content: center; align-items: center;'><h1>It's Work!</h1></div>"

@app.route("/upload", methods=["GET"])
def upload():
    return render_template("upload.html")

@app.route("/predict", methods=["POST"])
def predict():
    if 'file' not in request.files: 
        return jsonify({"error": "Nenhum arquivo enviado"}), 400
    

    file = request.files['file']

    if file.filename.endswith('.csv'):
        df = pd.read_csv(file)
    elif file.filename.endswith(('.xls', '.xlsx')):
        df = pd.read_excel(file)
    else:
        return jsonify({"error": "Formato de arquivo não suportado"}), 400

    result = {
        "linhas": df.shape[0],
        "colunas": df.shape[1],
        "colunas_nome": df.columns.tolist()
    }

    return jsonify(result), 200


@app.route("/dashboard")
def dashboard():
    data = {"algo1": 1}
    return jsonify(data)


app.run("localhost", 8080, debug=True)
