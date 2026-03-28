# ============================================================
# Dengue MT — Cache e Fallback de APIs Externas
# ============================================================
# Estratégia: se API falhar → usar último dado válido local
# Referência: MLOps best practices — graceful degradation
# ============================================================

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from src.config import DATA_DIR

logger = logging.getLogger('dengue-mt.pipeline')

# Pasta de cache
CACHE_DIR = DATA_DIR / 'cache'
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Validade do cache por fonte (em dias)
CACHE_VALIDADE = {
    'nasa_power':     7,   # atualização diária mas latência 7d
    'google_trends':  7,   # semana epidemiológica fechada
    'oni_index':      30,  # atualização trimestral NOAA
    'gee_ndvi':       30,  # latência Sentinel-2 ~14 dias
    'cnes':           90,  # cadastro muda pouco
}

# Arquivo de metadata do cache
CACHE_METADATA_PATH = CACHE_DIR / 'cache_metadata.json'


def _carregar_metadata() -> dict:
    """Carrega metadata do cache (quando cada fonte foi atualizada)."""
    if CACHE_METADATA_PATH.exists():
        with open(CACHE_METADATA_PATH) as f:
            return json.load(f)
    return {}


def _salvar_metadata(metadata: dict):
    """Salva metadata do cache."""
    with open(CACHE_METADATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def cache_valido(fonte: str) -> bool:
    """Verifica se o cache de uma fonte ainda é válido."""
    metadata = _carregar_metadata()
    if fonte not in metadata:
        return False

    ultima_atualizacao = datetime.fromisoformat(metadata[fonte]['atualizado_em'])
    validade_dias = CACHE_VALIDADE.get(fonte, 7)
    expirado = datetime.now() - ultima_atualizacao > timedelta(days=validade_dias)

    if expirado:
        logger.warning(f"CACHE_EXPIRADO | fonte={fonte} | ultima={ultima_atualizacao.date()}")
    return not expirado


def salvar_cache(fonte: str, df: pd.DataFrame, extra: dict = None):
    """Salva DataFrame no cache local após ingestão bem-sucedida."""
    cache_path = CACHE_DIR / f'{fonte}_latest.parquet'
    df.to_parquet(cache_path, index=False)

    metadata = _carregar_metadata()
    metadata[fonte] = {
        'atualizado_em': datetime.now().isoformat(),
        'n_registros':   len(df),
        'colunas':       list(df.columns),
    }
    if extra:
        metadata[fonte].update(extra)

    _salvar_metadata(metadata)
    logger.info(f"CACHE_SALVO | fonte={fonte} | registros={len(df)}")


def carregar_cache(fonte: str) -> pd.DataFrame | None:
    """
    Carrega cache local como fallback quando API falha.
    Retorna None se cache não existir.
    """
    cache_path = CACHE_DIR / f'{fonte}_latest.parquet'
    if not cache_path.exists():
        logger.error(f"CACHE_INEXISTENTE | fonte={fonte} | sem fallback disponível!")
        return None

    metadata = _carregar_metadata()
    info = metadata.get(fonte, {})
    ultima = info.get('atualizado_em', 'desconhecido')

    logger.warning(
        f"FALLBACK_ATIVO | fonte={fonte} | "
        f"usando cache de {ultima} | "
        f"registros={info.get('n_registros', '?')}"
    )

    df = pd.read_parquet(cache_path)
    return df


def status_cache() -> dict:
    """Retorna status de todas as fontes no cache — para o run_metadata."""
    metadata = _carregar_metadata()
    status = {}
    for fonte, info in metadata.items():
        valido = cache_valido(fonte)
        status[fonte] = {
            'valido':        valido,
            'atualizado_em': info.get('atualizado_em'),
            'n_registros':   info.get('n_registros'),
        }
    return status