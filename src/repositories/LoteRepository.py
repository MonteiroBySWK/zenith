import pymysql
import logging
from queue import Queue
from typing import Dict
from datetime import datetime, timedelta

conn = pymysql.connect(
    host='localhost',
    user='root',
    password='root',
    database='estoque',
    cursorclass=pymysql.cursors.DictCursor  # Importante!
)

def buscar_lotes_por_produto_em_fila(
    conn: pymysql.Connection, sku: str, data_atual: str
) -> Queue:
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM produto WHERE sku = %s", (sku,))
    produto = cursor.fetchone()
    if not produto:
        return Queue()

    produto_id = produto["id"]
    cursor.execute(
        """
        SELECT id, quantidade_retirada, quantidade_atual, idade, status, 
               data_retirado, data_venda, data_expiracao
        FROM lote
        WHERE produto_id = %s
        AND status IN ('sobra', 'disponivel')
        AND DATE_ADD(data_retirado, INTERVAL idade DAY) <= %s
        ORDER BY 
            CASE status WHEN 'sobra' THEN 0 WHEN 'disponivel' THEN 1 END,
            quantidade_atual ASC,
            idade ASC
        """,
        (produto_id, data_atual),
    )

    fila = Queue()
    for lote in cursor.fetchall():
        fila.put(
            {
                "id": lote["id"],
                "quantidade_retirada": lote["quantidade_retirada"],
                "quantidade_atual": lote["quantidade_atual"],
                "idade": lote["idade"],
                "status": lote["status"],
                "data_retirado": lote["data_retirado"],
                "data_venda": lote["data_venda"],
                "data_expiracao": lote["data_expiracao"],
            }
        )
    return fila


def criar_lote(conn: pymysql.Connection, produto_id, quantidade_bruta, data_retirada):
    """Cria um novo lote no sistema"""
    quantidade_liquida = quantidade_bruta * 0.85  # ALPHA
    data_venda = data_retirada + timedelta(days=2)
    data_expiracao = data_retirada + timedelta(days=4)

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO lote (
            quantidade_retirada,
            quantidade_atual,
            idade,
            status,
            data_retirado,
            data_venda,
            data_expiracao,
            produto_id
        ) VALUES (%s, %s, 0, 'descongelando', %s, %s, %s, %s)
        """,
        (
            quantidade_liquida,
            quantidade_liquida,
            data_retirada.strftime("%Y-%m-%d"),
            data_venda.strftime("%Y-%m-%d"),
            data_expiracao.strftime("%Y-%m-%d"),
            produto_id,
        ),
    )
    conn.commit()
    logging.info(
        f"Novo lote criado: {quantidade_bruta:.2f}kg bruto -> {quantidade_liquida:.2f}kg líquido"
    )


def obter_retirada_anterior(conn: pymysql.Connection, produto_id, data_hoje):
    """Obtém a retirada do dia anterior (t-1) para o produto"""
    data_ontem = (data_hoje - timedelta(days=1)).strftime("%Y-%m-%d")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT quantidade_retirada FROM lote WHERE produto_id = %s AND data_retirado = %s",
        (produto_id, data_ontem),
    )
    row = cursor.fetchone()
    return row["quantidade_retirada"] if row else 0.0


def atualizar_status_lotes_diario(conn: pymysql.Connection, data_hoje):
    """Atualiza o status dos lotes baseado na data atual"""
    cursor = conn.cursor()
    data_hoje_str = data_hoje.strftime("%Y-%m-%d")

    cursor.execute(
        """
        UPDATE lote
        SET status = 'disponivel'
        WHERE data_venda = %s AND status = 'descongelando'
        """,
        (data_hoje_str,),
    )

    cursor.execute(
        """
        UPDATE lote
        SET status = 'sobra'
        WHERE data_venda < %s AND status = 'disponivel' AND quantidade_atual > 0
        """,
        (data_hoje_str,),
    )

    cursor.execute(
        """
        UPDATE lote
        SET status = 'perda'
        WHERE data_expiracao <= %s AND status IN ('disponivel', 'sobra')
        """,
        (data_hoje_str,),
    )

    cursor.execute(
        """
        UPDATE lote
        SET status = 'vendido'
        WHERE data_venda <= %s AND status IN ('disponivel', 'sobra') AND quantidade_atual = 0
        """,
        (data_hoje_str,),
    )

    conn.commit()
    logging.info("Status dos lotes atualizados")
