import sqlite3
import logging
import pandas as pd
from typing import List, Dict, Optional

def buscar_produtos(conn: sqlite3.Connection) -> List[Dict]:
    """
    Busca todos os produtos no banco e retorna lista de dicionários.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id, sku, nome, categoria FROM produto")
    linhas = cursor.fetchall()
    
    produtos = []
    for id_, sku, nome, categoria in linhas:
        produtos.append({
            "id": id_,
            "sku": sku,
            "nome": nome,
            "categoria": categoria
        })
    return produtos

def buscar_previsoes(
    conn: sqlite3.Connection,
    sku: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None
) -> List[Dict]:
    """
    Busca previsões no banco, filtrando por SKU e intervalo de datas (YYYY-MM-DD).
    Retorna lista de dicionários.
    """
    cursor = conn.cursor()
    query = """
        SELECT p.id, pr.sku, p.data, p.quantidade_prevista, p.produto_id, pr.nome
        FROM previsao p
        JOIN produto pr ON p.produto_id = pr.id
        WHERE 1=1
    """
    params = []
    if sku is not None:
        query += " AND pr.sku = ?"
        params.append(sku)
    if data_inicio is not None:
        query += " AND p.data >= ?"
        params.append(data_inicio)
    if data_fim is not None:
        query += " AND p.data <= ?"
        params.append(data_fim)

    cursor.execute(query, params)
    linhas = cursor.fetchall()

    previsoes = []
    for id_, sku, data_, quantidade_prevista, produto_id_, nome_produto in linhas:
        previsoes.append({
            "id": id_,
            "sku": sku,
            "data": data_,
            "quantidade_prevista": quantidade_prevista,
            "produto_id": produto_id_,
            "nome_produto": nome_produto
        })
    return previsoes

def salvar_previsao_no_banco(
    conn: sqlite3.Connection,
    sku: str,
    nome_produto: str,
    categoria_produto: str,
    data_prevista: pd.Timestamp,
    quantidade_prevista: float
):
    c = conn.cursor()

    # Verifica se o produto já existe
    c.execute("SELECT id FROM produto WHERE sku = ?", (sku,))
    produto = c.fetchone()

    if produto:
        produto_id = produto[0]
        logging.info(f"Produto existente encontrado (SKU={sku}, id={produto_id})")
    else:
        # Insere novo produto
        c.execute(
            "INSERT INTO produto (sku, nome, categoria) VALUES (?, ?, ?)",
            (sku, nome_produto, categoria_produto)
        )
        produto_id = c.lastrowid
        logging.info(f"Novo produto inserido (SKU={sku}, id={produto_id})")

    data_str = data_prevista.strftime("%Y-%m-%d")

    # Verifica se já existe previsão para o produto e data
    c.execute(
        "SELECT id FROM previsao WHERE produto_id = ? AND data = ?",
        (produto_id, data_str)
    )
    previsao_existente = c.fetchone()

    if previsao_existente:
        logging.warning(f"Previsão para SKU={sku} na data {data_str} já existe. Ignorando inserção.")
    else:
        # Inserção corrigida: sem coluna 'sku'
        c.execute(
            """
            INSERT INTO previsao (data, quantidade_prevista, produto_id)
            VALUES (?, ?, ?)
            """,
            (data_str, quantidade_prevista, produto_id)
        )
        logging.info(f"Previsão inserida para SKU={sku} na data {data_str}")

    conn.commit()