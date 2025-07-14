from flask import Flask, render_template, request
from flask.json import jsonify

import pandas as pd

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["GET"])
def upload():
    return render_template("upload.html")


def read_file(file):
    if file.filename.endswith(".csv"):
        df = pd.read_csv(file)
    elif file.filename.endswith((".xls", ".xlsx")):
        df = pd.read_excel(file)
    else:
        return jsonify({"error": "Formato de arquivo não suportado"}), 400

    result = {
        "linhas": df.shape[0],
        "colunas": df.shape[1],
        "colunas_nome": df.columns.tolist(),
    }

    return result

def predict_model(data):
    # Modelo de predição aqui, retornar um excel? 
    # Não sei se é pra retornar a previsão de um dia ou de uma determinada serie
    ...

@app.route("/predict", methods=["POST"])
def predict():
    # Essa função deve ser melhor pensada
    if "file" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    file = request.files["file"]

    result = read_file(file)

    # aqui vem o predict(data)
    # puta merda isso tá muito mal escrito

    return jsonify(result), 200


@app.route("/report")
def report():
    # gerar o relatorio ou algo assim não se vai ficar assim no final
    ...

@app.route("/dashboard")
def dashboard():
    data = {"algo1": 1}
    return jsonify(data)


app.run("localhost", 8080, debug=True)
