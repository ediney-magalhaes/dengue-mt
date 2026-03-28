# ============================================================
# Dengue MT — Observabilidade e Logging Estruturado
# ============================================================

import logging
import time
from pathlib import Path
from src.config import REPORTS_DIR

# Garantir que o diretório existe
REPORTS_DIR.mkdir(exist_ok=True)

# Logger principal
obs_logger = logging.getLogger('dengue-mt.pipeline')
obs_logger.setLevel(logging.INFO)
obs_logger.propagate = False

# Handler arquivo
_fh = logging.FileHandler(REPORTS_DIR / 'pipeline.log', encoding='utf-8')
_fh.setLevel(logging.INFO)
_fh.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s'))
obs_logger.addHandler(_fh)

# Handler terminal
_sh = logging.StreamHandler()
_sh.setLevel(logging.INFO)
_sh.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s'))
obs_logger.addHandler(_sh)


def log_etapa(nome: str, inicio: float, resultado: dict):
    """Loga início/fim de etapa com duração e resultado."""
    duracao = round(time.time() - inicio, 2)
    status  = resultado.get('status', '?')
    obs_logger.info(
        f"ETAPA={nome} | DURACAO={duracao}s | STATUS={status} | DETALHES={resultado}"
    )


def log_metricas(mae: float, r2: float, smape: float = None):
    """Loga métricas do modelo."""
    obs_logger.info(
        f"METRICAS | MAE={mae} | R2={r2} | sMAPE={smape}"
    )


def log_nulos(df, features: list):
    """Loga % de nulos por feature crítica."""
    for feat in features:
        if feat in df.columns:
            pct = round(df[feat].isnull().mean() * 100, 2)
            obs_logger.info(f"NULOS | feature={feat} | pct={pct}%")


def log_pipeline_start(version: str, dataset: str, model: str, commit: str):
    obs_logger.info("=" * 60)
    obs_logger.info(
        f"PIPELINE_START | version={version} | dataset={dataset} "
        f"| model={model} | commit={commit}"
    )
    obs_logger.info("=" * 60)


def log_pipeline_end(timestamp: str, retreino: str):
    obs_logger.info("=" * 60)
    obs_logger.info(
        f"PIPELINE_END | timestamp={timestamp} | retreino={retreino}"
    )
    obs_logger.info("=" * 60)