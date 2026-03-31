"""
baixar_oni_index.py
-------------------
Baixa o ONI Index (El Niño/La Niña) da NOAA.
Usado como feature de ciclo climático global no modelo preditivo.

Fonte: NOAA Climate Prediction Center
ONI > +0.5 = El Niño | ONI < -0.5 = La Niña | entre = Neutro

Como usar:
    python src/baixar_oni_index.py
"""

import requests
import pandas as pd
from io import StringIO
from pathlib import Path

URL_ONI = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
SAIDA = Path('data/processed/oni_index_2018_2024.parquet')
ANO_INICIO = 2018
ANO_FIM = 2024

SEAS_MAP = {
    'DJF': 1, 'JFM': 2, 'FMA': 3, 'MAM': 4,
    'AMJ': 5, 'MJJ': 6, 'JJA': 7, 'JAS': 8,
    'ASO': 9, 'SON': 10, 'OND': 11, 'NDJ': 12
}


def baixar_oni(ano_inicio: int, ano_fim: int) -> pd.DataFrame:
    print(f"Baixando ONI Index da NOAA...")
    resp = requests.get(URL_ONI, timeout=30)
    resp.raise_for_status()

    df = pd.read_csv(StringIO(resp.text), sep='\s+')
    df = df[df['YR'].between(ano_inicio, ano_fim)].copy()

    df['mes'] = df['SEAS'].map(SEAS_MAP)
    df['data'] = pd.to_datetime(dict(year=df['YR'], month=df['mes'], day=1))
    df = df[['data', 'ANOM']].rename(columns={'ANOM': 'oni_index'})

    df['fase_enso'] = pd.cut(df['oni_index'],
        bins=[-999, -0.5, 0.5, 999],
        labels=['La_Nina', 'Neutro', 'El_Nino'])
    df['fase_enso_num'] = df['fase_enso'].map({'La_Nina': -1, 'Neutro': 0, 'El_Nino': 1})

    return df


if __name__ == '__main__':
    df = baixar_oni(ANO_INICIO, ANO_FIM)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(SAIDA, index=False)
    print(f"Salvo: {SAIDA}")
    print(f"   {len(df)} registros")
    print(df['fase_enso'].value_counts().to_string())