"""
config_backtesting.py — Configurações compartilhadas para backtesting
"""

import sys
from pathlib import Path
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# ── Paths ──
PROJECT_ROOT = Path(__file__).resolve().parents[2]
GOLD_PATH = PROJECT_ROOT / "data" / "gold" / "dataset_features_v5_latest.parquet"
REPORTS_DIR = PROJECT_ROOT / "reports" / "backtesting"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Parâmetros do backtesting ──
TESTE_INICIO = 2023          # Primeiro ano do período de teste
HORIZONTES = [1, 2, 3, 4]    # Semanas à frente
TARGET = "casos_confirmados"
LOG_TARGET = True             # log1p/expm1 (ADR-024)

# Features a excluir do treino (não-preditoras)
COLS_EXCLUIR = [
    "data_se", "semana_epidemiologica", "municipio_id",
    "municipio_nome", "dbt_updated_at",
    "casos_confirmados", "casos_estimados", "casos_estimados_min",
    "casos_estimados_max", "nivel_alerta", "rt_index",
    "prob_rt_maior_1", "incidencia_100k",
]

# ── Hiperparâmetros LightGBM (v5 produção) ──
LGBM_PARAMS = {
    "objective": "regression",
    "metric": "mae",
    "n_estimators": 500,
    "learning_rate": 0.05,
    "max_depth": 6,
    "num_leaves": 31,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_samples": 20,
    "random_state": 42,
    "verbosity": -1,
    "n_jobs": -1,
}

# ── Municípios ──
MUNICIPIOS = {5103403: "Cuiabá", 5108402: "Várzea Grande"}


def calcular_metricas(y_real, y_pred, y_naive=None):
    """
    Calcula métricas padrão para forecasting epidemiológico.
    
    Referências:
      - Reich et al. (2019) — FluSight: MAE, MASE como padrão
      - Araujo et al. (PNAS 2026) — IMDC24: MAE, RMSE, WIS
      - Hyndman & Koehler (2006) — MASE como métrica escalada
    
    Returns:
        dict com MAE, RMSE, R², MASE (se y_naive fornecido)
    """
    mae = mean_absolute_error(y_real, y_pred)
    rmse = np.sqrt(mean_squared_error(y_real, y_pred))
    r2 = r2_score(y_real, y_pred)

    resultado = {"MAE": mae, "RMSE": rmse, "R2": r2, "N": len(y_real)}

    # MASE = MAE_modelo / MAE_naive
    if y_naive is not None and len(y_naive) > 0:
        mae_naive = mean_absolute_error(y_real, y_naive)
        resultado["MAE_naive"] = mae_naive
        resultado["MASE"] = mae / mae_naive if mae_naive > 0 else np.inf

    return resultado


def carregar_gold():
    """Carrega Gold v5 e prepara para backtesting."""
    import polars as pl

    df = pl.read_parquet(str(GOLD_PATH)).to_pandas()
    df["data_se"] = pd.to_datetime(df["data_se"])
    df = df.sort_values(["municipio_id", "data_se"]).reset_index(drop=True)

    print(f"Gold carregado: {df.shape[0]} registros × {df.shape[1]} colunas")
    print(f"Período: {df['data_se'].min().date()} → {df['data_se'].max().date()}")
    for mun_id, nome in MUNICIPIOS.items():
        n = (df["municipio_id"] == mun_id).sum()
        print(f"  {nome}: {n} semanas")

    return df


def preparar_features(df):
    """Seleciona features para treino, excluindo colunas não-preditoras."""
    feature_cols = [c for c in df.columns if c not in COLS_EXCLUIR]
    return feature_cols


# Import pandas aqui para evitar import circular
import pandas as pd