"""
criar_dataset_merged.py
-----------------------
Une os dados epidemiológicos (SINAN) com os climáticos (INMET) por data.
Gera o dataset principal usado no treinamento dos modelos.

Como usar:
    python src/criar_dataset_merged.py
"""

import pandas as pd
from pathlib import Path

SINAN_DIR = Path('data/processed/sinan')
INMET_PATH = Path('data/processed/inmet/inmet_cuiaba_2018_2024.parquet')
DESTINO = Path('data/processed/dengue_clima_merged.parquet')

# Classificações confirmadas de dengue
CLASSI_CONFIRMADAS = ['10', '11', '12']


def carregar_sinan() -> pd.DataFrame:
    dfs = []
    for arq in sorted(SINAN_DIR.glob('*.parquet')):
        df = pd.read_parquet(arq)
        df['ano'] = int(arq.stem.split('_')[-1])
        dfs.append(df)
    dengue = pd.concat(dfs, ignore_index=True)
    print(f"SINAN carregado: {len(dengue):,} registros")
    return dengue


def carregar_inmet() -> pd.DataFrame:
    inmet = pd.read_parquet(INMET_PATH)
    print(f"INMET carregado: {len(inmet):,} registros")
    return inmet


def criar_merged():
    dengue = carregar_sinan()
    inmet = carregar_inmet()

    # Filtrar confirmados e agregar por dia
    confirmados = dengue[dengue['CLASSI_FIN'].isin(CLASSI_CONFIRMADAS)].copy()
    confirmados['DT_NOTIFIC'] = pd.to_datetime(confirmados['DT_NOTIFIC'])
    casos_dia = (confirmados
                 .groupby('DT_NOTIFIC')
                 .size()
                 .reset_index(name='casos')
                 .rename(columns={'DT_NOTIFIC': 'data'}))

    # Merge por data
    merged = pd.merge(casos_dia, inmet, on='data', how='inner')
    merged = merged.sort_values('data').reset_index(drop=True)

    # Salvar
    merged.to_parquet(DESTINO, index=False)
    print(f"\nDataset merged salvo: {DESTINO}")
    print(f"   {len(merged):,} dias | {merged.shape[1]} colunas")
    print(f"   Período: {merged['data'].min().date()} → {merged['data'].max().date()}")
    return merged


if __name__ == '__main__':
    criar_merged()