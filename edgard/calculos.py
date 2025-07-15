import pandas as pd
from sklearn.metrics import mean_squared_error, mean_absolute_percentage_error
from sklearn.linear_model import LinearRegression
import numpy as np

# Carregar os dados
df = pd.read_csv('zenith.csv')

# Renomear colunas para manter a consistência com o script original
df = df.rename(columns={'data_dia': 'data', 'total_venda_dia_kg': 'venda_kg'})

# Converter a coluna de data para o formato datetime
df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y')

# Funções do script main.py adaptadas para o nosso caso
def criar_features(df, config):
    """Cria features de data e lags para o modelo."""
    df['dia_semana'] = df['data'].dt.dayofweek
    df['semana_ano'] = df['data'].dt.isocalendar().week.astype(int)
    
    feats = []
    for lag in config['lags']:
        feat = f"lag_{lag}"
        df[feat] = df['venda_kg'].shift(lag)
        feats.append(feat)
        
    for lag in config['rolling_features']:
        feat = f"rolling_mean_{lag}"
        df[feat] = df['venda_kg'].shift(1).rolling(lag).mean()
        feats.append(feat)

    df = df.dropna()
    return df, feats

def treinar_modelo(df_feat, feats, config):
    """Treina um modelo de regressão linear."""
    X = df_feat[feats]
    y = df_feat[config['target']]
    model = LinearRegression()
    model.fit(X, y)
    return model

# Configuração para criação de features e treinamento
CONFIG = {
    'lags': [1, 2, 3, 7],
    'rolling_features': [7, 14],
    'target': 'venda_kg'
}

# Criar features no dataset completo antes de separar
df_completo_feat, feats = criar_features(df.copy(), CONFIG)

# Dividir os dados em treino (março e abril) e teste (maio)
train_feat_df = df_completo_feat[df_completo_feat['data'].dt.month.isin([3, 4])]
test_feat_df = df_completo_feat[df_completo_feat['data'].dt.month == 5]


# Treinar o modelo com os dados de treino
model = treinar_modelo(train_feat_df, feats, CONFIG)

# Fazer previsões nos dados de teste
X_test = test_feat_df[feats]
y_test = test_feat_df[CONFIG['target']]
predictions = model.predict(X_test)

# Calcular RMSE e MAPE
rmse = np.sqrt(mean_squared_error(y_test, predictions))
mape = mean_absolute_percentage_error(y_test, predictions)

print(f"RMSE: {round(rmse, 2)}Kg")
print(f"MAPE: {round(mape, 2)*100}%")