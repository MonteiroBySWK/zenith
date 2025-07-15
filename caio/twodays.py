# Importação das bibliotecas necessárias
import customtkinter as ctk  # Interface gráfica moderna baseada em Tkinter
import pandas as pd          # Manipulação de dados com DataFrames
import sqlite3               # Conexão com banco de dados SQLite
from datetime import datetime, timedelta  # Manipulação de datas
from typing import List, Dict, Optional   # Tipagens para melhor clareza e segurança
import numpy as np           # Cálculos numéricos e estatísticos
import scriptsDB             # Módulo próprio com funções de acesso ao banco

# Configuração visual da interface
ctk.set_appearance_mode("dark")  # Define o modo escuro
ctk.set_default_color_theme("blue")  # Define o tema azul

# Caminho do banco de dados
DB_PATH = "estoque.db"

# Função para calcular o desvio padrão das previsões dos próximos dois dias
def calcular_desvio_padrao_2dias(previsoes: List[Dict]) -> Optional[float]:
    hoje = datetime.today().date()
    horizonte = [hoje + timedelta(days=i) for i in range(1, 3)]  # Amanhã e depois
    previsoes_filtradas = [
        p for p in previsoes if pd.to_datetime(p['data']).date() in horizonte
    ]
    quantidades = [p['quantidade_prevista'] for p in previsoes_filtradas]
    if len(quantidades) < 2:
        return None  # Não é possível calcular desvio padrão com menos de 2 pontos
    return np.std(quantidades, ddof=1)  # ddof=1 para desvio amostral

# Classe principal da interface gráfica
class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configurações básicas da janela
        self.title("Previsão de Vendas - Zenith")
        self.geometry("600x400")
        self.configure(padx=20, pady=20)

        # Título da aplicação
        self.title_label = ctk.CTkLabel(
            self, text="Consulta de Previsão de Vendas", font=ctk.CTkFont(size=20, weight="bold")
        )
        self.title_label.pack(pady=10)

        # Campo para digitar o SKU do produto
        self.sku_entry = ctk.CTkEntry(self, placeholder_text="Digite o SKU do produto")
        self.sku_entry.pack(pady=10)

        # Botão para buscar previsões no banco
        self.search_button = ctk.CTkButton(self, text="Buscar Previsões", command=self.buscar_previsoes)
        self.search_button.pack(pady=10)

        # Botão para testar o modelo Prophet com os últimos 7 dias
        self.test_button = ctk.CTkButton(self, text="Testar Modelo (7 dias)", command=self.testar_modelo_prophet)
        self.test_button.pack(pady=10)

        # Caixa de texto para exibir os resultados
        self.result_text = ctk.CTkTextbox(self, width=500, height=200)
        self.result_text.pack(pady=10)

    # Função para testar o modelo Prophet e comparar com os últimos 7 dias reais
    def testar_modelo_prophet(self):
        try:
            import holidays
            from prophet import Prophet
            from sklearn.metrics import mean_squared_error  # ⬅️ Import necessário

            # Carrega dados
            df = pd.read_csv("dados_zenith.csv", dayfirst=True)
            df['data_dia'] = pd.to_datetime(df['data_dia'], format='%d/%m/%Y')
            df = df.sort_values("data_dia").reset_index(drop=True)

            # Divide entre treino e teste
            df_treino = df[:-7].tail(83).reset_index(drop=True)
            df_teste_real = df[-7:].reset_index(drop=True)

            # Formata para o Prophet
            df_prophet = df_treino.rename(columns={
                "data_dia": "ds",
                "total_venda_dia_kg": "y"
            })

            # Define feriados
            feriados = holidays.Brazil(years=df_prophet['ds'].dt.year.unique().tolist())
            feriados_df = pd.DataFrame([
                {'holiday': 'feriado', 'ds': pd.to_datetime(date), 'lower_window': 0, 'upper_window': 1}
                for date in feriados.keys()
            ])

            # Treina modelo
            model = Prophet(
                yearly_seasonality=False,
                weekly_seasonality=True,
                daily_seasonality=False,
                changepoint_prior_scale=0.01,
                holidays=feriados_df
            )
            model.add_seasonality(name='weekly_custom', period=7, fourier_order=3)
            model.fit(df_prophet)

            # Faz previsões
            future = model.make_future_dataframe(periods=7)
            forecast = model.predict(future)
            previsoes = forecast[['ds', 'yhat']].tail(7).reset_index(drop=True)

            # Compara com valores reais
            previsoes['real'] = df_teste_real['total_venda_dia_kg']
            previsoes['erro_abs'] = (previsoes['yhat'] - previsoes['real']).abs()
            mae = previsoes['erro_abs'].mean()
            rmse = np.sqrt(mean_squared_error(previsoes['real'], previsoes['yhat']))  # ⬅️ RMSE

            # Monta o texto de comparação
            texto = "🔎 Comparação (últimos 7 dias):\n\n"
            for i, row in previsoes.iterrows():
                data = row['ds'].strftime("%d/%m/%Y")
                texto += f"{data} → Previsto: {row['yhat']:.2f} kg | Real: {row['real']:.2f} kg | Erro: {row['erro_abs']:.2f}\n"

            texto += f"\n📊 MAE (Erro Médio Absoluto): {mae:.2f} kg"
            texto += f"\n📈 RMSE (Erro Médio Quadrático): {rmse:.2f} kg"  # ⬅️ Exibição

            # Exibe resultado
            self.result_text.delete("0.0", "end")
            self.result_text.insert("0.0", texto)

        except Exception as e:
            self.result_text.delete("0.0", "end")
            self.result_text.insert("0.0", f"Erro no teste do modelo: {str(e)}")

    # Função para buscar previsões futuras de um SKU específico no banco
    def buscar_previsoes(self):
        sku = self.sku_entry.get().strip()
        self.result_text.delete("0.0", "end")

        if not sku:
            self.result_text.insert("0.0", "Por favor, insira um SKU.")
            return

        try:
            with sqlite3.connect(DB_PATH) as conn:
                previsoes = scriptsDB.buscar_previsoes(conn, sku)  # busca no banco
                if not previsoes:
                    self.result_text.insert("0.0", f"Nenhuma previsão encontrada para SKU {sku}.")
                    return

                texto = f"Previsões para SKU {sku}:\n\n"
                hoje = datetime.today().date()
                horizonte = [hoje + timedelta(days=i) for i in range(1, 3)]  # amanhã e depois

                # Exibe apenas as previsões para os próximos dois dias
                for p in previsoes:
                    data = pd.to_datetime(p['data']).date()
                    if data in horizonte:
                        texto += f"{data.strftime('%d/%m/%Y')}: {p['quantidade_prevista']:.2f} kg\n"

                # Calcula o desvio padrão dessas previsões
                desvio = calcular_desvio_padrao_2dias(previsoes)
                if desvio is not None:
                    texto += f"\nDesvio padrão (2 dias): {desvio:.2f} kg"
                else:
                    texto += "\nNão há dados suficientes para calcular o desvio padrão."

                self.result_text.insert("0.0", texto)

        except Exception as e:
            self.result_text.insert("0.0", f"Erro ao consultar: {str(e)}")

# Execução principal da aplicação
if __name__ == "__main__":
    app = App()
    app.mainloop()
