import sqlite3
import logging
from queue import Queue
from typing import Dict

def buscar_lotes_por_produto_em_fila(conn: sqlite3.Connection, sku: str, data_atual: str) -> Queue:
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM produto WHERE sku = ?", (sku,))
    produto = cursor.fetchone()
    if not produto:
        return Queue()

    produto_id = produto[0]
    cursor.execute("""
        SELECT id, quantidade_retirada, quantidade_atual, idade, status, 
               data_retirado, data_venda, data_expiracao
        FROM lote
        WHERE produto_id = ?
        AND status IN ('sobra', 'disponivel')
        AND DATE(data_retirado, '+' || idade || ' days') <= DATE(?)
        ORDER BY 
            CASE status WHEN 'sobra' THEN 0 WHEN 'disponivel' THEN 1 END ASC,
            quantidade_atual ASC,
            idade ASC
    """, (produto_id, data_atual))

    fila = Queue()
    for lote in cursor.fetchall():
        fila.put({
            "id": lote[0],
            "quantidade_retirada": lote[1],
            "quantidade_atual": lote[2],
            "idade": lote[3],
            "status": lote[4],
            "data_retirado": lote[5],
            "data_venda": lote[6],
            "data_expiracao": lote[7],
        })
    return fila