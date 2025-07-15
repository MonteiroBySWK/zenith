import logging
from pathlib import Path
from typing import Dict, Any
import sqlite3
import pandas as pd
from typing import List, Dict
from queue import Queue

import createDB  # Importa o módulo que cria o banco e tabelas
from repositories import PrevisaoRepository, ProdutoRepository, LoteRepository, VendaRepository
import previsao  # Importa o módulo de previsão

# --- Configuração do Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

DB_PATH = Path("./enos/data/estoque.db")

# --- Configuração do Script ---
CONFIG: Dict[str, Any] = {
    "entrada": Path("./enos/data/dados_zenith.csv")
}

def logar_busca_previsoes(conn: sqlite3.Connection, sku: str) -> List[Dict[str, Any]]:
    """
    Busca previsões para o SKU fornecido e loga os resultados.
    """
    previsoes = PrevisaoRepository.buscar_previsoes(conn, sku)
    if not previsoes:
        logging.warning(f"Nenhuma previsão encontrada para SKU={sku}")
    else:
        logging.info(f"\n\nPrevisões encontradas para SKU={sku}: {len(previsoes)}")
        for p in previsoes:
            logging.info(f"Data: {p['data']}, Quantidade Prevista: {p['quantidade_prevista']} kg")
    return previsoes

def logar_busca_produtos(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Busca todos os produtos cadastrados e loga os resultados.
    """
    produtos = ProdutoRepository.buscar_produtos(conn)
    if not produtos:
        logging.warning("Nenhum produto encontrado no banco.")
    else:
        logging.info(f"\n\nProdutos encontrados: {len(produtos)}")
        for p in produtos:
            logging.info(f"SKU: {p['sku']}, Nome: {p['nome']}, Categoria: {p['categoria']}")
    return produtos

def atualizar_status_lote(conn: sqlite3.Connection, sku: str, data_venda: pd.Timestamp):
    fila = LoteRepository.buscar_lotes_por_produto_em_fila(conn, sku,data_venda)
    quantidade_vendida = VendaRepository.buscar_total_vendido_no_dia(conn, sku, data_venda.date())
    if fila.empty():   
        logging.warning(f"Nenhum lote encontrado para o SKU={sku}.")
        return
    else:
        lote = fila.get()
        for i in range(len(fila)):
            quantidade_atual = lote['quantidade_atual']
            resto = quantidade_atual - quantidade_vendida
            if resto > 0:
                lote['quantidade_atual'] = resto
                LoteRepository.atualizar_lote(conn, lote)
                return
            else:
                lote['quantidade_atual'] = 0
                LoteRepository.atualizar_lote(conn, lote)
                if i < len(fila) - 1:
                    lote = fila.get()
                else:
                    return
        LoteRepository.atualizar_idade_lotes(conn, sku, data_venda.date())

def main():
    with sqlite3.connect(DB_PATH) as conn:
        previsao.importar_vendas_csv(conn, CONFIG["entrada"])
        previsao.prever(conn)

        produtos = logar_busca_produtos(conn)
        previsoes = logar_busca_previsoes(conn, "237478")

if __name__ == "__main__":
    createDB.criar_banco_e_tabelas(DB_PATH)  # Cria o banco e tabelas se não existirem
    main()