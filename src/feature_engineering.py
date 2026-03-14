"""
feature_engineering.py
-----------------------
Constrói o dataset final com todas as features para modelagem.

Fontes integradas:
  - SINAN MT (epidemiológico) — lags e médias móveis de casos
  - INMET A901 Cuiabá (climático) — temperatura, precipitação, umidade
  - NASA POWER (radiação solar) — substitui sensor INMET defeituoso
  - GEE Sentinel-2 + MODIS (satélite) — NDVI e NDWI mensais
  - NOAA ONI Index (ENSO) — El Niño/La Niña
  - Features derivadas — sazonalidade cíclica, ciclo epidêmico

Como usar:
    python src/feature_engineering.py

Saída:
    data/processed/dataset_features_v2.parquet
"""

import pandas as pd
import numpy as np
import requests
from io import StringIO
from pathlib import Path

# Caminhos
MERGED_PATH = Path('data/processed/dengue_clima_merged.parquet')
GEE_PATH = Path('data/processed/gee_ndvi_ndwi_blend_2018_2024.parquet')
SAIDA = Path('data/processed/dataset_features_v2.parquet')

ANOS_PICO = [2020, 2024]

SEAS_MAP = {
    'DJF': 1, 'JFM': 2, 'FMA': 3, 'MAM': 4,
    'AMJ': 5, 'MJJ': 6, 'JJA': 7, 'JAS': 8,
    'ASO': 9, 'SON': 10, 'OND': 11, 'NDJ': 12
}


def carregar_base() -> pd.DataFrame:
    df = pd.read_parquet(MERGED_PATH)
    df['data'] = pd.to_datetime(df['data'])
    return df.sort_values('data').reset_index(drop=True)


def adicionar_features_temporais(df: pd.DataFrame) -> pd.DataFrame:
    df['ano'] = df['data'].dt.year
    df['mes'] = df['data'].dt.month
    df['semana_ano'] = df['data'].dt.isocalendar().week.astype(int)
    df['dia_ano'] = df['data'].dt.dayofyear
    df['trimestre'] = df['data'].dt.quarter
    df['mes_seno'] = np.sin(2 * np.pi * df['mes'] / 12)
    df['mes_cosseno'] = np.cos(2 * np.pi * df['mes'] / 12)
    df['semana_seno'] = np.sin(2 * np.pi * df['semana_ano'] / 52)
    df['semana_cosseno'] = np.cos(2 * np.pi * df['semana_ano'] / 52)
    return df


def adicionar_lags_casos(df: pd.DataFrame) -> pd.DataFrame:
    for lag in [7, 14, 21, 28]:
        df[f'casos_lag_{lag}d'] = df['casos'].shift(lag)
    for janela in [7, 14, 28]:
        df[f'casos_mm_{janela}d'] = df['casos'].shift(1).rolling(janela).mean()
    return df


def adicionar_features_climaticas(df: pd.DataFrame) -> pd.DataFrame:
    for lag in [28, 35, 42]:
        df[f'precip_lag_{lag}d'] = df['precipitacao_total'].shift(lag)
        df[f'umidade_lag_{lag}d'] = df['umidade_media'].shift(lag)
        df[f'temp_lag_{lag}d'] = df['temp_media'].shift(lag)
    for janela in [7, 14, 28]:
        df[f'precip_mm_{janela}d'] = df['precipitacao_total'].rolling(janela).mean()
        df[f'umidade_mm_{janela}d'] = df['umidade_media'].rolling(janela).mean()
    df['amplitude_termica'] = df['temp_max'] - df['temp_min']
    df['precip_acum_7d'] = df['precipitacao_total'].rolling(7).sum()
    df['precip_acum_14d'] = df['precipitacao_total'].rolling(14).sum()
    df['precip_acum_28d'] = df['precipitacao_total'].rolling(28).sum()
    df['dias_sem_chuva'] = (df['precipitacao_total'] == 0).astype(int).groupby(
        (df['precipitacao_total'] != 0).cumsum()).cumsum()
    return df


def adicionar_gee(df: pd.DataFrame) -> pd.DataFrame:
    gee = pd.read_parquet(GEE_PATH)
    gee['mes_periodo'] = gee['data'].dt.to_period('M')
    df['mes_periodo'] = df['data'].dt.to_period('M')
    df = df.merge(
        gee[['mes_periodo', 'ndvi_final', 'ndwi_final']].rename(
            columns={'ndvi_final': 'ndvi', 'ndwi_final': 'ndwi'}),
        on='mes_periodo', how='left'
    )
    return df.drop(columns=['mes_periodo'])


def adicionar_nasa_power(df: pd.DataFrame) -> pd.DataFrame:
    url = (
        "https://power.larc.nasa.gov/api/temporal/daily/point"
        "?parameters=ALLSKY_SFC_SW_DWN&community=RE"
        "&longitude=-56.0974&latitude=-15.5961"
        "&start=20180101&end=20241231&format=JSON"
    )
    print("NASA POWER...")
    resp = requests.get(url, timeout=120)
    radiacao = resp.json()['properties']['parameter']['ALLSKY_SFC_SW_DWN']
    nasa = pd.DataFrame(list(radiacao.items()), columns=['data_str', 'radiacao_mj'])
    nasa['data'] = pd.to_datetime(nasa['data_str'], format='%Y%m%d')
    nasa['radiacao_mj'] = nasa['radiacao_mj'].replace(-999.0, np.nan)
    nasa = nasa[['data', 'radiacao_mj']]

    df = df.merge(nasa, on='data', how='left')
    df['radiacao_lag_28d'] = df['radiacao_mj'].shift(28)
    df['radiacao_mm_14d'] = df['radiacao_mj'].rolling(14).mean()
    return df


def adicionar_oni(df: pd.DataFrame) -> pd.DataFrame:
    print("ONI Index NOAA...")
    resp = requests.get("https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt", timeout=30)
    oni = pd.read_csv(StringIO(resp.text), sep='\s+')
    oni = oni[oni['YR'].between(2018, 2024)].copy()
    oni['mes'] = oni['SEAS'].map(SEAS_MAP)
    oni['data'] = pd.to_datetime(dict(year=oni['YR'], month=oni['mes'], day=1))
    oni = oni[['data', 'ANOM']].rename(columns={'ANOM': 'oni_index'})
    oni['fase_enso_num'] = pd.cut(oni['oni_index'],
        bins=[-999, -0.5, 0.5, 999], labels=[-1, 0, 1]).astype(int)

    df['mes_periodo'] = df['data'].dt.to_period('M').dt.to_timestamp()
    oni = oni.rename(columns={'data': 'mes_periodo'})
    df = df.merge(oni, on='mes_periodo', how='left')
    return df.drop(columns=['mes_periodo'])


def adicionar_ciclo_epidemico(df: pd.DataFrame) -> pd.DataFrame:
    def anos_desde_pico(ano):
        picos_anteriores = [p for p in ANOS_PICO if p <= ano]
        return ano - max(picos_anteriores) if picos_anteriores else ano - 2018

    df['anos_desde_pico'] = df['ano'].apply(anos_desde_pico)
    df['ciclo_epidemico'] = df['anos_desde_pico'] % 4
    df['casos_acum_ano'] = df.groupby('ano')['casos'].cumsum()
    return df


def build_features():
    print("Construindo dataset de features...")
    df = carregar_base()
    df = adicionar_features_temporais(df)
    df = adicionar_lags_casos(df)
    df = adicionar_features_climaticas(df)
    df = adicionar_gee(df)
    df = adicionar_nasa_power(df)
    df = adicionar_oni(df)
    df = adicionar_ciclo_epidemico(df)

    # Remover colunas não numéricas e NaNs dos lags
    df = df.drop(columns=['estacao', 'cidade'], errors='ignore')
    df = df.dropna().reset_index(drop=True)

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(SAIDA, index=False)
    print(f"\nDataset salvo: {SAIDA}")
    print(f"   {df.shape[0]:,} registros × {df.shape[1]} features")
    return df


if __name__ == '__main__':
    build_features()