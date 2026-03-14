"""
baixar_nasa_power.py
--------------------
Baixa dados de radiação solar da NASA POWER API para Cuiabá/MT.
Cobertura diária sem falhas desde 1981 — substitui sensor INMET defeituoso.

Parâmetro: ALLSKY_SFC_SW_DWN (MJ/m²/dia)

Como usar:
    python src/baixar_nasa_power.py
"""

import requests
import pandas as pd
import numpy as np
from pathlib import Path

# Coordenadas da estação A901 — Cuiabá
LAT = -15.5961
LON = -56.0974
ANO_INICIO = 2018
ANO_FIM = 2024
SAIDA = Path('data/processed/nasa_power_radiacao_2018_2024.parquet')


def baixar_nasa_power(lat: float, lon: float, ano_inicio: int, ano_fim: int) -> pd.DataFrame:
    url = (
        f"https://power.larc.nasa.gov/api/temporal/daily/point"
        f"?parameters=ALLSKY_SFC_SW_DWN"
        f"&community=RE"
        f"&longitude={lon}"
        f"&latitude={lat}"
        f"&start={ano_inicio}0101"
        f"&end={ano_fim}1231"
        f"&format=JSON"
    )
    print(f"Consultando NASA POWER ({ano_inicio}–{ano_fim})...")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()

    data = resp.json()
    radiacao = data['properties']['parameter']['ALLSKY_SFC_SW_DWN']

    df = pd.DataFrame(list(radiacao.items()), columns=['data_str', 'radiacao_mj'])
    df['data'] = pd.to_datetime(df['data_str'], format='%Y%m%d')
    df = df[['data', 'radiacao_mj']]
    df['radiacao_mj'] = df['radiacao_mj'].replace(-999.0, np.nan)

    return df


if __name__ == '__main__':
    df = baixar_nasa_power(LAT, LON, ANO_INICIO, ANO_FIM)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(SAIDA, index=False)
    print(f"Salvo: {SAIDA}")
    print(f"   {len(df):,} dias | NaNs: {df['radiacao_mj'].isna().sum()}")