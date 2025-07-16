import logging
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd
from queue import Queue
import pymysql

import database as createDB  # Versão adaptada para MySQL
from repositories import PrevisaoRepository, ProdutoRepository, LoteRepository, VendaRepository
import previsao  # Já adaptado para pymysql

# --- Configuração de Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# --- Configuração do Script ---
CONFIG = {
    "entrada": Path("C:/Users/caiob/PycharmProjects/zenith/src/data/dados_zenith.csv")
}


# --- Configuração do Banco MySQL ---
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "root",
    "database": "estoque",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True
}


def logar_busca_previsoes(conn: pymysql.connections.Connection, sku: str) -> List[Dict[str, Any]]:
    previsoes = PrevisaoRepository.buscar_previsoes(conn, sku)
    if not previsoes:
        logging.warning(f"Nenhuma previsão encontrada para SKU={sku}")
    else:
        logging.info(f"\n\nPrevisões encontradas para SKU={sku}: {len(previsoes)}")
        for p in previsoes:
            logging.info(f"Data: {p['data']}, Quantidade Prevista: {p['quantidade_prevista']} kg")
    return previsoes


def logar_busca_produtos(conn: pymysql.connections.Connection) -> List[Dict[str, Any]]:
    produtos = ProdutoRepository.buscar_produtos(conn)
    if not produtos:
        logging.warning("Nenhum produto encontrado no banco.")
    else:
        logging.info(f"\n\nProdutos encontrados: {len(produtos)}")
        for p in produtos:
            logging.info(f"SKU: {p['sku']}, Nome: {p['nome']}, Categoria: {p['categoria']}")
    return produtos


def atualizar_status_lote(conn: pymysql.connections.Connection, sku: str, data_venda: pd.Timestamp):
    fila = LoteRepository.buscar_lotes_por_produto_em_fila(conn, sku, data_venda)
    quantidade_vendida = VendaRepository.buscar_total_vendido_no_dia(conn, sku, data_venda.date())

    if fila.empty():
        logging.warning(f"Nenhum lote encontrado para o SKU={sku}.")
        return

    lote = fila.get()
    for _ in range(fila.qsize()):
        quantidade_atual = lote['quantidade_atual']
        resto = quantidade_atual - quantidade_vendida

        if resto > 0:
            lote['quantidade_atual'] = resto
            LoteRepository.atualizar_lote(conn, lote)
            return
        else:
            lote['quantidade_atual'] = 0
            LoteRepository.atualizar_lote(conn, lote)
            if not fila.empty():
                lote = fila.get()
            else:
                return

    LoteRepository.atualizar_idade_lotes(conn, sku, data_venda.date())


def main():
    conn = pymysql.connect(**DB_CONFIG)
    try:
        previsao.importar_vendas_csv(conn, CONFIG["entrada"])
        previsao.prever(conn)

        produtos = logar_busca_produtos(conn)
        previsoes = logar_busca_previsoes(conn, "237478")
    except Exception as e:
        logging.error(f"Erro ao executar o sistema: {e}")
    finally:
        conn.close()



if __name__ == "__main__":
    createDB.criar_banco_e_tabelas()  # versão para MySQL
    main()
