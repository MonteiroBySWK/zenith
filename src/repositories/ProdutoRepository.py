import pymysql
from typing import List, Dict

conn = pymysql.connect(
    host='localhost',
    user='root',
    password='root',
    database='estoque',
    cursorclass=pymysql.cursors.DictCursor
)

def buscar_produtos(conn: pymysql.Connection) -> List[Dict]:
    cursor = conn.cursor()
    cursor.execute("SELECT id, sku, nome, categoria FROM produto")
    linhas = cursor.fetchall()

    produtos = []
    for linha in linhas:
        produtos.append({
            "id": linha["id"],
            "sku": linha["sku"],
            "nome": linha["nome"],
            "categoria": linha["categoria"]
        })
    return produtos
