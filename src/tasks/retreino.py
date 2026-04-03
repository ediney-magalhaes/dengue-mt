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
def retreinar_modelo(data_corte=None, params_retreino=None):
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

        # Aplicar corte temporal anti-leakage
        if data_corte:
            n_antes = len(df)
            df = df[df['data'] <= pd.Timestamp(data_corte)]
            n_depois = len(df)
            logger.info(f"Corte temporal aplicado: até {data_corte} — {n_antes} → {n_depois} registros")
        else:
            logger.warning("DATA_CORTE não definido — usando dataset completo (risco de leakage!)")

        # Features — módulo canônico (fonte única de verdade)
        from src.features.build_features import build_features, get_target, DROP_COLS
        drop_cols = [c for c in DROP_COLS if c in df.columns]
        X = build_features(df, data_corte=data_corte)
        y = get_target(df, data_corte=data_corte)

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
        X_train  = build_features(df_train)
        y_train  = get_target(df_train)

        # Parâmetros dinâmicos — conservadores se drift crítico
        params_dinamicos = params_retreino or {}
        params = {
            'objective':      'regression',
            'metric':         'mae',
            'verbosity':      -1,
            'n_estimators':   params_dinamicos.get('n_estimators', 500),
            'learning_rate':  params_dinamicos.get('learning_rate', 0.05),
            'num_leaves':     params_dinamicos.get('num_leaves', 31),
            'random_state':   42
        }
        logger.info(
            f"Params retreino: n_estimators={params['n_estimators']} "
            f"lr={params['learning_rate']} "
            f"motivo={params_dinamicos.get('motivo', 'padrao')}"
        )

        novo_modelo = lgb.LGBMRegressor(**params)
        novo_modelo.fit(X_train, y_train)

        # Validação por folds — registrar no MLflow
        from sklearn.model_selection import TimeSeriesSplit
        metricas_folds = []
        tscv = TimeSeriesSplit(n_splits=5)
        for fold, (idx_train, idx_test) in enumerate(tscv.split(X), 1):
            X_f, y_f = X.iloc[idx_train], y.iloc[idx_train]
            X_v, y_v = X.iloc[idx_test],  y.iloc[idx_test]
            m = lgb.LGBMRegressor(**params)
            m.fit(X_f, y_f)
            p = np.maximum(m.predict(X_v), 0)
            mae_f = mean_absolute_error(y_v, p)
            r2_f  = r2_score(y_v, p)
            metricas_folds.append({'fold': fold, 'mae': mae_f, 'r2': r2_f})
            logger.info(f"Fold {fold}: MAE={mae_f:.1f} | R²={r2_f:.3f}")

        # Registrar folds no MLflow
        try:
            import mlflow
            from src.tasks.mlflow_tracking import MLFLOW_TRACKING, EXPERIMENT_NAME
            mlflow.set_tracking_uri(MLFLOW_TRACKING)
            mlflow.set_experiment(EXPERIMENT_NAME)
            with mlflow.start_run(run_name=f"retreino_{datetime.now().strftime('%Y%m%d_%H%M')}",
                                  nested=True):
                for mf in metricas_folds:
                    mlflow.log_metric('mae_fold', mf['mae'], step=mf['fold'])
                    mlflow.log_metric('r2_fold',  mf['r2'],  step=mf['fold'])
                mlflow.log_metric('mae_medio_folds',
                                  np.mean([m['mae'] for m in metricas_folds]))
                mlflow.log_metric('r2_medio_folds',
                                  np.mean([m['r2']  for m in metricas_folds]))
        except Exception as e:
            logger.warning(f"MLflow folds não registrado: {e}")

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

            from src.features.build_features import atualizar_schema
            schema = atualizar_schema(
                novo_modelo, df_train,
                metricas={'r2': round(r2_novo, 3), 'mae': round(mae_novo, 1)}
            )
            schema.update({
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
            })
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