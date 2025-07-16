#!/usr/bin/env python3
"""
Script para comparar previsões do Prophet com dados reais do CSV
e calcular métricas MAPE e RMSE
"""
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.metrics import mean_squared_error, mean_absolute_percentage_error

def carregar_dados_reais(csv_path):
    """Carrega dados reais do CSV"""
    df = pd.read_csv(csv_path)
    df['data_dia'] = pd.to_datetime(df['data_dia'], format='%d/%m/%Y')
    df = df.rename(columns={'data_dia': 'data', 'total_venda_dia_kg': 'real'})
    return df[['data', 'real']].sort_values('data')

def carregar_previsoes_banco(db_path):
    """Carrega previsões do banco de dados"""
    conn = sqlite3.connect(db_path)
    query = """
        SELECT data, quantidade_prevista as previsto
        FROM previsao 
        ORDER BY data
    """
    df = pd.read_sql_query(query, conn)
    df['data'] = pd.to_datetime(df['data'])
    conn.close()
    return df

def comparar_previsoes(dados_reais, previsoes, dias_comparacao=7):
    """Compara previsões com dados reais"""
    
    print("📊 COMPARAÇÃO: PREVISÕES vs DADOS REAIS")
    print("=" * 50)
    
    # Combinar dados reais e previsões
    df_merged = pd.merge(dados_reais, previsoes, on='data', how='inner')
    
    if df_merged.empty:
        print("❌ Erro: Nenhuma data coincidente entre previsões e dados reais")
        return None
    
    # Pegar os últimos N dias que têm tanto dados reais quanto previsões
    df_comparison = df_merged.tail(dias_comparacao)
    
    if len(df_comparison) == 0:
        print("❌ Erro: Não há dados suficientes para comparação")
        return None
    
    print(f"📅 Comparando os últimos {len(df_comparison)} dias:")
    print()
    
    # Mostrar comparação dia a dia
    print("Data       | Real (kg) | Previsto (kg) | Erro Abs. | Erro %")
    print("-" * 60)
    
    for _, row in df_comparison.iterrows():
        erro_abs = abs(row['real'] - row['previsto'])
        erro_perc = (erro_abs / row['real']) * 100 if row['real'] != 0 else 0
        
        print(f"{row['data'].strftime('%d/%m/%Y')} | {row['real']:8.2f} | {row['previsto']:11.2f} | {erro_abs:8.2f} | {erro_perc:6.1f}%")
    
    # Calcular métricas
    reais = df_comparison['real'].values
    previstos = df_comparison['previsto'].values
    
    # RMSE
    rmse = np.sqrt(mean_squared_error(reais, previstos))
    
    # MAPE
    mape = mean_absolute_percentage_error(reais, previstos) * 100
    
    print()
    print("📈 MÉTRICAS DE PERFORMANCE:")
    print("-" * 30)
    print(f"RMSE (Root Mean Square Error): {rmse:.2f} kg")
    print(f"MAPE (Mean Absolute Percentage Error): {mape:.2f}%")
    
    # Interpretação dos resultados
    print()
    print("🎯 INTERPRETAÇÃO:")
    print("-" * 20)
    if mape < 10:
        print("✅ Excelente precisão (MAPE < 10%)")
    elif mape < 20:
        print("✅ Boa precisão (MAPE < 20%)")
    elif mape < 30:
        print("⚠️  Precisão moderada (MAPE < 30%)")
    else:
        print("❌ Precisão baixa (MAPE > 30%)")
    
    return {
        'rmse': rmse,
        'mape': mape,
        'dados_comparison': df_comparison
    }

def main():
    # Caminhos dos arquivos
    csv_path = "zenith.csv"
    db_path = "src/data/data.db"
    
    print("🚀 INICIANDO COMPARAÇÃO DE PREVISÕES")
    print("=" * 40)
    
    # Verificar se arquivos existem
    if not Path(csv_path).exists():
        print(f"❌ Erro: Arquivo CSV não encontrado: {csv_path}")
        return
    
    if not Path(db_path).exists():
        print(f"❌ Erro: Banco de dados não encontrado: {db_path}")
        return
    
    try:
        # Carregar dados
        print(f"📂 Carregando dados reais de: {csv_path}")
        dados_reais = carregar_dados_reais(csv_path)
        print(f"   → {len(dados_reais)} registros carregados")
        
        print(f"🗄️  Carregando previsões de: {db_path}")
        previsoes = carregar_previsoes_banco(db_path)
        print(f"   → {len(previsoes)} previsões carregadas")
        
        # Fazer comparação
        resultado = comparar_previsoes(dados_reais, previsoes, dias_comparacao=7)
        
        if resultado:
            print()
            print("✅ Comparação concluída com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro durante a execução: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
