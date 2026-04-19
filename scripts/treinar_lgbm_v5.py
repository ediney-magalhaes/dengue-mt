"""
Treinamento LightGBM v5 — Gold v5
TimeSeriesSplit 5 folds | 54 features | 2018→2025
"""
import pandas as pd
import numpy as np
import lightgbm as lgb
import pickle
from pathlib import Path
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import r2_score, mean_absolute_error

GOLD_PATH  = Path('data/gold/dataset_features_v5_latest.parquet')
MODEL_DIR  = Path('models')
MODEL_DIR.mkdir(exist_ok=True)

# Colunas que não entram no modelo
DROP_COLS = [
    'municipio_nome', 'data_se', 'dbt_updated_at',
    'casos_estimados', 'incidencia_100k',
    'semana_epidemiologica'
]

TARGET = 'casos_confirmados'

def carregar_dados():
    df = pd.read_parquet(GOLD_PATH)
    df = df.sort_values(['municipio_id', 'data_se']).reset_index(drop=True)
    print(f'Gold v5: {df.shape[0]} registros × {df.shape[1]} features')
    print(f'Período: {df["data_se"].min()} → {df["data_se"].max()}')
    return df

def preparar_features(df):
    X = df.drop(columns=DROP_COLS + [TARGET], errors='ignore')
    y = df[TARGET]
    print(f'Features: {X.shape[1]} | Target: {TARGET}')
    print(f'Features usadas: {X.columns.tolist()}')
    return X, y

def treinar_com_tscv(X, y, n_splits=5):
    tscv = TimeSeriesSplit(n_splits=n_splits)
    
    params = {
        'objective':        'regression',
        'metric':           'mae',
        'n_estimators':     500,
        'learning_rate':    0.05,
        'num_leaves':       31,
        'min_child_samples': 20,
        'subsample':        0.8,
        'colsample_bytree': 0.8,
        'random_state':     42,
        'verbose':          -1
    }

    r2_scores  = []
    mae_scores = []

    print(f'\n=== TimeSeriesSplit {n_splits} folds ===')
    for fold, (train_idx, test_idx) in enumerate(tscv.split(X), 1):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        modelo = lgb.LGBMRegressor(**params)
        modelo.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            callbacks=[lgb.early_stopping(50, verbose=False),
                      lgb.log_evaluation(period=-1)]
        )

        y_pred = modelo.predict(X_test)
        y_pred = np.clip(y_pred, 0, None)

        r2  = r2_score(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)
        r2_scores.append(r2)
        mae_scores.append(mae)

        print(f'Fold {fold}: R²={r2:.3f} | MAE={mae:.1f} | '
              f'train={len(train_idx)} | test={len(test_idx)}')

    print(f'\nMédia: R²={np.mean(r2_scores):.3f} ± {np.std(r2_scores):.3f} | '
          f'MAE={np.mean(mae_scores):.1f} ± {np.std(mae_scores):.1f}')

    return np.mean(r2_scores), np.mean(mae_scores)

def treinar_final(X, y):
    """Treina modelo final com todos os dados."""
    params = {
        'objective':        'regression',
        'metric':           'mae',
        'n_estimators':     500,
        'learning_rate':    0.05,
        'num_leaves':       31,
        'min_child_samples': 20,
        'subsample':        0.8,
        'colsample_bytree': 0.8,
        'random_state':     42,
        'verbose':          -1
    }

    modelo = lgb.LGBMRegressor(**params)
    modelo.fit(X, y)
    return modelo

def importancia_features(modelo, X):
    """Exibe top 20 features por importância."""
    imp = pd.DataFrame({
        'feature':    X.columns,
        'importance': modelo.feature_importances_
    }).sort_values('importance', ascending=False)

    print('\n=== Top 20 Features ===')
    print(imp.head(20).to_string(index=False))
    return imp

if __name__ == '__main__':
    print('=== Treinamento LightGBM v5 ===\n')

    # Carrega e prepara dados
    df = carregar_dados()
    X, y = preparar_features(df)

    # Avaliação com TimeSeriesSplit
    r2_medio, mae_medio = treinar_com_tscv(X, y, n_splits=5)

    # Treino final com todos os dados
    print('\n=== Treinando modelo final ===')
    modelo_final = treinar_final(X, y)

    # Importância de features
    imp = importancia_features(modelo_final, X)

    # Salva modelo
    path_modelo = MODEL_DIR / 'lgbm_v5_producao.pkl'
    with open(path_modelo, 'wb') as f:
        pickle.dump(modelo_final, f)

    # Salva importância de features
    imp.to_csv(MODEL_DIR / 'lgbm_v5_feature_importance.csv', index=False)

    print(f'\n✅ Modelo salvo: {path_modelo}')
    print(f'R² médio (TimeSeriesSplit): {r2_medio:.3f}')
    print(f'MAE médio (TimeSeriesSplit): {mae_medio:.1f} casos/semana')