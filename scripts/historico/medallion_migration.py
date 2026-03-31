"""
medallion_migration.py
----------------------
Migra dados para Arquitetura Medalhão (Bronze → Silver → Gold)
usando Polars para processamento eficiente.

Estrutura:
  🥉 Bronze: dados brutos imutáveis (cópia de raw/)
  🥈 Silver: dados limpos e validados (Polars)
  🥇 Gold:   dataset de features pronto para ML

Como usar:
    python src/medallion_migration.py
"""

import polars as pl
import shutil
from pathlib import Path

# Caminhos
RAW_SINAN    = Path('data/processed/sinan')
RAW_INMET    = Path('data/processed/inmet')
RAW_GEE      = Path('data/processed')

BRONZE_SINAN = Path('data/bronze/sinan')
BRONZE_INMET = Path('data/bronze/inmet')
BRONZE_GEE   = Path('data/bronze/gee')

SILVER_SINAN = Path('data/silver/sinan')
SILVER_INMET = Path('data/silver/inmet')
SILVER_GEE   = Path('data/silver/gee')

GOLD         = Path('data/gold')

# Códigos de classificação confirmados por período
CLASSI_CONFIRMADA = {
    'antiga':    ['1', '2', '3'],
    'transicao': ['1', '2', '3', '10', '11', '12'],
    'nova':      ['10', '11', '12'],
}

def get_classi_por_ano(ano: int) -> list:
    if ano <= 2013:
        return CLASSI_CONFIRMADA['antiga']
    elif ano <= 2016:
        return CLASSI_CONFIRMADA['transicao']
    else:
        return CLASSI_CONFIRMADA['nova']


# ============================================================
# BRONZE — copiar dados brutos
# ============================================================
def bronze_sinan():
    print("🥉 Bronze SINAN...")
    count = 0
    for arq in sorted(RAW_SINAN.glob('*.parquet')):
        shutil.copy2(arq, BRONZE_SINAN / arq.name)
        count += 1
    print(f"   {count} arquivos copiados → {BRONZE_SINAN}")

def bronze_inmet():
    print("🥉 Bronze INMET...")
    arq = RAW_INMET / 'inmet_cuiaba_2018_2024.parquet'
    if arq.exists():
        shutil.copy2(arq, BRONZE_INMET / arq.name)
        print(f"   1 arquivo copiado → {BRONZE_INMET}")

def bronze_gee():
    print("🥉 Bronze GEE...")
    count = 0
    for arq in RAW_GEE.glob('gee_*.parquet'):
        shutil.copy2(arq, BRONZE_GEE / arq.name)
        count += 1
    print(f"   {count} arquivos copiados → {BRONZE_GEE}")


# ============================================================
# SILVER — limpar e validar com Polars
# ============================================================
def silver_sinan():
    print("\n🥈 Silver SINAN...")
    dfs = []

    for arq in sorted(BRONZE_SINAN.glob('*.parquet')):
        ano = int(arq.stem.split('_')[-1])
        classi_validas = get_classi_por_ano(ano)

        df = pl.read_parquet(arq)

        # Normalizar e filtrar CLASSI_FIN
        if 'CLASSI_FIN' in df.columns:
            df = df.with_columns(
                pl.col('CLASSI_FIN').cast(pl.String).str.strip_chars()
            )
            df = df.filter(pl.col('CLASSI_FIN').is_in(classi_validas))

        # Selecionar colunas essenciais disponíveis
        colunas = ['DT_NOTIFIC', 'SG_UF_NOT', 'ID_MUNICIP', 'ID_UNIDADE',
           'CS_SEXO', 'NU_IDADE_N', 'HOSPITALIZ', 'EVOLUCAO']
        df = df.select([c for c in colunas if c in df.columns])

        # Converter data — verificar tipo antes de agir
        dtype = df['DT_NOTIFIC'].dtype
        if dtype == pl.String or str(dtype) == 'Utf8':
            sample = df['DT_NOTIFIC'].drop_nulls().head(1)[0]
            fmt = '%Y%m%d' if len(str(sample).replace('-', '')) == 8 and '-' not in str(sample) else '%Y-%m-%d'
            df = df.with_columns(
                pl.col('DT_NOTIFIC').str.to_date(format=fmt, strict=False)
            )
        elif dtype != pl.Date:
            df = df.with_columns(
                pl.col('DT_NOTIFIC').cast(pl.Date, strict=False)
            )
        # Se já for pl.Date — não fazer nada

        df = df.with_columns(pl.lit(ano).alias('ano'))
        df = df.drop_nulls(subset=['DT_NOTIFIC'])
        dfs.append(df)
        print(f"   {ano}: {len(df):,} registros confirmados")

    df_final = pl.concat(dfs, how='diagonal').sort('DT_NOTIFIC')

    for ano in df_final['ano'].unique().sort().to_list():
        df_ano = df_final.filter(pl.col('ano') == ano)
        df_ano.write_parquet(SILVER_SINAN / f'dengue_mt_{ano}.parquet')

    print(f"   Total silver SINAN: {len(df_final):,} registros")
    return df_final


def silver_inmet():
    print("\n🥈 Silver INMET...")
    df = pl.read_parquet(BRONZE_INMET / 'inmet_cuiaba_2018_2024.parquet')

    df = df.with_columns([
        pl.col('data').cast(pl.Date),
        pl.col('precipitacao_total').clip(0, 500),
        pl.col('temp_media').clip(10, 45),
        pl.col('umidade_media').clip(0, 100),
    ])
    df = df.drop_nulls(subset=['temp_media', 'umidade_media'])
    df.write_parquet(SILVER_INMET / 'inmet_cuiaba_2018_2024.parquet')
    print(f"   Silver INMET: {len(df):,} registros")
    return df


def silver_gee():
    print("\n🥈 Silver GEE...")
    arq = BRONZE_GEE / 'gee_ndvi_ndwi_blend_2018_2024.parquet'
    if arq.exists():
        df = pl.read_parquet(arq)
        df = df.drop_nulls(subset=['ndvi_final', 'ndwi_final'])
        df.write_parquet(SILVER_GEE / 'gee_ndvi_ndwi_blend_2018_2024.parquet')
        print(f"   Silver GEE: {len(df):,} registros")
        return df


# ============================================================
# GOLD — dataset de features para ML
# ============================================================
def gold_dataset():
    print("\n🥇 Gold — dataset de features...")

    df_features = pl.read_parquet('data/processed/dataset_features_v2.parquet')
    df_hist     = pl.read_parquet('data/processed/serie_semanal_historica_2007_2024.parquet')

    df_features.write_parquet(GOLD / 'dataset_features_v2.parquet')
    df_hist.write_parquet(GOLD / 'serie_historica_2007_2024.parquet')

    print(f"   Gold features:        {df_features.shape}")
    print(f"   Gold série histórica: {df_hist.shape}")


# ============================================================
# EXECUTAR MIGRAÇÃO
# ============================================================
if __name__ == '__main__':
    print("Iniciando migração para Arquitetura Medalhão\n")
    print("=" * 50)

    bronze_sinan()
    bronze_inmet()
    bronze_gee()

    silver_sinan()
    silver_inmet()
    silver_gee()

    gold_dataset()

    print("\n" + "=" * 50)
    print("✅ Migração concluída!")
    print("""
    Estrutura final:
    data/
    ├── bronze/  ← dados brutos imutáveis
    ├── silver/  ← dados limpos (Polars)
    ├── gold/    ← features ML prontas
    └── external/← dados IBGE e shapefiles
    """)