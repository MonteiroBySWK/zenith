import pymysql
import logging
from pathlib import Path

# --- Configuração de Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Dados de conexão (ajuste conforme necessário)
MYSQL_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'estoque',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def criar_banco_e_tabelas():
    """
    Cria o banco de dados MySQL e inicializa todas as tabelas necessárias.
    """

    logging.info("Conectando ao banco MySQL...")

    conn = pymysql.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    logging.info("Criando tabelas no banco MySQL...")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produto (
            id INT AUTO_INCREMENT PRIMARY KEY,
            sku VARCHAR(100) NOT NULL UNIQUE,
            nome VARCHAR(255) NOT NULL,
            categoria VARCHAR(100) NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lote (
            id INT AUTO_INCREMENT PRIMARY KEY,
            quantidade_retirada FLOAT NOT NULL,
            quantidade_atual FLOAT NOT NULL,
            idade INT NOT NULL,
            status VARCHAR(50) NOT NULL,
            data_retirado DATE NOT NULL,
            data_venda DATE NOT NULL,
            data_expiracao DATE NOT NULL,
            produto_id INT NOT NULL,
            FOREIGN KEY (produto_id) REFERENCES produto(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS venda (
            id INT AUTO_INCREMENT PRIMARY KEY,
            data DATE NOT NULL,
            quantidade FLOAT NOT NULL,
            produto_id INT NOT NULL,
            FOREIGN KEY (produto_id) REFERENCES produto(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS previsao (
            id INT AUTO_INCREMENT PRIMARY KEY,
            data DATE NOT NULL,
            quantidade_prevista FLOAT NOT NULL,
            produto_id INT NOT NULL,
            UNIQUE (produto_id, data),
            FOREIGN KEY (produto_id) REFERENCES produto(id)
        )
    """)

    conn.commit()
    conn.close()
    logging.info("Banco e tabelas criados com sucesso no MySQL.")

if __name__ == "__main__":
    criar_banco_e_tabelas()
