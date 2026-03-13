"""
processar_inmet.py
------------------
Processa os ZIPs do INMET, extrai estação A901 (Cuiabá) e agrega por dia.

Como usar:
    python src/processar_inmet.py
"""

import zipfile, io, os
import pandas as pd
from pathlib import Path

PASTA_INMET = Path('data/raw/inmet')
DESTINO = Path('data/processed/inmet')
ESTACOES = ['A901']

COLUNAS = {
    'DATA (YYYY-MM-DD)': 'data', 'Data': 'data',
    'PRECIPITAÇÃO TOTAL, HORÁRIO (mm)': 'precipitacao_mm',
    'TEMPERATURA DO AR - BULBO SECO, HORARIA (°C)': 'temp_bulbo_seco',
    'TEMPERATURA MÁXIMA NA HORA ANT. (AUT) (°C)': 'temp_max',
    'TEMPERATURA MÍNIMA NA HORA ANT. (AUT) (°C)': 'temp_min',
    'UMIDADE RELATIVA DO AR, HORARIA (%)': 'umidade_rel',
    'UMIDADE REL. MAX. NA HORA ANT. (AUT) (%)': 'umidade_max',
    'UMIDADE REL. MIN. NA HORA ANT. (AUT) (%)': 'umidade_min',
}

def processar_inmet():
    DESTINO.mkdir(parents=True, exist_ok=True)
    dfs = []

    for ano in range(2018, 2025):
        zip_path = PASTA_INMET / f'{ano}.zip'
        print(f"Processando {ano}...")

        with zipfile.ZipFile(zip_path) as z:
            arquivos = [f for f in z.namelist()
                        if any(f'_{e}_' in f for e in ESTACOES)]

            for arq in arquivos:
                estacao = [p for p in arq.split('_') if p.startswith('A')][0]
                cidade = arq.split('_')[4]

                with z.open(arq) as f:
                    df = pd.read_csv(
                        io.TextIOWrapper(f, encoding='latin-1'),
                        sep=';', skiprows=8, decimal=',',
                        na_values=['-9999', '-9999.0', '']
                    )
                    df = df.loc[:, ~df.columns.str.startswith('Unnamed')]
                    df = df.dropna(how='all')
                    df = df.rename(columns={k: v for k, v in COLUNAS.items() if k in df.columns})

                    if 'data' not in df.columns:
                        continue

                    df['data'] = pd.to_datetime(df['data'], errors='coerce')
                    df = df.dropna(subset=['data'])

                    agg = df.groupby('data').agg(
                        precipitacao_total=('precipitacao_mm', 'sum'),
                        temp_media=('temp_bulbo_seco', 'mean'),
                        temp_max=('temp_max', 'max'),
                        temp_min=('temp_min', 'min'),
                        umidade_media=('umidade_rel', 'mean'),
                        umidade_max=('umidade_max', 'max'),
                        umidade_min=('umidade_min', 'min'),
                    ).reset_index()

                    agg['estacao'] = estacao
                    agg['cidade'] = cidade
                    dfs.append(agg)
                    print(f" {estacao} {cidade}: {len(agg)} dias")

    inmet = pd.concat(dfs, ignore_index=True)
    saida = DESTINO / 'inmet_cuiaba_2018_2024.parquet'
    inmet.to_parquet(saida, index=False)
    print(f"\n Salvo: {saida} ({len(inmet):,} registros)")
    return inmet

if __name__ == '__main__':
    processar_inmet()