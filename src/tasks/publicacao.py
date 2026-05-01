# ============================================================
# Dengue MT — Task: Publicação no HF Hub v2.0
# ============================================================
# Responsabilidades:
#   1. publicar_bronze_incremental() — Bronze completo com SHA256
#   2. publicar_gold_versionado()    — Gold snapshot datado + latest
# Rastreabilidade: snapshot_date + commit_sha + sha256 + manifesto
# ============================================================
from prefect import task, get_run_logger
from datetime import datetime, date
from src.config import (
    DATA_DIR, PIPELINE_VERSION, DATASET_VERSION,
    HF_REPO_ID, HF_TOKEN, COMMIT_SHA,
    GOLD_LATEST_PATH, HF_GOLD_LATEST
)
import hashlib
import pandas as pd
import json
import os


# ============================================================
# UTILITÁRIOS
# ============================================================

def _sha256(path) -> str:
    """Calcula SHA256 de um arquivo local."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hf_sha256_index(api, path_in_repo: str) -> dict:
    """
    Retorna dicionário {path_hf: sha256} para todos os arquivos
    sob path_in_repo no HF Hub. Retorna {} se falhar.
    """
    try:
        items = api.list_repo_tree(
            repo_id=HF_REPO_ID,
            repo_type='dataset',
            path_in_repo=path_in_repo,
            recursive=True,
            token=HF_TOKEN,
        )
        return {
            item.path: item.lfs.sha256
            for item in items
            if hasattr(item, 'lfs') and item.lfs
        }
    except Exception:
        return {}


# ============================================================
# TASK 1 — BRONZE
# ============================================================

@task(name="publicar_bronze_hf")
def publicar_bronze_incremental():
    """
    Publica Bronze no HF Hub — incremental por SHA256.
    Só publica arquivo se conteúdo mudou desde último upload.
    Gera manifesto de rastreabilidade por execução.
    """
    logger = get_run_logger()
    logger.info("Publicando Bronze no HF Hub — verificação incremental...")

    try:
        from huggingface_hub import HfApi
        import tempfile

        api        = HfApi()
        bronze_dir = DATA_DIR / 'bronze'
        hoje       = date.today().isoformat()

        # Índice SHA256 atual no HF Hub
        logger.info("Buscando índice SHA256 do HF Hub...")
        hf_sha256 = _hf_sha256_index(api, 'bronze')
        if not hf_sha256:
            logger.warning("Índice HF Hub vazio ou inacessível — publicando todos os arquivos")

        arquivos   = sorted(bronze_dir.rglob('*.parquet'))
        publicados = []
        skipped    = []
        falhas     = []
        manifesto_arquivos = {}

        for path_local in arquivos:
            path_hf = 'bronze/' + '/'.join(
                path_local.relative_to(bronze_dir).parts
            )

            sha256_local = _sha256(path_local)
            sha256_hf    = hf_sha256.get(path_hf)

            entrada_manifesto = {
                'sha256':      sha256_local,
                'size_bytes':  path_local.stat().st_size,
            }

            # Skip se SHA256 igual
            if sha256_hf and sha256_hf == sha256_local:
                logger.info(f"SKIP {path_hf} — sem alteração")
                skipped.append(path_hf)
                entrada_manifesto['status'] = 'skipped'
                manifesto_arquivos[path_hf] = entrada_manifesto
                continue

            # Publica
            try:
                api.upload_file(
                    path_or_fileobj=str(path_local),
                    path_in_repo=path_hf,
                    repo_id=HF_REPO_ID,
                    repo_type='dataset',
                    token=HF_TOKEN,
                )
                logger.info(f"OK {path_hf}")
                publicados.append(path_hf)
                entrada_manifesto['status'] = 'publicado'
            except Exception as e:
                logger.error(f"ERRO {path_hf}: {e}")
                falhas.append(path_hf)
                entrada_manifesto['status'] = 'erro'
                entrada_manifesto['motivo'] = str(e)

            manifesto_arquivos[path_hf] = entrada_manifesto

        # Manifesto de rastreabilidade
        manifesto = {
            'snapshot_date':    hoje,
            'commit_sha':       COMMIT_SHA,
            'pipeline_version': PIPELINE_VERSION,
            'timestamp':        datetime.now().isoformat(),
            'resumo': {
                'publicados': len(publicados),
                'skipped':    len(skipped),
                'falhas':     len(falhas),
                'total':      len(arquivos),
            },
            'arquivos': manifesto_arquivos,
        }

        # Salva e publica manifesto
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json',
            delete=False, encoding='utf-8'
        ) as tmp:
            json.dump(manifesto, tmp, ensure_ascii=False, indent=2)
            tmp_path = tmp.name

        api.upload_file(
            path_or_fileobj=tmp_path,
            path_in_repo='bronze/bronze_manifest_latest.json',
            repo_id=HF_REPO_ID,
            repo_type='dataset',
            token=HF_TOKEN,
        )
        logger.info("Manifesto Bronze publicado")

        logger.info(
            f"Bronze HF Hub — publicados: {len(publicados)} "
            f"| skipped: {len(skipped)} | falhas: {len(falhas)}"
        )

        return {
            'status':     'ok' if not falhas else 'parcial',
            'publicados': len(publicados),
            'skipped':    len(skipped),
            'falhas':     len(falhas),
            'fonte':      'bronze_hf',
        }

    except Exception as e:
        logger.error(f"Erro ao publicar Bronze: {e}")
        return {'status': 'erro', 'motivo': str(e)}


# ============================================================
# TASK 2 — GOLD
# ============================================================

@task(name="publicar_gold_hf")
def publicar_gold_versionado():
    """
    Publica Gold no HF Hub — snapshot datado + ponteiro latest.
    Rastreabilidade: snapshot_date + commit_sha + sha256 + metadata JSON.
    """
    logger = get_run_logger()
    logger.info("Publicando Gold no HF Hub...")

    try:
        from huggingface_hub import HfApi

        gold_path = GOLD_LATEST_PATH
        if not gold_path.exists():
            logger.warning("Gold não encontrado — pulando publicação")
            return {'status': 'pendente'}

        api  = HfApi()
        hoje = date.today().isoformat()

        # Metadados
        df_meta    = pd.read_parquet(gold_path)
        sha256_gold = _sha256(gold_path)

        metadata = {
            'dataset_version':  DATASET_VERSION,
            'pipeline_version': PIPELINE_VERSION,
            'commit_sha':       COMMIT_SHA,
            'snapshot_date':    hoje,
            'timestamp':        datetime.now().isoformat(),
            'start_date':       str(df_meta['data_se'].min()),
            'end_date':         str(df_meta['data_se'].max()),
            'n_registros':      len(df_meta),
            'n_features':       len(df_meta.columns),
            'municipios':       sorted(df_meta['municipio_id'].unique().tolist()),
            'sha256':           sha256_gold,
        }

        # Salva metadata local
        metadata_path = DATA_DIR / 'gold' / f'dataset_features_{DATASET_VERSION}_{hoje}.metadata.json'
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        # 1. Snapshot datado
        nome_datado = f'gold/dataset_features_{DATASET_VERSION}_{hoje}.parquet'
        api.upload_file(
            path_or_fileobj=str(gold_path),
            path_in_repo=nome_datado,
            repo_id=HF_REPO_ID,
            repo_type='dataset',
            token=HF_TOKEN,
        )
        logger.info(f"Snapshot salvo: {nome_datado}")

        # 2. Metadata
        nome_metadata = f'gold/dataset_features_{DATASET_VERSION}_{hoje}.metadata.json'
        api.upload_file(
            path_or_fileobj=str(metadata_path),
            path_in_repo=nome_metadata,
            repo_id=HF_REPO_ID,
            repo_type='dataset',
            token=HF_TOKEN,
        )
        logger.info(f"Metadata salvo: {nome_metadata}")

        # 3. Ponteiro latest
        api.upload_file(
            path_or_fileobj=str(gold_path),
            path_in_repo=HF_GOLD_LATEST,
            repo_id=HF_REPO_ID,
            repo_type='dataset',
            token=HF_TOKEN,
        )
        logger.info("Ponteiro latest atualizado")

        return {
            'status':      'ok',
            'snapshot':    nome_datado,
            'metadata':    nome_metadata,
            'latest':      HF_GOLD_LATEST,
            'n_registros': len(df_meta),
            'sha256':      sha256_gold,
        }

    except Exception as e:
        logger.error(f"Erro ao publicar Gold: {e}")
        return {'status': 'erro', 'motivo': str(e)}
    
# ============================================================
# TASK 3 — PREVISÃO POR BAIRRO (IDW)
# ============================================================

@task(name="publicar_previsao_bairros_hf")
def publicar_previsao_bairros():
    """
    Gera previsão municipal SE+1→SE+4 via LightGBM,
    distribui pelos 143 bairros via IDW mass-preserving
    e publica GeoJSON no HF Hub.
    Executa após publicar_gold_versionado() — depende do Gold atualizado.
    """
    logger = get_run_logger()
    logger.info("Gerando previsão por bairro via IDW...")

    try:
        import subprocess
        from pathlib import Path

        script = Path(__file__).resolve().parents[2] / 'scripts' / 'gerar_previsao_bairros.py'

        resultado = subprocess.run(
            ['python', str(script)],
            capture_output=True,
            text=True,
            timeout=120
        )

        if resultado.returncode != 0:
            logger.error(f"gerar_previsao_bairros falhou: {resultado.stderr}")
            return {'status': 'erro', 'motivo': resultado.stderr}

        logger.info(resultado.stdout)
        return {
            'status':  'ok',
            'fonte':   'previsao_bairros_idw',
        }

    except Exception as e:
        logger.error(f"Erro ao gerar previsão por bairro: {e}")
        return {'status': 'erro', 'motivo': str(e)}