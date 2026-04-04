# ============================================================
# Dengue MT — Ingestão NASA POWER
# ============================================================
# Responsabilidade: Bronze → Silver para dados NASA POWER API
# ============================================================

import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from src.config import DATA_DIR

logger = logging.getLogger('dengue-mt.ingestion')

BRONZE_DIR = DATA_DIR / 'bronze' / 'nasa_power'
SILVER_DIR = DATA_DIR / 'silver' / 'nasa_power'
BRONZE_DIR.mkdir(parents=True, exist_ok=True)
SILVER_DIR.mkdir(parents=True, exist_ok=True)

NASA_URL    = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMETROS  = 'ALLSKY_SFC_SW_DWN,T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M'
LATITUDE    = -15.6
LONGITUDE   = -56.1


def ingerir_bronze(data_inicio: datetime,
                   data_fim: datetime) -> pd.DataFrame:
    """
    Busca dados da NASA POWER API e salva na camada Bronze.
    Retorna DataFrame bruto com valores exatamente como vieram da API.
    """
    params = {
        'parameters': PARAMETROS,
        'community':  'RE',
        'longitude':  LONGITUDE,
        'latitude':   LATITUDE,
        'start':      data_inicio.strftime('%Y%m%d'),
        'end':        data_fim.strftime('%Y%m%d'),
        'format':     'JSON'
    }

    r = requests.get(NASA_URL, params=params, timeout=60)
    if r.status_code != 200:
        raise ValueError(f"NASA POWER status: {r.status_code}")

    parametros = r.json()['properties']['parameter']
    datas      = list(parametros['ALLSKY_SFC_SW_DWN'].keys())

    # Bronze — valores brutos da API
    df = pd.DataFrame({
        'data_str':         datas,
        'radiacao_raw':     list(parametros['ALLSKY_SFC_SW_DWN'].values()),
        'temp_media_raw':   list(parametros['T2M'].values()),
        'temp_max_raw':     list(parametros['T2M_MAX'].values()),
        'temp_min_raw':     list(parametros['T2M_MIN'].values()),
        'precipitacao_raw': list(parametros['PRECTOTCORR'].values()),
        'umidade_raw':      list(parametros['RH2M'].values()),
        'ingestao_ts':      datetime.now().isoformat(),
        'fonte':            'nasa_power_api',
        'latitude':         LATITUDE,
        'longitude':        LONGITUDE,
    })

    # Salvar Bronze
    nome  = f'nasa_{data_inicio.strftime("%Y%m%d")}_{data_fim.strftime("%Y%m%d")}.parquet'
    path  = BRONZE_DIR / nome
    df.to_parquet(path, index=False)
    logger.info(f"Bronze NASA POWER: {len(df)} dias → {nome}")
    return df


def bronze_para_silver(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transforma Bronze NASA POWER em Silver:
    - Converte datas
    - Renomeia colunas
    - Remove valores inválidos (-999)
    - Valida intervalos plausíveis
    """
    df = df.copy()
    df['data'] = pd.to_datetime(df['data_str'], format='%Y%m%d')

    df = df.rename(columns={
        'radiacao_raw':     'radiacao_mj',
        'temp_media_raw':   'temp_media_nasa',
        'temp_max_raw':     'temp_max_nasa',
        'temp_min_raw':     'temp_min_nasa',
        'precipitacao_raw': 'precipitacao_nasa',
        'umidade_raw':      'umidade_nasa',
    })

    # Substituir -999 (inválido NASA) por NaN
    cols_num = ['radiacao_mj', 'temp_media_nasa', 'temp_max_nasa',
                'temp_min_nasa', 'precipitacao_nasa', 'umidade_nasa']
    for col in cols_num:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        df[col] = df[col].replace(-999, pd.NA)

    # Validações Silver
    df = df[df['radiacao_mj'].notna()]
    df = df[df['temp_media_nasa'].between(-10, 55) | df['temp_media_nasa'].isna()]
    df = df[df['precipitacao_nasa'].ge(0) | df['precipitacao_nasa'].isna()]

    # Selecionar colunas Silver
    cols = ['data', 'radiacao_mj', 'temp_media_nasa',
            'temp_max_nasa', 'temp_min_nasa',
            'precipitacao_nasa', 'umidade_nasa']
    df = df[cols].sort_values('data').reset_index(drop=True)

    logger.info(f"Silver NASA POWER: {len(df)} dias")
    return df


def salvar_silver(df: pd.DataFrame) -> Path:
    """Persiste Silver NASA POWER em disco."""
    path = SILVER_DIR / 'nasa_power_2025_atual.parquet'
    df.to_parquet(path, index=False)
    logger.info(f"Silver salvo: {path}")
    return path


def carregar_silver_fallback() -> pd.DataFrame | None:
    """Carrega Silver salvo como fallback."""
    path = SILVER_DIR / 'nasa_power_2025_atual.parquet'
    if path.exists():
        logger.warning("NASA POWER — usando Silver salvo como fallback")
        return pd.read_parquet(path)
    return None