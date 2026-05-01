"""
Exporta Gold do DuckDB para Parquet e publica no HF Hub
Executa após dbt run --select marts
"""
import duckdb
import pandas as pd
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

GOLD_DIR = Path('data/gold')
GOLD_DIR.mkdir(parents=True, exist_ok=True)

def exportar_gold() -> Path:
    """Exporta mart_dengue_features do DuckDB para Parquet."""
    conn = duckdb.connect('dengue_mt_dbt/dev.duckdb')
    df = conn.execute('SELECT * FROM main_marts.mart_dengue_features').df()
    conn.close()

    print(f'Gold: {len(df)} registros × {len(df.columns)} features')
    print(f'Período: {df["data_se"].min()} → {df["data_se"].max()}')
    print(f'Municípios: {df["municipio_id"].unique().tolist()}')

    # Salva com data do snapshot
    hoje = datetime.now().strftime('%Y-%m-%d')
    path_datado = GOLD_DIR / f'dataset_features_v5_{hoje}.parquet'
    path_latest_v5 = GOLD_DIR / 'dataset_features_v5_latest.parquet'
    path_latest    = GOLD_DIR / 'dataset_features_latest.parquet'

    df.to_parquet(path_datado, index=False)
    df.to_parquet(path_latest_v5, index=False)
    df.to_parquet(path_latest, index=False)

    print(f'\n✅ Gold salvo:')
    print(f'  {path_datado}')
    print(f'  {path_latest}')

    return path_latest


def publicar_hf_hub(path: Path):
    """Publica Gold no HF Hub."""
    try:
        from huggingface_hub import HfApi
        token = os.environ.get('HF_TOKEN')
        api   = HfApi()
        hoje  = datetime.now().strftime('%Y-%m-%d')

        # Upload snapshot datado
        api.upload_file(
            path_or_fileobj=str(path.parent / f'dataset_features_v5_{hoje}.parquet'),
            path_in_repo=f'gold/dataset_features_v5_{hoje}.parquet',
            repo_id='edyestatistica/dengue-mt-medallion',
            repo_type='dataset',
            token=token,
        )

        # Upload latest v5
        api.upload_file(
            path_or_fileobj=str(path.parent / 'dataset_features_v5_latest.parquet'),
            path_in_repo='gold/dataset_features_v5_latest.parquet',
            repo_id='edyestatistica/dengue-mt-medallion',
            repo_type='dataset',
            token=token,
        )

        # Upload latest genérico (lido pelo pipeline e dashboard)
        api.upload_file(
            path_or_fileobj=str(path),
            path_in_repo='gold/dataset_features_latest.parquet',
            repo_id='edyestatistica/dengue-mt-medallion',
            repo_type='dataset',
            token=token,
        )

        print(f'✅ Publicado no HF Hub: edyestatistica/dengue-mt-medallion')

    except Exception as e:
        print(f'❌ Erro HF Hub: {e}')


if __name__ == '__main__':
    print('=== Exportando Gold v5 ===')
    path = exportar_gold()

    resposta = input('\nPublicar no HF Hub? (s/n): ')
    if resposta.lower() == 's':
        publicar_hf_hub(path)