# ============================================================
# Dengue MT — Task: Retreino do Modelo
# ============================================================

from prefect import task, get_run_logger
from datetime import datetime
from src.config import (
    DATA_DIR, MODELS_DIR, PIPELINE_VERSION,
    DATASET_VERSION, COMMIT_SHA
)
import pandas as pd
import numpy as np
import joblib
import json
import os


@task(name="retreinar_modelo")
def retreinar_modelo():
    """Retreina LightGBM v4 com dados mais recentes."""
    logger = get_run_logger()
    logger.info("Iniciando retreino do modelo...")

    try:
        import lightgbm as lgb
        from sklearn.metrics import mean_absolute_error, r2_score

        # Carregar gold dataset
        gold_path = DATA_DIR / 'gold' / 'dataset_features_v4.parquet'
        if not gold_path.exists():
            logger.error("dataset_features_v4 não encontrado")
            return {'status': 'erro', 'motivo': 'dataset não encontrado'}

        df = pd.read_parquet(gold_path)
        df['data'] = pd.to_datetime(df['data'])
        df = df.sort_values('data').dropna().reset_index(drop=True)

        # Features — remover leakage
        drop_cols = ['data', 'casos', 'casos_nowcast', 'municipio_id']
        drop_cols = [c for c in drop_cols if c in df.columns]
        X = df.drop(columns=drop_cols)
        y = df['casos']

        # Carregar modelo atual
        modelo_path = MODELS_DIR / 'lgbm_v4_producao.pkl'
        modelo_atual = joblib.load(modelo_path) if modelo_path.exists() else None

        # Carregar schema de features
        schema_path = MODELS_DIR / 'lgbm_v4_feature_schema.json'
        if schema_path.exists():
            with open(schema_path) as f:
                schema_salvo = json.load(f)
            feature_cols_esperadas = schema_salvo['feature_names']
            logger.info(f"Schema carregado: {len(feature_cols_esperadas)} features")
        else:
            feature_cols_esperadas = modelo_atual.feature_name_ if modelo_atual else None
            logger.warning("Schema não encontrado — usando features do modelo atual")

        # Verificar compatibilidade
        if feature_cols_esperadas:
            features_faltando = [f for f in feature_cols_esperadas if f not in X.columns]
            features_extras   = [f for f in X.columns if f not in feature_cols_esperadas]

            if features_faltando:
                logger.error(f"Features faltando: {features_faltando}")
                return {'status': 'erro', 'motivo': f'Features faltando: {features_faltando}'}

            if features_extras:
                logger.warning(f"Features extras ignoradas: {features_extras}")

            X = X[feature_cols_esperadas]
            logger.info(f"Dataset alinhado: {X.shape[1]} features")

        # Avaliar modelo atual nas últimas 90 observações
        r2_atual = None
        if modelo_atual:
            feature_cols = [c for c in modelo_atual.feature_name_ if c in df.columns]
            df_test  = df.tail(90)
            X_test   = df_test[feature_cols]
            y_test   = df_test['casos']
            preds_atual = np.maximum(modelo_atual.predict(X_test), 0)
            r2_atual = r2_score(y_test, preds_atual)
            logger.info(f"R² modelo atual (90d): {r2_atual:.3f}")

        # Retreinar com Rolling Window (últimos 365 dias)
        corte    = df['data'].max() - pd.Timedelta(days=365)
        df_train = df[df['data'] >= corte]
        X_train  = df_train.drop(columns=drop_cols)
        y_train  = df_train['casos']

        params = {
            'objective':          'regression',
            'metric':             'mae',
            'verbosity':          -1,
            'n_estimators':       500,
            'learning_rate':      0.05,
            'num_leaves':         31,
            'random_state':       42
        }

        novo_modelo = lgb.LGBMRegressor(**params)
        novo_modelo.fit(X_train, y_train)

        # Avaliar novo modelo
        preds_novo = np.maximum(
            novo_modelo.predict(X_test if modelo_atual else X.tail(90)), 0
        )
        y_eval  = y_test if modelo_atual else y.tail(90)
        r2_novo = r2_score(y_eval, preds_novo)
        mae_novo = mean_absolute_error(y_eval, preds_novo)

        logger.info(f"R² novo modelo: {r2_novo:.3f} | MAE: {mae_novo:.1f}")

        # Decisão: promover ou manter
        promover = r2_novo >= (r2_atual - 0.05) if r2_atual else True

        if promover:
            joblib.dump(novo_modelo, modelo_path)

            schema = {
                'feature_names':      novo_modelo.feature_name_,
                'n_features':         len(novo_modelo.feature_name_),
                'pipeline_version':   PIPELINE_VERSION,
                'commit_sha':         os.environ.get('GITHUB_SHA', 'local')[:8],
                'dataset_version':    DATASET_VERSION,
                'drop_cols':          drop_cols,
                'data_treino':        str(df_train['data'].max().date()),
                'n_registros_treino': len(df_train),
                'timestamp':          datetime.now().isoformat(),
                'r2':                 round(r2_novo, 3),
                'mae':                round(mae_novo, 1)
            }
            with open(schema_path, 'w', encoding='utf-8') as f:
                json.dump(schema, f, ensure_ascii=False, indent=2)

            logger.info(f"Modelo promovido — R²={r2_novo:.3f}")
            return {
                'status':       'promovido',
                'r2_novo':      round(r2_novo, 3),
                'r2_anterior':  round(r2_atual, 3) if r2_atual else None,
                'mae':          round(mae_novo, 1)
            }
        else:
            logger.warning(
                f"Modelo mantido — R²={r2_novo:.3f} < {r2_atual:.3f} - 0.05"
            )
            return {
                'status':      'mantido',
                'r2_novo':     round(r2_novo, 3),
                'r2_anterior': round(r2_atual, 3),
                'motivo':      'queda de performance acima do limiar'
            }

    except Exception as e:
        logger.error(f"Erro no retreino: {e}")
        return {'status': 'erro', 'motivo': str(e)}