from datetime import datetime, timedelta
import pymysql
import numpy as np
import logging
from pathlib import Path

import src.repositories.PrevisaoRepository as PrevisaoRepository
import src.repositories.VendaRepository as VendaRepository
import src.repositories.LoteRepository as LoteRepository

import src.previsao

# Configuração de logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

MYSQL_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'estoque',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}


class ManagerSystem:
    def __init__(self):
        self.conn = pymysql.connect(**MYSQL_CONFIG)
        self.k = 1.65  # Fator de segurança para 95% de confiança
        self.alpha = 0.85  # Fator de retração (15% de perda)
        self.validade_dias = 2  # Validade após descongelamento

    def calcular_desvio_padrao(self, produto_id, horizonte=2):
        """Calcula o desvio padrão dos erros de previsão"""
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.quantidade_prevista, v.quantidade
                FROM previsao p
                JOIN venda v ON p.produto_id = v.produto_id AND p.data = v.data
                WHERE p.produto_id = %s
                ORDER BY p.data DESC
                LIMIT 30
                """,
                (produto_id,)
            )
            dados = cursor.fetchall()

        if not dados:
            return 0.0

        erros = [row["quantidade"] - row["quantidade_prevista"] for row in dados]
        return np.std(erros)

    def calcular_retirada(self, produto_id, data_hoje):
        """Calcula R(t) - quantidade a ser retirada hoje (kg brutos)"""
        data_venda = data_hoje + timedelta(days=2)

        Vp_t2 = PrevisaoRepository.obter_previsao(self.conn, produto_id, data_venda)

        if Vp_t2 is None:
            Vp_t2 = VendaRepository.obter_demanda_media(self.conn, produto_id)
            logging.warning(
                f"Previsão não encontrada para produto {produto_id}. Usando demanda média: {Vp_t2}"
            )

        m_t2 = self.calcular_desvio_padrao(produto_id)
        R_t1 = LoteRepository.obter_retirada_anterior(self.conn, produto_id, data_hoje)

        R_t = (Vp_t2 + self.k * m_t2 - self.alpha * R_t1) / self.alpha

        demanda_media = VendaRepository.obter_demanda_media(self.conn, produto_id)
        R_max = (2 * demanda_media) / self.alpha

        R_t = max(0, R_t)
        R_t = min(R_t, R_max)

        return R_t

    def registrar_venda(self, produto_id, data, quantidade):
        """Registra uma venda real e atualiza os lotes"""
        data_str = data.strftime("%Y-%m-%d")

        with self.conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO venda (data, quantidade, produto_id) VALUES (%s, %s, %s)",
                (data_str, quantidade, produto_id)
            )

            cursor.execute(
                """
                SELECT id, quantidade_atual
                FROM lote
                WHERE produto_id = %s AND status IN ('disponivel', 'sobra') AND data_venda <= %s
                ORDER BY data_retirado
                """,
                (produto_id, data_str)
            )

            lotes = cursor.fetchall()
            quantidade_restante = quantidade

            for lote in lotes:
                if quantidade_restante <= 0:
                    break

                consumo = min(lote['quantidade_atual'], quantidade_restante)
                nova_quantidade = lote['quantidade_atual'] - consumo
                quantidade_restante -= consumo

                cursor.execute(
                    "UPDATE lote SET quantidade_atual = %s WHERE id = %s",
                    (nova_quantidade, lote['id'])
                )

                if nova_quantidade <= 0:
                    cursor.execute(
                        "UPDATE lote SET status = 'vendido' WHERE id = %s",
                        (lote['id'],)
                    )

            self.conn.commit()
            logging.info(f"Venda registrada: {quantidade}kg para produto {produto_id}")
            return quantidade_restante

    def executar_fluxo_diario(self, produto_id):
        """Executa todo o fluxo diário para um produto"""
        data_hoje = datetime.now().date()

        try:
            LoteRepository.atualizar_status_lotes_diario(self.conn, data_hoje)
            R_t = self.calcular_retirada(produto_id, data_hoje)
            logging.info(
                f"Produto {produto_id}: Quantidade a retirar hoje: {R_t:.2f}kg"
            )

            LoteRepository.criar_lote(self.conn, produto_id, R_t, data_hoje)

            # Exemplo de simulação de venda
            self.registrar_venda(produto_id, data_hoje, 50.0)

            return True
        except Exception as e:
            logging.error(f"Erro no fluxo diário: {str(e)}")
            return False

    def fechar(self):
        self.conn.close()

    def realizar_previsao(self):
        previsao.importar_vendas_csv(self.conn, Path("src/data/dados_zenith.csv"))
        previsao.prever(self.conn)


if __name__ == "__main__":
    sistema = ManagerSystem()

    try:
        produto_id = "237478"
        sucesso = sistema.executar_fluxo_diario(produto_id)

        if sucesso:
            with sistema.conn.cursor() as cursor:
                cursor.execute("SELECT * FROM lote WHERE produto_id = %s", (produto_id,))
                lotes = cursor.fetchall()

                print("\nLotes atuais:")
                for lote in lotes:
                    print(
                        f"ID: {lote['id']}, Status: {lote['status']}, Quantidade: {lote['quantidade_atual']}kg"
                    )
    finally:
        sistema.fechar()
