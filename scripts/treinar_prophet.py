"""
Treinamento Prophet — comparação com LightGBM v5
Modelo baseline com sazonalidade para dengue MT
Referência: Taylor & Letham 2018 — Forecasting at Scale

Estratégia:
  - Modelos separados por município
  - Regressores externos (clima, ENSO, Trends)
  - Validação temporal equivalente ao TimeSeriesSplit
  - Comparação direta com LightGBM v5
"""
import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from prophet import Prophet
from sklearn.metrics import r2_score, mean_absolute_error
import warnings
warnings.filterwarnings('ignore')

GOLD_PATH = Path('data/gold/dataset_features_v5_latest.parquet')
MODEL_DIR  = Path('models')
MODEL_DIR.mkdir(exist_ok=True)

MUNICIPIOS = {
    5103403: 'cuiaba',
    5108402: 'varzea_grande'
}

# Regressores externos — features mais importantes do SHAP
REGRESSORES = [
    'casos_lag1', 'casos_lag2', 'casos_lag3', 'casos_mm4',
    'rt_index_lag1', 'prob_rt_maior_1_lag1',
    'trends_lag1', 'trends_lag2',
    'temp_media_lag2', 'temp_media_lag3',
    'precip_lag2', 'precip_lag3',
    'oni_lag4', 'oni_lag6',
]

N_SPLITS = 5


def carregar_dados(municipio_id):
    df = pd.read_parquet(GOLD_PATH)
    df = df[df['municipio_id'] == municipio_id].copy()
    df = df.sort_values('data_se').reset_index(drop=True)
    return df


def preparar_prophet(df):
    """Prophet requer colunas ds (data) e y (target)."""
    df_p = df[['data_se', 'casos_confirmados'] + REGRESSORES].copy()
    df_p = df_p.rename(columns={
        'data_se':           'ds',
        'casos_confirmados': 'y'
    })
    # Transformação log — mesma do LightGBM para comparação justa
    df_p['y'] = np.log1p(df_p['y'])

    # Prophet não aceita NaN nos regressores — preenche com forward fill + mediana
    for col in REGRESSORES:
        if col in df_p.columns:
            df_p[col] = df_p[col].ffill().bfill()
            # Se ainda houver NaN (coluna toda nula), preenche com 0
            df_p[col] = df_p[col].fillna(0)

    return df_p


def treinar_avaliar_tscv(df_p, municipio_nome):
    """Avaliação via TimeSeriesSplit equivalente ao LightGBM."""
    n = len(df_p)
    fold_size = n // (N_SPLITS + 1)

    r2_scores  = []
    mae_scores = []

    print(f'\n  TimeSeriesSplit {N_SPLITS} folds:')

    for fold in range(N_SPLITS):
        train_end  = fold_size * (fold + 1)
        test_start = train_end
        test_end   = min(test_start + fold_size, n)

        train = df_p.iloc[:train_end].copy()
        test  = df_p.iloc[test_start:test_end].copy()

        if len(train) < 50 or len(test) < 10:
            continue

        # Treina Prophet
        modelo = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            seasonality_mode='multiplicative',
            changepoint_prior_scale=0.05,
            seasonality_prior_scale=10,
        )

        # Adiciona regressores disponíveis
        regs_disponiveis = [
            r for r in REGRESSORES
            if r in train.columns and train[r].notna().sum() > 10
        ]
        for reg in regs_disponiveis:
            modelo.add_regressor(reg)

        modelo.fit(train[['ds', 'y'] + regs_disponiveis])

        # Previsão
        futuro = test[['ds'] + regs_disponiveis].copy()
        previsao = modelo.predict(futuro)

        # Reverte log
        y_pred = np.expm1(np.clip(previsao['yhat'].values, 0, None))
        y_true = np.expm1(test['y'].values)

        r2  = r2_score(y_true, y_pred)
        mae = mean_absolute_error(y_true, y_pred)
        r2_scores.append(r2)
        mae_scores.append(mae)

        print(f'  Fold {fold+1}: R²={r2:.3f} | MAE={mae:.1f} | '
              f'train={len(train)} | test={len(test)}')

    r2_medio  = np.mean(r2_scores)
    mae_medio = np.mean(mae_scores)

    print(f'  Média: R²={r2_medio:.3f} ± {np.std(r2_scores):.3f} | '
          f'MAE={mae_medio:.1f} ± {np.std(mae_scores):.1f}')

    return r2_medio, mae_medio


def treinar_final(df_p):
    """Treina Prophet com todos os dados."""
    regs_disponiveis = [
        r for r in REGRESSORES
        if r in df_p.columns and df_p[r].notna().sum() > 10
    ]

    modelo = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        seasonality_mode='multiplicative',
        changepoint_prior_scale=0.05,
        seasonality_prior_scale=10,
    )

    for reg in regs_disponiveis:
        modelo.add_regressor(reg)

    modelo.fit(df_p[['ds', 'y'] + regs_disponiveis])
    return modelo, regs_disponiveis


if __name__ == '__main__':
    print('=== Treinamento Prophet — Comparação com LightGBM v5 ===\n')

    resultados = {}

    for municipio_id, municipio_nome in MUNICIPIOS.items():
        print(f'\n{"="*50}')
        print(f'Município: {municipio_nome.upper()} ({municipio_id})')
        print(f'{"="*50}')

        df      = carregar_dados(municipio_id)
        df_p    = preparar_prophet(df)

        print(f'Registros: {len(df_p)} | '
              f'Regressores: {len(REGRESSORES)}')

        # Avaliação TimeSeriesSplit
        r2_medio, mae_medio = treinar_avaliar_tscv(df_p, municipio_nome)

        # Modelo final
        modelo_final, regs = treinar_final(df_p)

        # Salva modelo
        path = MODEL_DIR / f'prophet_{municipio_nome}.pkl'
        with open(path, 'wb') as f:
            pickle.dump({
                'modelo':      modelo_final,
                'regressores': regs,
                'municipio':   municipio_id
            }, f)

        resultados[municipio_nome] = {
            'r2':  r2_medio,
            'mae': mae_medio
        }

        print(f'\n  ✅ Modelo salvo: {path}')

    # Comparação final
    print(f'\n{"="*50}')
    print('COMPARAÇÃO PROPHET vs LIGHTGBM v5')
    print(f'{"="*50}')
    print(f'\n{"Município":<20} {"Prophet R²":>12} {"LightGBM R²":>12}')
    print('-' * 46)

    lgbm_r2 = {'cuiaba': 0.726, 'varzea_grande': 0.554}
    for municipio, res in resultados.items():
        lgbm = lgbm_r2.get(municipio, 0)
        vencedor = 'LightGBM ✅' if lgbm > res['r2'] else 'Prophet ✅'
        print(f'{municipio:<20} {res["r2"]:>12.3f} {lgbm:>12.3f}  ← {vencedor}')