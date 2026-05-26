"""
atualizar_modis.py — Atualização mensal do Bronze MODIS
Roda via GitHub Actions (cron mensal) para manter o MODIS
atualizado no HF Hub sem impactar o pipeline semanal.

Fluxo:
  1. Remove Bronze local para forçar re-ingestão
  2. Chama ingerir_bronze() via AppEEARS NASA
  3. Publica Bronze atualizado no HF Hub

Uso:
  python scripts/atualizar_modis.py
  Requer: MODIS_USUARIO, MODIS_SENHA, HF_TOKEN como env vars
"""

import os
import sys
import logging
from pathlib import Path

# Adiciona raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DATA_DIR, HF_REPO_ID, HF_TOKEN
from src.ingestion.modis import ingerir_bronze, BRONZE_DIR

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger('dengue-mt.modis-mensal')


def main():
    usuario = os.environ.get('MODIS_USUARIO')
    senha = os.environ.get('MODIS_SENHA')

    if not usuario or not senha:
        logger.error('MODIS_USUARIO e MODIS_SENHA não configurados')
        sys.exit(1)

    if not HF_TOKEN:
        logger.error('HF_TOKEN não configurado')
        sys.exit(1)

    # --- 1. Remove Bronze local para forçar re-ingestão ---
    path_bronze = BRONZE_DIR / 'modis_ndvi_evi_latest.parquet'
    if path_bronze.exists():
        logger.info(f'Removendo Bronze existente para forçar atualização: {path_bronze.name}')
        path_bronze.unlink()

    # --- 2. Ingestão via AppEEARS (timeout interno: 60 min/tarefa) ---
    logger.info('Iniciando ingestão MODIS via AppEEARS...')
    arquivos = ingerir_bronze(usuario, senha, ano_inicio=2018)

    if not arquivos:
        logger.error('Ingestão MODIS falhou — nenhum arquivo gerado')
        sys.exit(1)

    # Valida que o arquivo foi criado
    if not path_bronze.exists():
        logger.error(f'Arquivo Bronze não encontrado: {path_bronze}')
        sys.exit(1)

    import pandas as pd
    df = pd.read_parquet(path_bronze)
    logger.info(f'Bronze MODIS atualizado: {len(df)} registros')
    logger.info(f'Período: {pd.to_datetime(df["Date"]).min()} → {pd.to_datetime(df["Date"]).max()}')

    # --- 3. Publica no HF Hub ---
    logger.info('Publicando Bronze MODIS no HF Hub...')
    try:
        from huggingface_hub import HfApi
        api = HfApi(token=HF_TOKEN)
        api.upload_file(
            path_or_fileobj=str(path_bronze),
            path_in_repo='bronze/modis/modis_ndvi_evi_latest.parquet',
            repo_id=HF_REPO_ID,
            repo_type='dataset',
            commit_message=f'modis: atualização mensal ({len(df)} registros)'
        )
        logger.info('✅ Bronze MODIS publicado no HF Hub com sucesso!')
    except Exception as e:
        logger.error(f'Falha ao publicar no HF Hub: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()