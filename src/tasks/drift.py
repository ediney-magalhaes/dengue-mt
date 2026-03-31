# ============================================================
# Dengue MT — Task: Monitoramento de Drift + Evidently
# ============================================================
# Referência: Wasserstein distance para drift de features
# Níveis: Normal (<0.3) | Moderado (0.3-0.6) | Crítico (≥0.6)
# ============================================================

from prefect import task, get_run_logger
from datetime import timedelta
from src.config import DATA_DIR, MODELS_DIR, MAE_LIMIAR, R2_MINIMO
import pandas as pd
import numpy as np
import joblib


# Limiares de drift baseados em Wasserstein distance normalizada
DRIFT_NORMAL   = 0.3   # abaixo → modelo estável
DRIFT_CRITICO  = 0.6   # acima → retreino conservador obrigatório


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
                # Normalizar pelo range da referência
                rng = ref.max() - ref.min()
                dist = wasserstein_distance(ref, cur)
                scores[col] = round(dist / rng, 4) if rng > 0 else 0.0

    score_medio = round(np.mean(list(scores.values())), 4) if scores else 0.0
    return {'score_medio': score_medio, 'por_feature': scores}


@task(name="monitorar_drift")
def monitorar_drift_modelo():
    """
    Monitora drift do modelo com janela deslizante + Evidently.
    Retorna nível de drift e parâmetros de retreino recomendados.
    """
    logger = get_run_logger()
    logger.info("Monitorando drift do modelo...")

    modelo_path = MODELS_DIR / 'lgbm_v4_producao.pkl'
    gold_path   = DATA_DIR / 'gold' / 'dataset_features_v4.parquet'

    if not modelo_path.exists() or not gold_path.exists():
        logger.warning("Modelo ou dados não encontrados")
        return {'status': 'pendente', 'retreinar': False,
                'nivel_drift': 'desconhecido', 'params_retreino': None}

    modelo = joblib.load(modelo_path)
    df = pd.read_parquet(gold_path)
    df['data'] = pd.to_datetime(df['data'])
    df = df.sort_values('data').dropna()

    # Janelas: referência (ano anterior) vs atual (últimos 90 dias)
    data_max  = df['data'].max()
    corte_cur = data_max - timedelta(days=90)
    corte_ref = data_max - timedelta(days=90+365)

    df_ref = df[(df['data'] >= corte_ref) & (df['data'] < corte_cur)].copy()
    df_cur = df[df['data'] >= corte_cur].copy()

    if len(df_cur) < 30:
        logger.warning("Poucos dados recentes para avaliar drift")
        return {'status': 'poucos_dados', 'retreinar': False,
                'nivel_drift': 'desconhecido', 'params_retreino': None}

    # Features e target
    drop_cols    = ['data', 'casos', 'casos_nowcast', 'municipio_id']
    drop_cols    = [c for c in drop_cols if c in df_cur.columns]
    feature_cols = [c for c in modelo.feature_name_ if c in df_cur.columns]

    # Calcular drift score (Wasserstein)
    drift_result = _calcular_drift_score(df_ref, df_cur, feature_cols)
    drift_score  = drift_result['score_medio']

    # Avaliar performance do modelo nos últimos 90 dias
    X_rec = df_cur[feature_cols]
    y_rec = df_cur['casos']
    y_pred = np.maximum(modelo.predict(X_rec), 0)

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

    logger.info(f"MAE recente (90d): {mae_recente:.1f} | R²: {r2_recente:.3f}")
    logger.info(f"Drift score: {drift_score:.3f} | Nível: {nivel.upper()}")
    logger.info(f"Limiares: MAE≤{MAE_LIMIAR} | R²≥{R2_MINIMO}")
    logger.info(
        f"{'DRIFT CRÍTICO — retreino conservador!' if nivel == 'critico' else 'DRIFT MODERADO — retreino padrão!' if nivel == 'moderado' else 'Modelo estável'}"
        if retreinar else "Modelo estável — sem retreino necessário"
    )

    return {
        'status':           'ok',
        'mae_recente':      round(mae_recente, 2),
        'r2_recente':       round(r2_recente, 3),
        'drift_score':      drift_score,
        'drift_por_feature': drift_result['por_feature'],
        'nivel_drift':      nivel,
        'retreinar':        retreinar,
        'params_retreino':  params_retreino,
        'n_registros':      len(df_cur)
    }