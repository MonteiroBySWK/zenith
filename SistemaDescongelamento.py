from datetime import datetime, timedelta
import sqlite3
import numpy as np
import logging
from pathlib import Path

import src.repositories.PrevisaoRepository as PrevisaoRepository
import src.repositories.VendaRepository as VendaRepository
import src.repositories.LoteRepository as LoteRepository

# Configuração de logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class SistemaDescongelamento:
    def __init__(self, db_path="src/data/data.db"):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.k = 1.65  # Fator de segurança para 95% de confiança
        self.alpha = 0.85  # Fator de retração (15% de perda)
        self.validade_dias = 2  # Validade após descongelamento

    # Rever isso aqui
    def calcular_desvio_padrao(self, produto_id, horizonte=2):
        """Calcula o desvio padrão dos erros de previsão"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT p.quantidade_prevista, v.quantidade
            FROM previsao p
            JOIN venda v ON p.produto_id = v.produto_id AND p.data = v.data
            WHERE p.produto_id = ? 
            ORDER BY p.data DESC
            LIMIT 30
        """,
            (produto_id,),
        )

        dados = cursor.fetchall()
        if not dados:
            return 0.0

        erros = [row["quantidade"] - row["quantidade_prevista"] for row in dados]
        return np.std(erros)

    def calcular_retirada(self, produto_id, data_hoje):
        """
        Calcula R(t) - quantidade a ser retirada hoje (kg brutos)

        :param produto_id: ID do produto (SKU)
        :param data_hoje: Data atual (dia t)
        :return: Quantidade em kg a ser retirada
        """
        # 1. Obter previsão para t+2
        data_venda = data_hoje + timedelta(days=2)

        Vp_t2 = PrevisaoRepository.obter_previsao(self.conn, produto_id, data_venda)

        if Vp_t2 is None:
            # Fallback para demanda média se não houver previsão
            Vp_t2 = VendaRepository.obter_demanda_media(self.conn, produto_id)
            logging.warning(
                f"Previsão não encontrada para produto {produto_id}. Usando demanda média: {Vp_t2}"
            )

        # 2. Calcular desvio padrão para t+2
        m_t2 = self.calcular_desvio_padrao(produto_id)  # MUDAR URGENTE

        # 3. Obter retirada do dia anterior (t-1)
        R_t1 = LoteRepository.obter_retirada_anterior(self.conn, produto_id, data_hoje)

        # 4. Aplicar fórmula principal
        R_t = (Vp_t2 + self.k * m_t2 - self.alpha * R_t1) / self.alpha

        # 5. Aplicar restrições
        demanda_media = VendaRepository.obter_demanda_media(self.conn, produto_id)
        R_max = (2 * demanda_media) / self.alpha

        R_t = max(0, R_t)  # Não pode ser negativo
        R_t = min(R_t, R_max)  # depois adicionar capacidade

        return R_t

    def registrar_venda(self, produto_id, data, quantidade):
        """Registra uma venda real e atualiza os lotes"""
        cursor = self.conn.cursor()
        data_str = data.strftime("%Y-%m-%d")

        # 1. Registrar a venda
        cursor.execute(
            """
            INSERT INTO venda (data, quantidade, produto_id)
            VALUES (?, ?, ?)
        """,
            (data_str, quantidade, produto_id),
        )

        # 2. Atualizar lotes (FIFO)
        cursor.execute(
            """
            SELECT id, quantidade_atual
            FROM lote
            WHERE produto_id = ? 
            AND status IN ('disponivel', 'sobra')
            AND data_venda <= ?
            ORDER BY data_retirado
        """,
            (produto_id, data_str),
        )

        lotes = cursor.fetchall()
        quantidade_restante = quantidade

        for lote in lotes:
            lote_id, qtd_lote = lote["id"], lote["quantidade_atual"]
            if quantidade_restante <= 0:
                break

            # Calcular quanto podemos consumir deste lote
            consumo = min(qtd_lote, quantidade_restante)
            nova_quantidade = qtd_lote - consumo
            quantidade_restante -= consumo

            # Atualizar a quantidade no lote
            cursor.execute(
                """
                UPDATE lote
                SET quantidade_atual = ?
                WHERE id = ?
            """,
                (nova_quantidade, lote_id),
            )

            # Se o lote zerou, marcamos como vendido
            if nova_quantidade <= 0:
                cursor.execute(
                    """
                    UPDATE lote
                    SET status = 'vendido'
                    WHERE id = ?
                """,
                    (lote_id,),
                )

        self.conn.commit()
        logging.info(f"Venda registrada: {quantidade}kg para produto {produto_id}")
        return quantidade_restante  # Retorna o que não foi atendido

    def executar_fluxo_diario(self, produto_id):
        """Executa todo o fluxo diário para um produto"""
        data_hoje = datetime.now().date()

        try:
            # 1. Atualizar status dos lotes
            LoteRepository.atualizar_status_lotes_diario(self.conn, data_hoje)

            # 2. Calcular retirada para hoje
            R_t = self.calcular_retirada(produto_id, data_hoje)
            logging.info(
                f"Produto {produto_id}: Quantidade a retirar hoje: {R_t:.2f}kg"
            )

            # 3. Criar novo lote com a retirada calculada
            LoteRepository.criar_lote(self.conn, produto_id, R_t, data_hoje)

            # 4. (Opcional) Simular vendas do dia
            # Em produção, isso seria feito no final do dia com dados reais
            self.registrar_venda(produto_id, data_hoje, 50.0)

            return True
        except Exception as e:
            logging.error(f"Erro no fluxo diário: {str(e)}")
            return False

    def fechar(self):
        self.conn.close()


# Exemplo de uso
if __name__ == "__main__":
    sistema = SistemaDescongelamento()

    

    try:
        # Supondo que temos um produto com ID 1
        produto_id = "237478"

        # Executar fluxo diário
        sucesso = sistema.executar_fluxo_diario(produto_id)

        if sucesso:
            # Obter relatório de lotes atualizados
            cursor = sistema.conn.cursor()
            cursor.execute("SELECT * FROM lote WHERE produto_id = ?", (produto_id,))
            lotes = cursor.fetchall()

            print("\nLotes atuais:")
            for lote in lotes:
                print(
                    f"ID: {lote['id']}, Status: {lote['status']}, Quantidade: {lote['quantidade_atual']}kg"
                )
    finally:
        sistema.fechar()
