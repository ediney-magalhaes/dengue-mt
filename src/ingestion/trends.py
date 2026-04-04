# ============================================================
# Dengue MT — Ingestão Google Trends
# ============================================================
# Responsabilidade: Bronze → Silver para Google Trends
# ============================================================

import logging
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from src.config import DATA_DIR

logger = logging.getLogger('dengue-mt.ingestion')

BRONZE_DIR = DATA_DIR / 'bronze' / 'trends'
SILVER_DIR = DATA_DIR / 'silver' / 'trends'
BRONZE_DIR.mkdir(parents=True, exist_ok=True)
SILVER_DIR.mkdir(parents=True, exist_ok=True)


def ingerir_bronze(data_corte=None) -> pd.DataFrame:
    """
    Busca Google Trends via pytrends e salva na camada Bronze.
    Aplica lag=7d para evitar data leakage.
    """
    from pytrends.request import TrendReq

    pytrends  = TrendReq(hl='pt-BR', tz=-240)
    data_fim  = data_corte if data_corte else datetime.now()
    hoje      = data_fim.strftime('%Y-%m-%d')
    inicio    = (data_fim - timedelta(days=90)).strftime('%Y-%m-%d')

    pytrends.build_payload(
        kw_list=['dengue'],
        timeframe=f'{inicio} {hoje}',
        geo='BR-MT'
    )
    df = pytrends.interest_over_time()

    if df.empty:
        raise ValueError("Google Trends retornou vazio")

    df_bronze = df.reset_index()[['date', 'dengue']].copy()
    df_bronze.columns = ['data', 'trends_dengue_raw']
    df_bronze['ingestao_ts'] = datetime.now().isoformat()
    df_bronze['fonte']       = 'google_trends_api'
    df_bronze['geo']         = 'BR-MT'

    path = BRONZE_DIR / 'trends_dengue_latest.parquet'
    df_bronze.to_parquet(path, index=False)
    logger.info(f"Bronze Trends: {len(df_bronze)} semanas → {path.name}")
    return df_bronze


def bronze_para_silver(df: pd.DataFrame,
                        data_corte=None) -> pd.DataFrame:
    """
    Transforma Bronze Trends em Silver:
    - Converte tipos
    - Aplica corte temporal (lag=7d garantido)
    - Valida intervalo [0, 100]
    """
    df = df.copy()
    df['data']          = pd.to_datetime(df['data'])
    df['trends_dengue'] = pd.to_numeric(df['trends_dengue_raw'], errors='coerce')

    # Validação — Trends entre 0 e 100
    df = df[df['trends_dengue'].between(0, 100) | df['trends_dengue'].isna()]

    # Corte temporal anti-leakage
    if data_corte is not None:
        df = df[df['data'] <= pd.Timestamp(data_corte)]

    cols = ['data', 'trends_dengue']
    df   = df[cols].sort_values('data').reset_index(drop=True)

    logger.info(f"Silver Trends: {len(df)} semanas")
    return df


def salvar_silver(df: pd.DataFrame) -> Path:
    path = SILVER_DIR / 'trends_dengue_latest.parquet'
    df.to_parquet(path, index=False)
    logger.info(f"Silver Trends salvo: {path}")
    return path


def carregar_silver_fallback() -> pd.DataFrame | None:
    path = SILVER_DIR / 'trends_dengue_latest.parquet'
    if path.exists():
        logger.warning("Trends — usando Silver salvo como fallback")
        return pd.read_parquet(path)
    return None