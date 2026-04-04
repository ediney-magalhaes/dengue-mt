# ============================================================
# Dengue MT — Ingestão InfoDengue
# ============================================================
# Responsabilidade: Bronze → Silver para dados InfoDengue API
# Separado da orquestração Prefect (src/tasks/ingestao.py)
# ============================================================

import logging
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path
from src.config import DATA_DIR

logger = logging.getLogger('dengue-mt.ingestion')

BRONZE_DIR = DATA_DIR / 'bronze' / 'infodengue'
SILVER_DIR = DATA_DIR / 'silver' / 'infodengue'
BRONZE_DIR.mkdir(parents=True, exist_ok=True)
SILVER_DIR.mkdir(parents=True, exist_ok=True)

GEOCODES = {
    'cuiaba':        '5103403',
    'varzea_grande': '5108402'
}

RENAME_MAP = {
    'casos':     'casos_confirmados',
    'casos_est': 'casos_nowcast',
    'tempmed':   'temp_media',
    'tempmin':   'temp_min',
    'tempmax':   'temp_max',
    'umidmed':   'umidade_media',
    'umidmin':   'umidade_min',
    'umidmax':   'umidade_max',
    'Rt':        'rt_index',
    'nivel':     'nivel_alerta',
    'p_inc100k': 'incidencia_100k',
}

COLS_SILVER = [
    'data', 'municipio', 'geocode',
    'casos_confirmados', 'casos_nowcast',
    'temp_media', 'temp_min', 'temp_max',
    'umidade_media', 'umidade_min', 'umidade_max',
    'rt_index', 'nivel_alerta', 'incidencia_100k',
    'SE', 'pop', 'receptivo', 'transmissao'
]


def ingerir_bronze(ano_inicio: int = 2025,
                   data_corte=None) -> pd.DataFrame:
    """
    Busca dados da InfoDengue API e salva na camada Bronze.
    Retorna DataFrame bruto com todos os campos da API.
    """
    hoje      = datetime.now()
    ano_atual = hoje.year
    dfs       = []

    for municipio, geocode in GEOCODES.items():
        for ano in range(ano_inicio, ano_atual + 1):
            params = {
                'geocode':  geocode,
                'disease':  'dengue',
                'format':   'json',
                'ew_start': 1,
                'ew_end':   53,
                'ey_start': ano,
                'ey_end':   ano
            }
            r = requests.get(
                'https://info.dengue.mat.br/api/alertcity',
                params=params, timeout=30
            )
            if r.status_code != 200 or not r.json():
                logger.warning(f"InfoDengue {municipio} {ano}: status {r.status_code}")
                continue

            df = pd.DataFrame(r.json())
            df['municipio']   = municipio
            df['geocode']     = geocode
            df['ingestao_ts'] = datetime.now().isoformat()
            df['fonte']       = 'infodengue_api'

            # Salvar Bronze por município/ano
            path = BRONZE_DIR / f'infodengue_{municipio}_{ano}.parquet'
            df.to_parquet(path, index=False)
            logger.info(f"Bronze: {municipio} {ano} → {len(df)} semanas")
            dfs.append(df)

    if not dfs:
        raise ValueError("InfoDengue — sem dados da API")

    df_all = pd.concat(dfs, ignore_index=True)
    logger.info(f"Bronze total: {len(df_all)} registros")
    return df_all


def bronze_para_silver(df: pd.DataFrame,
                        data_corte=None) -> pd.DataFrame:
    """
    Transforma Bronze InfoDengue em Silver:
    - Converte timestamps
    - Renomeia colunas para padrão do projeto
    - Valida tipos e intervalos
    - Aplica corte temporal
    - Seleciona colunas Silver
    """
    df = df.copy()

    # Converter timestamp para data
    df['data'] = pd.to_datetime(df['data_iniSE'], unit='ms')

    # Renomear colunas
    df = df.rename(columns={k: v for k, v in RENAME_MAP.items()
                             if k in df.columns})

    # Converter numéricas
    cols_num = ['temp_media', 'temp_min', 'temp_max',
                'umidade_media', 'umidade_min', 'umidade_max',
                'casos_confirmados', 'casos_nowcast',
                'rt_index', 'incidencia_100k']
    for col in cols_num:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Validações Silver
    df = df[df['data'].notna()]
    df = df[df['casos_confirmados'] >= 0]
    if 'temp_media' in df.columns:
        mask_temp = df['temp_media'].between(10, 50) | df['temp_media'].isna()
        df = df[mask_temp]

    # Corte temporal anti-leakage
    if data_corte is not None:
        df = df[df['data'] <= pd.Timestamp(data_corte)]

    # Selecionar colunas Silver
    cols = [c for c in COLS_SILVER if c in df.columns]
    df   = df[cols]

    df = df.sort_values('data').reset_index(drop=True)
    logger.info(f"Silver InfoDengue: {len(df)} registros")
    return df


def salvar_silver(df: pd.DataFrame) -> Path:
    """Persiste Silver InfoDengue em disco."""
    path = SILVER_DIR / 'infodengue_2025_atual.parquet'
    df.to_parquet(path, index=False)
    logger.info(f"Silver salvo: {path}")
    return path


def carregar_silver_fallback() -> pd.DataFrame | None:
    """Carrega Silver salvo como fallback."""
    path = SILVER_DIR / 'infodengue_2025_atual.parquet'
    if path.exists():
        logger.warning("InfoDengue — usando Silver salvo como fallback")
        return pd.read_parquet(path)
    return None