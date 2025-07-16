import pymysql
import logging
import pandas as pd
from typing import Optional, List, Dict

conn = pymysql.connect(
    host='localhost',
    user='root',
    password='root',
    database='estoque',
    cursorclass=pymysql.cursors.DictCursor
)

def buscar_previsoes(conn: pymysql.Connection, sku: Optional[str] = None,
                     data_inicio: Optional[str] = None, data_fim: Optional[str] = None) -> List[Dict]:
    cursor = conn.cursor()
    query = """
        SELECT p.id, pr.sku, p.data, p.quantidade_prevista, p.produto_id, pr.nome
        FROM previsao p
        JOIN produto pr ON p.produto_id = pr.id
        WHERE 1=1
    """
    params = []
    if sku is not None:
        query += " AND pr.sku = %s"
        params.append(sku)
    if data_inicio is not None:
        query += " AND p.data >= %s"
        params.append(data_inicio)
    if data_fim is not None:
        query += " AND p.data <= %s"
        params.append(data_fim)

    cursor.execute(query, params)
    linhas = cursor.fetchall()

    previsoes = []
    for linha in linhas:
        previsoes.append({
            "id": linha["id"],
            "sku": linha["sku"],
            "data": linha["data"],
            "quantidade_prevista": linha["quantidade_prevista"],
            "produto_id": linha["produto_id"],
            "nome_produto": linha["nome"]
        })
    return previsoes


def obter_previsao(conn: pymysql.Connection, produto_id, data_venda):
    """Obtém a previsão de demanda para um produto em uma data específica"""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT quantidade_prevista FROM previsao WHERE produto_id = %s AND data = %s",
        (produto_id, data_venda.strftime("%Y-%m-%d")),
    )
    row = cursor.fetchone()
    return row["quantidade_prevista"] if row else None


def salvar_previsao_no_banco(conn: pymysql.Connection, sku: str, nome_produto: str,
                              categoria_produto: str, data_prevista: pd.Timestamp,
                              quantidade_prevista: float):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM produto WHERE sku = %s", (sku,))
    produto = cursor.fetchone()

    if produto:
        produto_id = produto["id"]
    else:
        cursor.execute(
            "INSERT INTO produto (sku, nome, categoria) VALUES (%s, %s, %s)",
            (sku, nome_produto, categoria_produto)
        )
        produto_id = cursor.lastrowid

    data_str = data_prevista.strftime("%Y-%m-%d")
    cursor.execute("SELECT id FROM previsao WHERE produto_id = %s AND data = %s",
                   (produto_id, data_str))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO previsao (data, quantidade_prevista, produto_id) VALUES (%s, %s, %s)",
                       (data_str, quantidade_prevista, produto_id))
        conn.commit()
