"""
Previsão de venda para 2 dias após o último dado de 3 meses (90 dias) com Prophet.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any
from typing import Dict

import pandas as pd

import createDB  # Importa o módulo que cria o banco e tabelas
import scriptsDB  # Importa o módulo com funções de acesso ao banco

# --- Configuração do Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

DB_PATH = Path("estoque.db")

# --- Configuração do Script ---
CONFIG: Dict[str, Any] = {
    "entrada": Path("dados_zenith.csv"),
    "col_data": "data_dia",
    "col_alvo": "total_venda_dia_kg",
    "fmt_data": "%d/%m/%Y",
    "dias_treino": 90,        # 3 meses
    "dias_prev": 30            # previsão para 30 dias à frente
}

def sincronizar_produtos_csv_banco(
    conn: sqlite3.Connection,
    df: pd.DataFrame,
    arquivo_saida: Path = Path("produtos_nao_cadastrados.csv")
):
    """
    Verifica cada produto do DataFrame CSV no banco pelo SKU.
    Insere produtos novos no banco.
    Salva produtos não cadastrados num CSV.
    """
    cursor = conn.cursor()
    
    produtos_nao_cadastrados = []
    
    skus_unicos = df[['id_produto', 'descricao_produto']].drop_duplicates()
    
    for _, row in skus_unicos.iterrows():
        sku = str(row['id_produto'])
        nome = row['descricao_produto']
        
        cursor.execute("SELECT id FROM produto WHERE sku = ?", (sku,))
        existe = cursor.fetchone()
        
        if not existe:
            produtos_nao_cadastrados.append({'sku': sku, 'nome': nome})
            # Opcional: pode inserir já o produto no banco aqui, se quiser:
            cursor.execute(
                "INSERT INTO produto (sku, nome, categoria) VALUES (?, ?, ?)",
                (sku, nome, "Desconhecida")  # categoria padrão, ou você pode adaptar
            )
            logging.info(f"Produto inserido no banco: SKU={sku}, nome={nome}")
    
    conn.commit()
    
    if produtos_nao_cadastrados:
        df_nao_cadastrados = pd.DataFrame(produtos_nao_cadastrados)
        df_nao_cadastrados.to_csv(arquivo_saida, index=False)
        logging.info(f"Produtos não cadastrados salvos em {arquivo_saida}")
    else:
        logging.info("Todos os produtos do CSV já existem no banco.")

def carregar_dados(cfg: Dict[str, Any]) -> pd.DataFrame:
    df = pd.read_csv(cfg["entrada"], dayfirst=True)
    df[cfg["col_data"]] = pd.to_datetime(df[cfg["col_data"]], format=cfg["fmt_data"])
    df = df.sort_values(cfg["col_data"]).reset_index(drop=True)

    # Pegando apenas os últimos 90 dias
    df = df.tail(cfg["dias_treino"]).reset_index(drop=True)
    return df


from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics


def treinar_e_prever(df: pd.DataFrame, cfg: Dict[str, Any]) -> pd.DataFrame:
    """
    Treina o modelo Prophet e retorna previsões futuras com validação de erro.
    """
    df_prophet = df[[cfg["col_data"], cfg["col_alvo"]]].rename(
        columns={cfg["col_data"]: "ds", cfg["col_alvo"]: "y"}
    )

    # --- Ajustes recomendados para séries curtas (90 dias) ---
    model = Prophet(
        yearly_seasonality=False,
        weekly_seasonality=True,
        daily_seasonality=False,
        changepoint_prior_scale=0.01
    )

    # Customização opcional da sazonalidade semanal
    model.add_seasonality(name='weekly_custom', period=7, fourier_order=3)

    model.fit(df_prophet)

    # --- Previsão futura ---
    future = model.make_future_dataframe(periods=cfg["dias_prev"])
    forecast = model.predict(future)

    # Filtrar apenas previsões futuras
    data_final_treino = df_prophet["ds"].max()
    previsoes_futuras = forecast[forecast["ds"] > data_final_treino][["ds", "yhat"]].copy()

    # --- Validação com Cross-Validation ---
    try:
        df_cv = cross_validation(
            model,
            initial="60 days",
            period="15 days",
            horizon="2 days",
            parallel="processes"  # melhora desempenho
        )
        df_p = performance_metrics(df_cv)
        mae = df_p["mae"].mean()
        rmse = df_p["rmse"].mean()
        print(f"MAE médio: {mae:.2f} | RMSE médio: {rmse:.2f}")
    except Exception as e:
        print(f"[!] Validação não foi possível: {e}")

    return previsoes_futuras


def salvar_previsoes_no_banco(
    conn: sqlite3.Connection,
    df: pd.DataFrame,
    skus_unicos: pd.DataFrame
):
    for _, row in skus_unicos.iterrows():
            sku = str(row['id_produto'])
            nome_produto = row['descricao_produto']
            categoria_produto = "Frango"
            
            df_produto = df[df['id_produto'] == row['id_produto']]
            if df_produto.empty:
                logging.warning(f"Sem dados para o produto SKU={sku}")
                continue
            
            previsoes = treinar_e_prever(df_produto, CONFIG)
            
            for _, prev in previsoes.iterrows():
                data_prevista = prev["ds"].date()
                quantidade_prevista = prev["yhat"]
                scriptsDB.salvar_previsao_no_banco(
                    conn, sku, nome_produto, categoria_produto,
                    pd.Timestamp(data_prevista), quantidade_prevista
                )

def main():
    df = carregar_dados(CONFIG)
    
    with sqlite3.connect(DB_PATH) as conn:
        # Sincroniza produtos CSV no banco e salva CSV dos novos produtos
        sincronizar_produtos_csv_banco(conn, df)
        
        skus_unicos = df[['id_produto', 'descricao_produto']].drop_duplicates()
        salvar_previsoes_no_banco(conn, df, skus_unicos)

        # Exemplo de consulta (pode remover se quiser)
        produtos = scriptsDB.buscar_produtos(conn)
        logging.info(f"Produtos cadastrados: {len(produtos)}")
        for produto in produtos:
            logging.info(f"SKU: {produto['sku']}, Nome: {produto['nome']}, Categoria: {produto['categoria']}") 
        previsoes = scriptsDB.buscar_previsoes(conn, '237478')
        logging.info(f"Previsões encontradas: {len(previsoes)}")
        for previsao in previsoes:
            logging.info(f"Previsão: {previsao['data']} - {previsao['quantidade_prevista']} kg para SKU {previsao['sku']}")




if __name__ == "__main__":
    createDB.criar_banco_e_tabelas(DB_PATH)  # Cria o banco e tabelas se não existirem
    main()