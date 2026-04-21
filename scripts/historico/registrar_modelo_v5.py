"""
Registra modelo LightGBM v5 formalmente
- Schema JSON com features, métricas e metadados
- MLflow tracking
- Publicação no HF Hub
"""
import json
import pickle
import hashlib
import pandas as pd
import numpy as np
import lightgbm as lgb
from datetime import datetime
from pathlib import Path

GOLD_PATH  = Path('data/gold/dataset_features_v5_latest.parquet')
MODEL_DIR  = Path('models')
SCHEMA_PATH = MODEL_DIR / 'lgbm_v5_feature_schema.json'

DROP_COLS = [
    'municipio_nome', 'data_se', 'dbt_updated_at',
    'casos_estimados', 'incidencia_100k', 'semana_epidemiologica'
]
TARGET = 'casos_confirmados'

# Métricas validadas nesta sessão
METRICAS = {
    'r2_tscv_medio':    0.741,
    'mae_tscv_medio':   9.7,
    'r2_tscv_std':      0.081,
    'mae_tscv_std':     6.2,
    'n_folds':          5,
    'validacao':        'TimeSeriesSplit',
    'transformacao':    'log1p(y)',
    'shap_top1':        'casos_mm4',
    'shap_top1_pct':    46.5,
    'shap_top5_pct':    70.6,
    'nota': (
        'R²=0.741 com dados 2018-2025 incluindo surto histórico 2024/2025. '
        'Competitivo com literatura — IMDC24 (PNAS 2026) reporta que nenhum '
        'modelo excelu no surto de 2024.'
    )
}


def treinar_modelo_final(X, y):
    params = {
        'objective': 'regression', 'metric': 'mae',
        'n_estimators': 500, 'learning_rate': 0.05,
        'num_leaves': 31, 'min_child_samples': 20,
        'subsample': 0.8, 'colsample_bytree': 0.8,
        'random_state': 42, 'verbose': -1
    }
    modelo = lgb.LGBMRegressor(**params)
    modelo.fit(X, np.log1p(y))
    return modelo, params


def calcular_hash(path):
    with open(path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


if __name__ == '__main__':
    print('=== Registrando LightGBM v5 ===\n')

    # Carrega Gold
    df = pd.read_parquet(GOLD_PATH)
    df = df.sort_values(['municipio_id', 'data_se']).reset_index(drop=True)
    X  = df.drop(columns=DROP_COLS + [TARGET, 'municipio_id'], errors='ignore')
    y  = df[TARGET]

    print(f'Dataset: {len(df)} registros × {len(X.columns)} features')

    # Treina modelo final
    print('Treinando modelo final...')
    modelo, params = treinar_modelo_final(X, y)

    # Salva modelo
    path_modelo = MODEL_DIR / 'lgbm_v5_producao.pkl'
    with open(path_modelo, 'wb') as f:
        pickle.dump(modelo, f)

    # Hash do modelo
    hash_modelo = calcular_hash(path_modelo)
    hash_gold   = calcular_hash(GOLD_PATH)

    # Schema formal
    schema = {
        'modelo_versao':    'v5',
        'algoritmo':        'LightGBM',
        'dataset_versao':   'v5',
        'data_treino':      datetime.now().strftime('%Y-%m-%d'),
        'periodo_treino':   '2018-02-04 → 2025-12-28',
        'n_registros':      len(df),
        'municipios':       [5103403, 5108402],
        'feature_names':    X.columns.tolist(),
        'n_features':       len(X.columns),
        'target':           TARGET,
        'transformacao_target': 'log1p',
        'params':           params,
        'metricas':         METRICAS,
        'drop_cols':        DROP_COLS + ['municipio_id'],
        'hash_modelo_md5':  hash_modelo,
        'hash_gold_md5':    hash_gold,
        'arquivo_modelo':   str(path_modelo),
        'arquivo_gold':     str(GOLD_PATH),
        'hf_hub_dataset':   'edyestatistica/dengue-mt-medallion',
        'referencias': [
            'Hii et al. 2012 — lags climáticos dengue',
            'Codeco et al. 2018 — InfoDengue nowcasting',
            'Sebastianelli et al. 2024 — MODIS dengue Brasil',
            'Scientific Data Nature 2026 — Trends overlapping windows',
            'IMDC24 PNAS 2026 — benchmark dengue Brasil'
        ]
    }

    with open(SCHEMA_PATH, 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    print(f'✅ Modelo salvo: {path_modelo}')
    print(f'✅ Schema salvo: {SCHEMA_PATH}')
    print(f'\nMétricas registradas:')
    print(f'  R²  (TSCV): {METRICAS["r2_tscv_medio"]:.3f} '
          f'± {METRICAS["r2_tscv_std"]:.3f}')
    print(f'  MAE (TSCV): {METRICAS["mae_tscv_medio"]:.1f} '
          f'± {METRICAS["mae_tscv_std"]:.1f} casos/semana')
    print(f'  Top feature: {METRICAS["shap_top1"]} '
          f'({METRICAS["shap_top1_pct"]}%)')

    # Publica no HF Hub
    resposta = input('\nPublicar modelo e schema no HF Hub? (s/n): ')
    if resposta.lower() == 's':
        from huggingface_hub import HfApi
        api = HfApi()
        hoje = datetime.now().strftime('%Y-%m-%d')

        for arquivo, nome_repo in [
            (path_modelo, f'models/lgbm_v5_producao_{hoje}.pkl'),
            (path_modelo, 'models/lgbm_v5_producao_latest.pkl'),
            (SCHEMA_PATH, f'models/lgbm_v5_feature_schema_{hoje}.json'),
            (SCHEMA_PATH, 'models/lgbm_v5_feature_schema_latest.json'),
        ]:
            api.upload_file(
                path_or_fileobj=str(arquivo),
                path_in_repo=nome_repo,
                repo_id='edyestatistica/dengue-mt-medallion',
                repo_type='dataset'
            )
            print(f'  ✅ {nome_repo}')

        print('\n✅ Modelo publicado no HF Hub!')