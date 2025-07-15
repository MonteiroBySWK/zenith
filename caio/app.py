"""
Previsão de venda para 7 dias após o último dado disponível com Prophet,
usando todo o histórico disponível e validando com os últimos 7 dias reais.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import numpy as np
import holidays
from sklearn.metrics import mean_squared_error
from prophet import Prophet

import createDB  # Criação do banco e tabelas
import scriptsDB  # Funções de acesso ao banco

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
    "dias_prev": 7          # previsão para 7 dias à frente
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
            cursor.execute(
                "INSERT INTO produto (sku, nome, categoria) VALUES (?, ?, ?)",
                (sku, nome, "Desconhecida")  # categoria padrão
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
    # Usa todo o período, sem limitar
    return df

def treinar_e_prever(df: pd.DataFrame) -> pd.DataFrame:
    """
    Treina Prophet usando todo o histórico do DataFrame,
    prevê próximos 7 dias, e valida contra últimos 7 dias reais se existirem.
    """
    df = df.sort_values('data_dia').reset_index(drop=True)

    if len(df) > CONFIG["dias_prev"]:
        df_treino = df[:-CONFIG["dias_prev"]].copy()
        df_teste_real = df[-CONFIG["dias_prev"]:].copy()
    else:
        df_treino = df.copy()
        df_teste_real = None

    df_prophet = df_treino.rename(columns={'data_dia': 'ds', 'total_venda_dia_kg': 'y'})

    # Adiciona feriados Brasil
    anos = df_prophet['ds'].dt.year.unique().tolist()
    feriados = holidays.Brazil(years=anos)
    feriados_df = pd.DataFrame([
        {'holiday': 'feriado', 'ds': pd.to_datetime(date), 'lower_window': 0, 'upper_window': 1}
        for date in feriados.keys()
    ])

    model = Prophet(
        yearly_seasonality=False,
        weekly_seasonality=True,
        daily_seasonality=False,
        changepoint_prior_scale=0.01,
        holidays=feriados_df
    )
    model.add_seasonality(name='weekly_custom', period=7, fourier_order=3)
    model.fit(df_prophet)

    future = model.make_future_dataframe(periods=CONFIG["dias_prev"])
    forecast = model.predict(future)

    previsoes = forecast[['ds', 'yhat']].tail(CONFIG["dias_prev"]).reset_index(drop=True)

    if df_teste_real is not None and len(df_teste_real) == CONFIG["dias_prev"]:
        previsoes['real'] = df_teste_real['total_venda_dia_kg'].values
        previsoes['erro_abs'] = (previsoes['yhat'] - previsoes['real']).abs()
        mae = previsoes['erro_abs'].mean()
        rmse = np.sqrt(mean_squared_error(previsoes['real'], previsoes['yhat']))

        logging.info("🔎 Comparação dos últimos 7 dias:")
        for i, row in previsoes.iterrows():
            data_str = row['ds'].strftime("%d/%m/%Y")
            logging.info(f"{data_str} → Previsto: {row['yhat']:.2f} kg | Real: {row['real']:.2f} kg | Erro absoluto: {row['erro_abs']:.2f}")
        logging.info(f"📊 MAE (Erro Médio Absoluto): {mae:.2f} kg")
        logging.info(f"📈 RMSE (Erro Médio Quadrático): {rmse:.2f} kg")
    else:
        logging.info("Não há dados suficientes para validação de erro (últimos 7 dias ausentes).")

    return previsoes[['ds', 'yhat']]

def salvar_previsoes_no_banco(
    conn: sqlite3.Connection,
    df: pd.DataFrame,
    skus_unicos: pd.DataFrame
):
    for _, row in skus_unicos.iterrows():
        sku = str(row['id_produto'])
        nome_produto = row['descricao_produto']
        categoria_produto = "Frango"

        df_produto = df[df['id_produto'] == row['id_produto']].copy()
        if df_produto.empty:
            logging.warning(f"Sem dados para o produto SKU={sku}")
            continue

        previsoes = treinar_e_prever(df_produto)

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
        sincronizar_produtos_csv_banco(conn, df)

        skus_unicos = df[['id_produto', 'descricao_produto']].drop_duplicates()
        salvar_previsoes_no_banco(conn, df, skus_unicos)

        produtos = scriptsDB.buscar_produtos(conn)
        logging.info(f"Produtos cadastrados: {len(produtos)}")
        for produto in produtos:
            logging.info(f"SKU: {produto['sku']}, Nome: {produto['nome']}, Categoria: {produto['categoria']}")

        previsoes = scriptsDB.buscar_previsoes(conn, '237478')
        logging.info(f"Previsões encontradas: {len(previsoes)}")
        for previsao in previsoes:
            logging.info(f"Previsão: {previsao['data']} - {previsao['quantidade_prevista']} kg para SKU {previsao['sku']}")

if __name__ == "__main__":
    createDB.criar_banco_e_tabelas(DB_PATH)
    main()
