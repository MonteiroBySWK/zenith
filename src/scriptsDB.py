import sqlite3
import logging
import pandas as pd
from typing import List, Dict, Optional
from queue import Queue
from datetime import date

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

def buscar_lotes_por_produto_em_fila(
    conn: sqlite3.Connection,
    sku: str,
    data_atual: str  # formato 'YYYY-MM-DD'
) -> Queue:
    """
    Busca todos os lotes do produto com o SKU fornecido,
    apenas com status 'sobra' ou 'disponivel',
    com precedência para 'sobra',
    e que estejam disponíveis em data_atual
    (data_retirado + idade <= data_atual),
    ordenados por idade (mais velho primeiro) e menor quantidade_atual.
    Retorna os resultados em uma fila FIFO.
    """
    cursor = conn.cursor()

    # Busca o ID do produto com o SKU
    cursor.execute("SELECT id FROM produto WHERE sku = ?", (sku,))
    produto = cursor.fetchone()
    
    if not produto:
        logging.warning(f"Produto com SKU={sku} não encontrado.")
        return Queue()

    produto_id = produto[0]

    # Busca os lotes com status válido e disponíveis até a data_atual
    cursor.execute("""
        SELECT id, quantidade_retirada, quantidade_atual, idade, status, 
               data_retirado, data_venda, data_expiracao
        FROM lote
        WHERE produto_id = ?
        AND status IN ('sobra', 'disponivel')
        AND DATE(data_retirado, '+' || idade || ' days') <= DATE(?)
        ORDER BY 
            CASE status
                WHEN 'sobra' THEN 0
                WHEN 'disponivel' THEN 1
            END ASC,
            quantidade_atual ASC,
            idade ASC
    """, (produto_id, data_atual))

    lotes = cursor.fetchall()

    fila = Queue()
    for lote in lotes:
        lote_dict: Dict = {
            "id": lote[0],
            "quantidade_retirada": lote[1],
            "quantidade_atual": lote[2],
            "idade": lote[3],
            "status": lote[4],
            "data_retirado": lote[5],
            "data_venda": lote[6],
            "data_expiracao": lote[7],
        }
        fila.put(lote_dict)

    logging.info(f"{fila.qsize()} lotes enfileirados para SKU={sku} até {data_atual}.")
    return fila

def salvar_venda_no_banco(
    conn: sqlite3.Connection,
    sku: str,
    data_venda: str,  # formato 'YYYY-MM-DD'
    quantidade: float
):
    """
    Salva uma venda no banco de dados associada ao produto com o SKU informado.
    Se o produto não existir, a venda não é registrada.
    """
    cursor = conn.cursor()

    # Busca o ID do produto pelo SKU
    cursor.execute("SELECT id FROM produto WHERE sku = ?", (sku,))
    resultado = cursor.fetchone()

    if not resultado:
        logging.warning(f"Produto com SKU={sku} não encontrado. Venda não registrada.")
        return

    produto_id = resultado[0]

    # Insere a venda
    cursor.execute(
        """
        INSERT INTO venda (data, quantidade, produto_id)
        VALUES (?, ?, ?)
        """,
        (data_venda, quantidade, produto_id)
    )

    conn.commit()
    logging.info(f"Venda registrada: SKU={sku}, Data={data_venda}, Quantidade={quantidade}")

def buscar_total_vendido_no_dia(conn: sqlite3.Connection, data_venda: str = None) -> float:
    """
    Retorna o total de kg vendidos na data especificada (YYYY-MM-DD).
    Se nenhuma data for fornecida, usa a data atual.
    """
    cursor = conn.cursor()

    if data_venda is None:
        data_venda = date.today().isoformat()

    query = """
        SELECT SUM(quantidade) 
        FROM venda 
        WHERE data = ?
    """
    cursor.execute(query, (data_venda,))
    resultado = cursor.fetchone()

    total_vendido = resultado[0] if resultado[0] is not None else 0.0
    return total_vendido