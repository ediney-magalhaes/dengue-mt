# ============================================================
# Dengue MT — Task: Monitoramento de Drift
# ============================================================

from prefect import task, get_run_logger
from datetime import timedelta
from src.config import DATA_DIR, MODELS_DIR, MAE_LIMIAR, R2_MINIMO
import pandas as pd
import numpy as np
import joblib


@task(name="monitorar_drift")
def monitorar_drift_modelo():
    """Monitora drift do modelo com janela deslizante."""
    logger = get_run_logger()
    logger.info("Monitorando drift do modelo...")

    modelo_path = MODELS_DIR / 'lgbm_v4_producao.pkl'
    gold_path   = DATA_DIR / 'gold' / 'dataset_features_v4.parquet'

    if not modelo_path.exists() or not gold_path.exists():
        logger.warning("Modelo ou dados não encontrados")
        return {'status': 'pendente', 'retreinar': False}

    modelo = joblib.load(modelo_path)
    df = pd.read_parquet(gold_path)
    df['data'] = pd.to_datetime(df['data'])
    df = df.sort_values('data').dropna()

    # Avaliar nos últimos 90 dias
    corte = df['data'].max() - timedelta(days=90)
    df_recente = df[df['data'] >= corte].copy()

    if len(df_recente) < 30:
        logger.warning("Poucos dados recentes para avaliar drift")
        return {'status': 'poucos_dados', 'retreinar': False}

    # Features e target
    drop_cols = ['data', 'casos', 'casos_nowcast', 'municipio_id']
    drop_cols = [c for c in drop_cols if c in df_recente.columns]

    feature_cols = [c for c in modelo.feature_name_ if c in df_recente.columns]
    X_rec = df_recente[feature_cols]
    y_rec = df_recente['casos']

    y_pred = np.maximum(modelo.predict(X_rec), 0)

    from sklearn.metrics import mean_absolute_error, r2_score
    mae_recente = mean_absolute_error(y_rec, y_pred)
    r2_recente  = r2_score(y_rec, y_pred)

    retreinar = mae_recente > MAE_LIMIAR or r2_recente < R2_MINIMO

    logger.info(f"MAE recente (90d): {mae_recente:.1f} | R²: {r2_recente:.3f}")
    logger.info(f"Limiares: MAE≤{MAE_LIMIAR} | R²≥{R2_MINIMO}")
    logger.info(
        f"{'DRIFT DETECTADO — retreino necessário!' if retreinar else 'Modelo estável'}"
    )

    return {
        'status':      'ok',
        'mae_recente': round(mae_recente, 2),
        'r2_recente':  round(r2_recente, 3),
        'retreinar':   retreinar,
        'n_registros': len(df_recente)
    }