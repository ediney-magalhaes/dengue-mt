"""
Avaliação Rolling Window — LightGBM v5
Simula uso operacional real — retreino a cada janela
Referência: Chen & Moraga 2025 (BMC Public Health) —
moving window strategy para dengue no Brasil
"""
import pandas as pd
import numpy as np
import lightgbm as lgb
import pickle
from pathlib import Path
from sklearn.metrics import r2_score, mean_absolute_error

GOLD_PATH  = Path('data/gold/dataset_features_v5_latest.parquet')
MODEL_DIR  = Path('models')

DROP_COLS = [
    'municipio_nome', 'data_se', 'dbt_updated_at',
    'casos_estimados', 'incidencia_100k', 'semana_epidemiologica'
]
TARGET = 'casos_confirmados'

MUNICIPIOS = {
    5103403: 'cuiaba',
    5108402: 'varzea_grande'
}

# Parâmetros do Rolling Window
JANELA_TREINO = 156  # 3 anos de treino
HORIZONTE     = 13    # previsão 1 TRI à frente
PASSO         = 13    # avança 1 trimestre por vez

# Parâmetros LightGBM otimizados (da sessão anterior)
PARAMS = {
    'objective':         'regression',
    'metric':            'mae',
    'n_estimators':      200,
    'learning_rate':     0.05,
    'num_leaves':        31,
    'min_child_samples': 20,
    'subsample':         0.8,
    'colsample_bytree':  0.8,
    'random_state':      42,
    'verbose':           -1
}


def carregar_dados(municipio_id):
    df = pd.read_parquet(GOLD_PATH)
    df = df[df['municipio_id'] == municipio_id].copy()
    df = df.sort_values('data_se').reset_index(drop=True)
    X  = df.drop(columns=DROP_COLS + [TARGET, 'municipio_id'], errors='ignore')
    y  = df[TARGET]
    datas = df['data_se']
    return X, y, datas


def avaliar_rolling(X, y, datas, municipio_nome, horizonte=13, passo=13):
    n = len(X)
    r2_scores  = []
    mae_scores = []
    resultados = []

    for inicio in range(JANELA_TREINO, n - horizonte + 1, passo):
        train_start = max(0, inicio - JANELA_TREINO)
        X_train = X.iloc[train_start:inicio]
        y_train = y.iloc[train_start:inicio]
        X_test  = X.iloc[inicio:inicio + horizonte]
        y_test  = y.iloc[inicio:inicio + horizonte]

        y_train_log = np.log1p(y_train)
        modelo = lgb.LGBMRegressor(**PARAMS)
        modelo.fit(X_train, y_train_log)

        y_pred = np.expm1(np.clip(modelo.predict(X_test), 0, None))
        r2_scores.append(r2_score(y_test, y_pred))
        mae_scores.append(mean_absolute_error(y_test, y_pred))

    return np.mean(r2_scores), np.mean(mae_scores), pd.DataFrame()


if __name__ == '__main__':
    print('=== Avaliação Rolling Window — Múltiplos Horizontes ===\n')

    horizontes = [2, 4, 8, 13]

    for municipio_id, municipio_nome in MUNICIPIOS.items():
        print(f'\n{"="*60}')
        print(f'Município: {municipio_nome.upper()} ({municipio_id})')
        print(f'{"="*60}')

        X, y, datas = carregar_dados(municipio_id)

        print(f'\n{"Horizonte":>12} {"R² médio":>10} {"MAE médio":>10}')
        print('-' * 35)

        for h in horizontes:
            r2, mae, _ = avaliar_rolling(X, y, datas, municipio_nome,
                                         horizonte=h, passo=h)
            print(f'{h:>8} SE   {r2:>10.3f} {mae:>10.1f}')