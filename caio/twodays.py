import customtkinter as ctk
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import numpy as np
import scriptsDB  # Funções: buscar_previsoes()

# Configuração de estilo
ctk.set_appearance_mode("dark")  # "light" ou "system"
ctk.set_default_color_theme("blue")  # Tema azul moderno

DB_PATH = "estoque.db"


def calcular_desvio_padrao_2dias(previsoes: List[Dict]) -> Optional[float]:
    hoje = datetime.today().date()
    horizonte = [hoje + timedelta(days=i) for i in range(1, 3)]
    previsoes_filtradas = [
        p for p in previsoes if pd.to_datetime(p['data']).date() in horizonte
    ]
    quantidades = [p['quantidade_prevista'] for p in previsoes_filtradas]
    if len(quantidades) < 2:
        return None
    return np.std(quantidades, ddof=1)


# --- Interface ---
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Previsão de Vendas - Zenith")
        self.geometry("600x400")
        self.configure(padx=20, pady=20)

        self.title_label = ctk.CTkLabel(
            self, text="Consulta de Previsão de Vendas", font=ctk.CTkFont(size=20, weight="bold")
        )
        self.title_label.pack(pady=10)

        self.sku_entry = ctk.CTkEntry(self, placeholder_text="Digite o SKU do produto")
        self.sku_entry.pack(pady=10)

        self.search_button = ctk.CTkButton(self, text="Buscar Previsões", command=self.buscar_previsoes)
        self.search_button.pack(pady=10)

        self.result_text = ctk.CTkTextbox(self, width=500, height=200)
        self.result_text.pack(pady=10)

    def buscar_previsoes(self):
        sku = self.sku_entry.get().strip()
        self.result_text.delete("0.0", "end")

        if not sku:
            self.result_text.insert("0.0", "Por favor, insira um SKU.")
            return

        try:
            with sqlite3.connect(DB_PATH) as conn:
                previsoes = scriptsDB.buscar_previsoes(conn, sku)
                if not previsoes:
                    self.result_text.insert("0.0", f"Nenhuma previsão encontrada para SKU {sku}.")
                    return

                texto = f"Previsões para SKU {sku}:\n\n"
                hoje = datetime.today().date()
                horizonte = [hoje + timedelta(days=i) for i in range(1, 3)]

                for p in previsoes:
                    data = pd.to_datetime(p['data']).date()
                    if data in horizonte:
                        texto += f"{data.strftime('%d/%m/%Y')}: {p['quantidade_prevista']:.2f} kg\n"

                desvio = calcular_desvio_padrao_2dias(previsoes)
                if desvio is not None:
                    texto += f"\nDesvio padrão (2 dias): {desvio:.2f} kg"
                else:
                    texto += "\nNão há dados suficientes para calcular o desvio padrão."

                self.result_text.insert("0.0", texto)
        except Exception as e:
            self.result_text.insert("0.0", f"Erro ao consultar: {str(e)}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
