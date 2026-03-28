# ============================================================
# Dengue MT — Task: Publicação no HF Hub
# ============================================================

from prefect import task, get_run_logger
from datetime import datetime, date
from src.config import (
    DATA_DIR, PIPELINE_VERSION, DATASET_VERSION,
    HF_REPO_ID, COMMIT_SHA
)
import pandas as pd
import json
import os
import hashlib


@task(name="publicar_gold_hf")
def publicar_gold_versionado():
    """Salva Gold no HF Hub com data + latest pointer + metadata."""
    logger = get_run_logger()
    logger.info("Publicando Gold no HF Hub...")

    try:
        from huggingface_hub import HfApi
        import polars as pl
        import lightgbm as lgb_lib
        import polars as pl_lib

        gold_path = DATA_DIR / 'gold' / 'dataset_features_v4.parquet'
        if not gold_path.exists():
            logger.warning("Gold não encontrado — pulando publicação")
            return {'status': 'pendente'}

        api  = HfApi()
        hoje = date.today().isoformat()

        # Carregar dataset para metadados
        df_meta = pl.read_parquet(gold_path)

        # Hash MD5
        with open(gold_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()

        # Versões das libs
        libs = {
            'polars':    pl_lib.__version__,
            'lightgbm':  lgb_lib.__version__,
            'pandas':    pd.__version__,
        }

        # Metadata do snapshot
        metadata = {
            'dataset_version':  DATASET_VERSION,
            'pipeline_version': PIPELINE_VERSION,
            'commit_sha':       os.environ.get('GITHUB_SHA', 'local')[:8],
            'snapshot_date':    hoje,
            'start_date':       str(df_meta['data'].min()),
            'end_date':         str(df_meta['data'].max()),
            'n_registros':      len(df_meta),
            'n_features':       len(df_meta.columns),
            'features': list(df_meta.columns),
            'file_hash_md5':    file_hash,
            'libs':             libs,
            'timestamp':        datetime.now().isoformat()
        }

        # Salvar metadata local
        metadata_path = gold_path.parent / f'dataset_features_v4_{hoje}.metadata.json'
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        # 1. Upload snapshot datado
        nome_datado = f'gold/dataset_features_v4_{hoje}.parquet'
        api.upload_file(
            path_or_fileobj=str(gold_path),
            path_in_repo=nome_datado,
            repo_id=HF_REPO_ID,
            repo_type='dataset'
        )
        logger.info(f"Snapshot salvo: {nome_datado}")

        # 2. Upload metadata
        nome_metadata = f'gold/dataset_features_v4_{hoje}.metadata.json'
        api.upload_file(
            path_or_fileobj=str(metadata_path),
            path_in_repo=nome_metadata,
            repo_id=HF_REPO_ID,
            repo_type='dataset'
        )
        logger.info(f"Metadata salvo: {nome_metadata}")

        # 3. Upload latest
        api.upload_file(
            path_or_fileobj=str(gold_path),
            path_in_repo='gold/dataset_features_v4_latest.parquet',
            repo_id=HF_REPO_ID,
            repo_type='dataset'
        )
        logger.info("Ponteiro latest atualizado")

        return {
            'status':      'ok',
            'snapshot':    nome_datado,
            'metadata':    nome_metadata,
            'latest':      'gold/dataset_features_v4_latest.parquet',
            'n_registros': len(df_meta),
            'file_hash':   file_hash
        }

    except Exception as e:
        logger.error(f"Erro ao publicar Gold: {e}")
        return {'status': 'erro', 'motivo': str(e)}