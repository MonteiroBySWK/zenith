import pymysql
from datetime import date
from typing import Optional

pymysql.connect(
    host='localhost',
    user='root',
    password='root',
    database='estoque',
    cursorclass=pymysql.cursors.DictCursor
)


def salvar_venda_no_banco(
    conn: pymysql.Connection, sku: str, data_venda: str, quantidade: float
):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM produto WHERE sku = %s", (sku,))
    resultado = cursor.fetchone()

    if not resultado:
        return

    produto_id = resultado["id"]
    cursor.execute(
        "INSERT INTO venda (data, quantidade, produto_id) VALUES (%s, %s, %s)",
        (data_venda, quantidade, produto_id),
    )
    conn.commit()


def buscar_total_vendido_no_dia(
    conn: pymysql.Connection, data_venda: Optional[str] = None
) -> float:
    cursor = conn.cursor()
    if data_venda is None:
        data_venda = date.today().isoformat()

    cursor.execute("SELECT SUM(quantidade) AS total FROM venda WHERE data = %s", (data_venda,))
    resultado = cursor.fetchone()
    return resultado["total"] if resultado and resultado["total"] else 0.0


def obter_demanda_media(conn: pymysql.Connection, produto_id: int) -> float:
    """Calcula a demanda média do produto"""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT AVG(quantidade) AS media FROM venda WHERE produto_id = %s", (produto_id,)
    )
    row = cursor.fetchone()
    return row["media"] if row and row["media"] else 0.0
