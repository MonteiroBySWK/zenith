from flask import Flask, render_template, request
from flask.json import jsonify
from src.Manager import ManagerSystem

import pandas as pd

app = Flask(__name__)
manager = ManagerSystem()


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


@app.route('/api/retirada/<int:produto_id>', methods=['POST'])
def executar_fluxo_diario(produto_id):
    sucesso = manager.executar_fluxo_diario(produto_id)
    if sucesso:
        return jsonify({"message": "Fluxo diário executado com sucesso."}), 200
    else:
        return jsonify({"message": "Erro ao executar o fluxo diário."}), 500

@app.route('/api/lotes/<int:produto_id>', methods=['GET'])
def obter_lotes(produto_id):
    cursor = manager.conn.cursor()
    cursor.execute("SELECT * FROM lote WHERE produto_id = ?", (produto_id,))
    lotes = cursor.fetchall()
    return jsonify([dict(lote) for lote in lotes]), 200

@app.route('/api/criar_db', methods=['POST'])
def criar_banco():
    db_path = Path("estoque.db")
    manager.criar_banco_e_tabelas(db_path)
    return jsonify({"message": "Banco de dados criado com sucesso."}), 201

if __name__ == '__main__':
    app.run(debug=True)