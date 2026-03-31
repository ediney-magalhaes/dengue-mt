"""
processar_gee.py
----------------
Processa o CSV exportado do GEE (blend Sentinel-2 + MODIS)
e gera o dataset processado em Parquet.

Fonte NDVI: Sentinel-2 SR Harmonized (prioridade) + MODIS MOD13A3 (complemento)
Fonte NDWI: Sentinel-2 SR Harmonized + imputação sazonal nos meses MODIS

Como usar:
    python src/processar_gee.py
"""

import pandas as pd
import numpy as np
from pathlib import Path

ENTRADA = Path('data/raw/gee/ndvi_ndwi_blend_2018_2024.csv')
SAIDA = Path('data/processed/gee_ndvi_ndwi_blend_2018_2024.parquet')


def processar_gee():
    df = pd.read_csv(ENTRADA)
    df = df[['ano','mes','data','ndvi_final','ndwi_final','fonte','n_s2','n_modis']].copy()
    df['data'] = pd.to_datetime(df['data'], format='%Y-%m')
    df = df.sort_values('data').reset_index(drop=True)

    # Imputação sazonal do NDWI nos meses MODIS (MODIS não tem banda equivalente)
    media_ndwi = df.groupby('mes')['ndwi_final'].mean()
    for idx, row in df.iterrows():
        if pd.isna(row['ndwi_final']):
            df.at[idx, 'ndwi_final'] = media_ndwi.loc[row['mes']]

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(SAIDA, index=False)

    print(f"✅ Dataset GEE salvo: {SAIDA}")
    print(f"   {len(df)} registros | Período: {df['data'].min().date()} → {df['data'].max().date()}")
    print(f"   Fontes: {df['fonte'].value_counts().to_dict()}")
    print(f"   NaNs: {df[['ndvi_final','ndwi_final']].isna().sum().to_dict()}")
    return df


if __name__ == '__main__':
    processar_gee()