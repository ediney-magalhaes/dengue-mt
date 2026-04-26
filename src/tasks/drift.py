# ============================================================
# Dengue MT — Task: Monitoramento de Drift v2.0
# ============================================================
# Referência: Wasserstein distance para drift de features
# Níveis: Normal (<0.3) | Moderado (0.3-0.6) | Crítico (≥0.6)
# ============================================================

from prefect import task, get_run_logger
from datetime import timedelta
from src.config import (
    MODELS_DIR, MAE_LIMIAR, R2_MINIMO,
    MODEL_LATEST_PATH, GOLD_LATEST_PATH
)
import pandas as pd
import numpy as np
import joblib


# Limiares de drift baseados em Wasserstein distance normalizada
DRIFT_NORMAL  = 0.3   # abaixo → modelo estável
DRIFT_CRITICO = 0.6   # acima → retreino conservador obrigatório


def _calcular_drift_score(df_ref: pd.DataFrame, df_cur: pd.DataFrame,
                          feature_cols: list) -> dict:
    """
    Calcula score de drift via Wasserstein distance normalizada.
    Retorna score agregado e por feature.
    """
    from scipy.stats import wasserstein_distance

    scores = {}
    for col in feature_cols:
        if col in df_ref.columns and col in df_cur.columns:
            ref = df_ref[col].dropna().values
            cur = df_cur[col].dropna().values
            if len(ref) > 0 and len(cur) > 0:
                rng = ref.max() - ref.min()
                dist = wasserstein_distance(ref, cur)
                scores[col] = round(dist / rng, 4) if rng > 0 else 0.0

    score_medio = round(np.mean(list(scores.values())), 4) if scores else 0.0
    return {'score_medio': score_medio, 'por_feature': scores}


@task(name="monitorar_drift")
def monitorar_drift_modelo():
    """
    Monitora drift do modelo com janela deslizante.
    Retorna nível de drift e parâmetros de retreino recomendados.
    """
    logger = get_run_logger()
    logger.info("Monitorando drift do modelo...")

    if not MODEL_LATEST_PATH.exists() or not GOLD_LATEST_PATH.exists():
        logger.warning("Modelo ou Gold não encontrados")
        return {'status': 'pendente', 'retreinar': False,
                'nivel_drift': 'desconhecido', 'params_retreino': None}

    modelo = joblib.load(MODEL_LATEST_PATH)
    df = pd.read_parquet(GOLD_LATEST_PATH)
    df['data_se'] = pd.to_datetime(df['data_se'])
    df = df.sort_values('data_se').reset_index(drop=True)
    df = df[df['casos_confirmados'].notna()]

    # Janelas: referência (ano anterior) vs atual (últimas 26 SE)
    data_max  = df['data_se'].max()
    corte_cur = data_max - timedelta(weeks=26)
    corte_ref = data_max - timedelta(weeks=26 + 52)

    df_ref = df[(df['data_se'] >= corte_ref) & (df['data_se'] < corte_cur)].copy()
    df_cur = df[df['data_se'] >= corte_cur].copy()

    if len(df_cur) < 8:
        logger.warning("Poucos dados recentes para avaliar drift")
        return {'status': 'poucos_dados', 'retreinar': False,
                'nivel_drift': 'desconhecido', 'params_retreino': None}

    # Features do modelo
    feature_cols = [c for c in modelo.feature_name_ if c in df_cur.columns]

    # Calcular drift score (Wasserstein)
    drift_result = _calcular_drift_score(df_ref, df_cur, feature_cols)
    drift_score  = drift_result['score_medio']

    # Avaliar performance do modelo nas últimas 26 SE
    X_rec  = df_cur[feature_cols]
    y_rec  = df_cur['casos_confirmados']
    y_pred = np.maximum(np.expm1(modelo.predict(X_rec)), 0)

    from sklearn.metrics import mean_absolute_error, r2_score
    mae_recente = mean_absolute_error(y_rec, y_pred)
    r2_recente  = r2_score(y_rec, y_pred)

    # Determinar nível de drift
    if drift_score < DRIFT_NORMAL:
        nivel = 'normal'
    elif drift_score < DRIFT_CRITICO:
        nivel = 'moderado'
    else:
        nivel = 'critico'

    # Decisão de retreino
    retreinar = (
        mae_recente > MAE_LIMIAR or
        r2_recente  < R2_MINIMO  or
        nivel == 'critico'
    )

    # Parâmetros de retreino — conservadores se drift crítico
    if nivel == 'critico':
        params_retreino = {
            'n_estimators':  1000,
            'learning_rate': 0.01,
            'num_leaves':    20,
            'motivo':        'drift_critico'
        }
    else:
        params_retreino = {
            'n_estimators':  500,
            'learning_rate': 0.05,
            'num_leaves':    31,
            'motivo':        'retreino_padrao'
        }

    logger.info(f"MAE recente (26 SE): {mae_recente:.1f} | R²: {r2_recente:.3f}")
    logger.info(f"Drift score: {drift_score:.3f} | Nível: {nivel.upper()}")
    logger.info(f"Limiares: MAE≤{MAE_LIMIAR} | R²≥{R2_MINIMO}")
    if retreinar:
        logger.info(
            f"{'DRIFT CRÍTICO — retreino conservador!' if nivel == 'critico' else 'DRIFT MODERADO — retreino padrão!'}"
        )
    else:
        logger.info("Modelo estável — sem retreino necessário")

    return {
        'status':            'ok',
        'mae_recente':       round(mae_recente, 2),
        'r2_recente':        round(r2_recente, 3),
        'drift_score':       drift_score,
        'drift_por_feature': drift_result['por_feature'],
        'nivel_drift':       nivel,
        'retreinar':         retreinar,
        'params_retreino':   params_retreino,
        'n_registros':       len(df_cur)
    }