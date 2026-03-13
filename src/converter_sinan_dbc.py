"""
converter_sinan_dbc.py
----------------------
Converte arquivos .dbc do SINAN Dengue para .parquet filtrados por MT.

IMPORTANTE: Este script requer ambiente Linux (ou Google Colab) devido à
dependência do pyreaddbc que não compila no Windows.

Como usar no Google Colab:
    1. Acesse https://colab.research.google.com
    2. Instale as dependências: !pip install pysus pandas pyarrow -q
    3. Execute este script
    4. Baixe os arquivos gerados em data/processed/sinan/

Arquivos gerados:
    - dengue_mt_2018.parquet
    - dengue_mt_2019.parquet
    - dengue_mt_2020.parquet
    - dengue_mt_2021.parquet
    - dengue_mt_2022.parquet
    - dengue_mt_2023.parquet
    - dengue_mt_2024.parquet
"""

from pysus.ftp.databases.sinan import SINAN
import pyarrow.parquet as pq
import pandas as pd
import os

# Configurações
UF_MT = '51'
ANOS = range(2018, 2025)
DESTINO = 'dengue_mt'

os.makedirs(DESTINO, exist_ok=True)
sinan = SINAN().load()


def converter_ano(ano: int) -> int:
    """Baixa, filtra por MT e salva o arquivo de um ano específico."""
    print(f"\n Processando {ano}...")
    files = sinan.get_files('DENG', year=ano)
    parquet_set = files[0].download()

    # 2024 vem particionado em múltiplos arquivos
    if hasattr(parquet_set, 'path') and os.path.isdir(parquet_set.path):
        arquivos = [
            os.path.join(parquet_set.path, f)
            for f in os.listdir(parquet_set.path)
            if f.endswith('.parquet')
        ]
        chunks = []
        for arq in arquivos:
            df_chunk = pq.read_table(arq).to_pandas()
            df_mt = df_chunk[df_chunk['SG_UF_NOT'] == UF_MT].copy()
            if len(df_mt) > 0:
                for col in df_mt.columns:
                    if df_mt[col].dtype == 'object':
                        df_mt[col] = df_mt[col].astype(str)
                chunks.append(df_mt)
            del df_chunk, df_mt
        df_final = pd.concat(chunks, ignore_index=True)

    # Anos anteriores vêm como arquivo único
    else:
        df = parquet_set.to_dataframe()
        df_final = df[df['SG_UF_NOT'] == UF_MT].copy()
        for col in df_final.columns:
            if df_final[col].dtype == 'object':
                df_final[col] = df_final[col].astype(str)
        del df

    # Salvar
    destino_arquivo = f'{DESTINO}/dengue_mt_{ano}.parquet'
    df_final.to_parquet(destino_arquivo, index=False)
    total = len(df_final)
    print(f"{ano}: {total} registros salvos em {destino_arquivo}")
    return total


if __name__ == "__main__":
    print("Iniciando conversão SINAN Dengue → Parquet (MT)\n")
    resumo = {}

    for ano in ANOS:
        try:
            resumo[ano] = converter_ano(ano)
        except Exception as e:
            print(f"Erro em {ano}: {e}")
            resumo[ano] = 0

    print("\n Resumo final:")
    total_geral = 0
    for ano, qtd in resumo.items():
        print(f"  {ano}: {qtd:>8,} registros")
        total_geral += qtd
    print(f"  {'TOTAL':>4}: {total_geral:>8,} registros")