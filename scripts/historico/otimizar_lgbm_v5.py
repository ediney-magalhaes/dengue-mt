"""
Otimização LightGBM v5 via Optuna
Estratégia:
  1. Modelos separados por município
  2. Optuna — otimização bayesiana de hiperparâmetros
  3. Feature selection via SHAP
"""
import pandas as pd
import numpy as np
import lightgbm as lgb
import optuna
import shap
import pickle
from pathlib import Path
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import r2_score, mean_absolute_error

optuna.logging.set_verbosity(optuna.logging.WARNING)

GOLD_PATH = Path('data/gold/dataset_features_v5_latest.parquet')
MODEL_DIR = Path('models')
MODEL_DIR.mkdir(exist_ok=True)

DROP_COLS = [
    'municipio_nome', 'data_se', 'dbt_updated_at',
    'casos_estimados', 'incidencia_100k', 'semana_epidemiologica'
]
TARGET = 'casos_confirmados'

MUNICIPIOS = {
    5103403: 'cuiaba',
    5108402: 'varzea_grande'
}

N_TRIALS  = 50
N_SPLITS  = 5


def carregar_dados():
    df = pd.read_parquet(GOLD_PATH)
    df = df.sort_values(['municipio_id', 'data_se']).reset_index(drop=True)
    return df


def preparar_features(df, municipio_id):
    df_mun = df[df['municipio_id'] == municipio_id].copy()
    X = df_mun.drop(columns=DROP_COLS + [TARGET, 'municipio_id'], errors='ignore')
    y = df_mun[TARGET]
    return X, y


def avaliar_params(params, X, y, n_splits=N_SPLITS):
    """Avalia um conjunto de parâmetros via TimeSeriesSplit."""
    # Transformação log do target
    y_log = np.log1p(y)
    tscv = TimeSeriesSplit(n_splits=n_splits)
    r2_scores = []

    for train_idx, test_idx in tscv.split(X):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        y_train_log = np.log1p(y_train)  # ← transforma treino

        modelo = lgb.LGBMRegressor(**params, verbose=-1, random_state=42)
        y_test_log = np.log1p(y_test)
        modelo.fit(
            X_train, y_train_log,
            eval_set=[(X_test, y_test_log)],
            callbacks=[lgb.early_stopping(50, verbose=False),
                      lgb.log_evaluation(period=-1)]
        )

        y_pred_log = np.clip(modelo.predict(X_test), 0, None)
        y_pred = np.expm1(y_pred_log)    # ← reverte para original
        r2_scores.append(r2_score(y_test, y_pred))  # ← compara na escala original

    return np.mean(r2_scores)


def otimizar(X, y, municipio_nome):
    """Otimização bayesiana via Optuna."""
    print(f'\n  Otimizando {municipio_nome} ({N_TRIALS} trials)...')

    def objective(trial):
        params = {
            'objective':         'regression',
            'metric':            'mae',
            'n_estimators':      trial.suggest_int('n_estimators', 200, 1000),
            'learning_rate':     trial.suggest_float('learning_rate', 0.01, 0.1, log=True),
            'num_leaves':        trial.suggest_int('num_leaves', 20, 100),
            'min_child_samples': trial.suggest_int('min_child_samples', 10, 50),
            'subsample':         trial.suggest_float('subsample', 0.6, 1.0),
            'colsample_bytree':  trial.suggest_float('colsample_bytree', 0.6, 1.0),
            'reg_alpha':         trial.suggest_float('reg_alpha', 1e-8, 1.0, log=True),
            'reg_lambda':        trial.suggest_float('reg_lambda', 1e-8, 1.0, log=True),
        }
        return avaliar_params(params, X, y)

    study = optuna.create_study(direction='maximize')
    study.optimize(objective, n_trials=N_TRIALS, show_progress_bar=True)

    print(f'  Melhor R²: {study.best_value:.3f}')
    print(f'  Melhores params: {study.best_params}')
    return study.best_params


def selecionar_features_shap(modelo, X, threshold=0.01):
    """Remove features com importância SHAP abaixo do threshold."""
    explainer  = shap.TreeExplainer(modelo)
    shap_vals  = explainer.shap_values(X)
    importancia = pd.DataFrame({
        'feature':    X.columns,
        'shap_mean':  np.abs(shap_vals).mean(axis=0)
    }).sort_values('shap_mean', ascending=False)

    # Normaliza para soma = 1
    importancia['shap_pct'] = importancia['shap_mean'] / importancia['shap_mean'].sum()

    features_selecionadas = importancia[
        importancia['shap_pct'] >= threshold
    ]['feature'].tolist()

    removidas = importancia[importancia['shap_pct'] < threshold]['feature'].tolist()

    print(f'  Features mantidas: {len(features_selecionadas)} | '
          f'Removidas: {len(removidas)}')
    if removidas:
        print(f'  Removidas: {removidas}')

    return features_selecionadas, importancia


def treinar_final(X, y, params):
    """Treina modelo final com todos os dados e melhores params."""
    # Transformação log do target
    y_log = np.log1p(y)
    modelo = lgb.LGBMRegressor(**params, verbose=-1, random_state=42)
    modelo.fit(X, y_log)             # ← treina com log
    return modelo


if __name__ == '__main__':
    print('=== Otimização LightGBM v5 por Município ===\n')

    df = carregar_dados()
    resultados = {}

    for municipio_id, municipio_nome in MUNICIPIOS.items():
        print(f'\n{"="*50}')
        print(f'Município: {municipio_nome.upper()} ({municipio_id})')
        print(f'{"="*50}')

        X, y = preparar_features(df, municipio_id)
        print(f'Registros: {len(X)} | Features: {X.shape[1]}')

        # Baseline com params padrão
        params_base = {
            'objective': 'regression', 'metric': 'mae',
            'n_estimators': 500, 'learning_rate': 0.05,
            'num_leaves': 31, 'min_child_samples': 20,
            'subsample': 0.8, 'colsample_bytree': 0.8
        }
        r2_base = avaliar_params(params_base, X, y)
        print(f'Baseline R²: {r2_base:.3f}')

        # Otimização Optuna
        melhores_params = otimizar(X, y, municipio_nome)
        melhores_params.update({
            'objective': 'regression',
            'metric':    'mae'
        })

        r2_otimizado = avaliar_params(melhores_params, X, y)
        print(f'Otimizado R²: {r2_otimizado:.3f} '
              f'(+{r2_otimizado - r2_base:.3f})')

        # Treina modelo com todos os dados para SHAP
        modelo_temp = treinar_final(X, y, melhores_params)

        # Feature selection via SHAP
        print('\n  Feature selection via SHAP:')
        features_sel, importancia = selecionar_features_shap(modelo_temp, X)

        # Re-treina com features selecionadas
        X_sel = X[features_sel]
        r2_final = avaliar_params(melhores_params, X_sel, y)
        print(f'  R² após feature selection: {r2_final:.3f}')

        # Modelo final
        modelo_final = treinar_final(X_sel, y, melhores_params)

        # Salva modelo
        path = MODEL_DIR / f'lgbm_v5_{municipio_nome}_otimizado.pkl'
        with open(path, 'wb') as f:
            pickle.dump({
                'modelo':    modelo_final,
                'features':  features_sel,
                'params':    melhores_params,
                'municipio': municipio_id
            }, f)

        # Salva importância SHAP
        importancia.to_csv(
            MODEL_DIR / f'shap_importance_{municipio_nome}.csv',
            index=False
        )

        resultados[municipio_nome] = {
            'r2_base':      r2_base,
            'r2_otimizado': r2_otimizado,
            'r2_final':     r2_final,
            'n_features':   len(features_sel),
            'path':         str(path)
        }

        print(f'\n  ✅ Modelo salvo: {path}')

    # Resumo final
    print(f'\n{"="*50}')
    print('RESUMO FINAL')
    print(f'{"="*50}')
    for municipio, res in resultados.items():
        print(f'\n{municipio.upper()}:')
        print(f'  Baseline:         R²={res["r2_base"]:.3f}')
        print(f'  Otimizado:        R²={res["r2_otimizado"]:.3f}')
        print(f'  + Feature sel:    R²={res["r2_final"]:.3f}')
        print(f'  Features finais:  {res["n_features"]}')