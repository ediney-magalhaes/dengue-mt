# ============================================================
# Dengue MT — Ingestão ONI Index NOAA
# ============================================================
# Responsabilidade: Bronze → Silver para ONI Index
# ============================================================

import logging
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path
from src.config import DATA_DIR

logger = logging.getLogger('dengue-mt.ingestion')

BRONZE_DIR = DATA_DIR / 'bronze' / 'oni'
SILVER_DIR = DATA_DIR / 'silver' / 'oni'
BRONZE_DIR.mkdir(parents=True, exist_ok=True)
SILVER_DIR.mkdir(parents=True, exist_ok=True)

ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"


def ingerir_bronze() -> pd.DataFrame:
    """
    Baixa ONI Index NOAA e salva na camada Bronze.
    Retorna DataFrame bruto.
    """
    r = requests.get(ONI_URL, timeout=15)
    if r.status_code != 200:
        raise ValueError(f"ONI NOAA status: {r.status_code}")

    linhas = [l.split() for l in r.text.strip().split('\n')[1:] if l.strip()]
    df     = pd.DataFrame(linhas, columns=['seas', 'yr', 'total', 'anom'])
    df['ingestao_ts'] = datetime.now().isoformat()
    df['fonte']       = 'noaa_oni'

    path = BRONZE_DIR / 'oni_index_latest.parquet'
    df.to_parquet(path, index=False)
    logger.info(f"Bronze ONI: {len(df)} trimestres → {path.name}")
    return df


def bronze_para_silver(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transforma Bronze ONI em Silver:
    - Converte tipos
    - Valida intervalos
    """
    df = df.copy()
    df['yr']    = pd.to_numeric(df['yr'],    errors='coerce').astype('Int64')
    df['anom']  = pd.to_numeric(df['anom'],  errors='coerce')
    df['total'] = pd.to_numeric(df['total'], errors='coerce')

    # Validação — anom ONI entre -4 e +4
    df = df[df['anom'].between(-4, 4) | df['anom'].isna()]
    df = df[df['yr'].notna()]

    cols = ['seas', 'yr', 'total', 'anom']
    df   = df[cols].reset_index(drop=True)

    logger.info(f"Silver ONI: {len(df)} trimestres")
    return df


def salvar_silver(df: pd.DataFrame) -> Path:
    path = SILVER_DIR / 'oni_index_latest.parquet'
    df.to_parquet(path, index=False)
    logger.info(f"Silver ONI salvo: {path}")
    return path


def carregar_silver_fallback() -> pd.DataFrame | None:
    path = SILVER_DIR / 'oni_index_latest.parquet'
    if path.exists():
        logger.warning("ONI — usando Silver salvo como fallback")
        return pd.read_parquet(path)
    return None