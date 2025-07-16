from pathlib import Path
import numpy as np
from sqlalchemy import create_engine
import pandas as pd
import pymysql
import logging
from typing import Union, Dict, Any
from prophet import Prophet
import holidays
from sklearn.metrics import mean_squared_error

from src.repositories import ProdutoRepository, PrevisaoRepository

engine = create_engine("mysql+pymysql://usuario:root@localhost:3306/estoque")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

CONFIG: Dict[str, Any] = {
    "dias_prev": 7
}


def importar_vendas_csv(conn: pymysql.connections.Connection, caminho_csv: Union[str, Path]):
    df = pd.read_csv(caminho_csv, parse_dates=["data_dia"], dayfirst=True)

    with conn.cursor() as cursor:
        total_linhas = 0
        produtos_criados = 0
        vendas_inseridas = 0

        for _, row in df.iterrows():
            sku = str(row["id_produto"])
            nome = row["descricao_produto"]
            categoria = row["Equipe responsável"]
            data = row["data_dia"].strftime("%Y-%m-%d")
            quantidade = float(row["total_venda_dia_kg"])

            cursor.execute("SELECT id FROM produto WHERE sku = %s", (sku,))
            resultado = cursor.fetchone()

            if resultado:
                produto_id = resultado["id"]
            else:
                cursor.execute(
                    "INSERT INTO produto (sku, nome, categoria) VALUES (%s, %s, %s)",
                    (sku, nome, categoria)
                )
                produto_id = cursor.lastrowid
                produtos_criados += 1
                logging.info(f"Produto criado: SKU={sku}, Nome={nome}")

            cursor.execute(
                "SELECT id FROM venda WHERE produto_id = %s AND data = %s",
                (produto_id, data)
            )
            if cursor.fetchone():
                logging.warning(f"Venda já registrada para SKU={sku} em {data}. Ignorando.")
                continue

            cursor.execute(
                "INSERT INTO venda (data, quantidade, produto_id) VALUES (%s, %s, %s)",
                (data, quantidade, produto_id)
            )
            vendas_inseridas += 1
            total_linhas += 1

        conn.commit()

    logging.info(f"Importação finalizada: {produtos_criados} produtos criados, {vendas_inseridas} vendas inseridas, {total_linhas} linhas processadas.")


def carregar_dados_do_banco(sku: str) -> pd.DataFrame:
    query = """
        SELECT v.data, SUM(v.quantidade) as total_venda_dia_kg
        FROM venda v
        JOIN produto p ON v.produto_id = p.id
        WHERE p.sku = %s
        GROUP BY v.data
        ORDER BY v.data ASC
    """
    df = pd.read_sql(query, engine, params=(sku,))
    df['data_dia'] = pd.to_datetime(df['data'])
    df = df.drop(columns=['data'])
    return df


def treinar_e_prever(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values('data_dia').reset_index(drop=True)

    if len(df) > CONFIG["dias_prev"]:
        df_treino = df[:-CONFIG["dias_prev"]].copy()
        df_teste_real = df[-CONFIG["dias_prev"]:].copy()
    else:
        df_treino = df.copy()
        df_teste_real = None

    df_prophet = df_treino.rename(columns={'data_dia': 'ds', 'total_venda_dia_kg': 'y'})

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

        logging.info("\n🔎 Validação dos últimos 7 dias:")
        for i, row in previsoes.iterrows():
            logging.info(f"{row['ds'].date()} | Previsto: {row['yhat']:.2f} | Real: {row['real']:.2f} | Erro: {row['erro_abs']:.2f}")
        logging.info(f"\nMAE: {mae:.2f} kg | RMSE: {rmse:.2f} kg")

    return previsoes[['ds', 'yhat']]


def salvar_previsoes(conn: pymysql.connections.Connection, sku: str, nome_produto: str, previsoes: pd.DataFrame):
    for _, row in previsoes.iterrows():
        PrevisaoRepository.salvar_previsao_no_banco(
            conn=conn,
            sku=sku,
            nome_produto=nome_produto,
            categoria_produto="Frango",
            data_prevista=pd.Timestamp(row['ds']),
            quantidade_prevista=row['yhat']
        )


def prever(conn: pymysql.connections.Connection):
    produtos = ProdutoRepository.buscar_produtos(conn)

    for produto in produtos:
        sku = produto['sku']
        nome = produto['nome']

        df = carregar_dados_do_banco(conn, sku)
        if df.empty:
            logging.warning(f"Nenhuma venda encontrada para SKU={sku}")
            continue

        previsoes = treinar_e_prever(df)
        salvar_previsoes(conn, sku, nome, previsoes)
        logging.info(f"Previsões salvas no banco para SKU={sku}")
