# ============================================================
# Dengue MT — Configurações Globais
# ============================================================

from pathlib import Path
from datetime import datetime, timedelta
import os

# Identidade do pipeline
PIPELINE_VERSION = "1.0.1-dev"
DATASET_VERSION  = "v4"
MODEL_VERSION    = "lgbm_v4"

# Diretórios
ROOT_DIR     = Path(__file__).parent.parent
DATA_DIR     = ROOT_DIR / 'data'
MODELS_DIR   = ROOT_DIR / 'models'
REPORTS_DIR  = ROOT_DIR / 'reports'
METADATA_DIR = ROOT_DIR / 'metadata'

# Limiares do modelo
MAE_LIMIAR = 25.0
R2_MINIMO  = 0.75

# HF Hub
HF_REPO_ID = 'edyestatistica/dengue-mt-medallion'
HF_TOKEN   = os.environ.get('HF_TOKEN')

# CI/CD
COMMIT_SHA = os.environ.get('GITHUB_SHA', 'local')[:8]
RUN_ENV    = os.environ.get('GITHUB_ACTIONS', 'local')

# ============================================================
# CORTE TEMPORAL ANTI-LEAKAGE
# ============================================================

# Atrasos reais por fonte (baseado em literatura + testes empíricos)
# Codeco et al. 2018; PLOS NTD 2024; NASA POWER empirical test 27/03/2026
ATRASOS_FONTES = {
    'sinan':        15 * 7,   # 15 semanas — 95% notificação (Codeco et al.)
    'nasa_power':   7,        # 7 dias — dado recente retorna -999
    'google_trends':7,        # 7 dias — semana aberta = leakage
    'oni_index':    60,       # ~2 meses — atualização trimestral NOAA
    'gee_ndvi':     14,       # 14 dias — latência padrão GEE Sentinel-2
    'inmet':        2,        # 2 dias — dado quase em tempo real
}

# Corte operacional — bottleneck = fonte mais lenta em uso diário
# SINAN tem 15 semanas mas é corrigido via nowcasting
# O bottleneck operacional é NASA POWER = 7 dias
ATRASO_OPERACIONAL_DIAS = 14  # NASA POWER: dado < 7d retorna -999; usando 14d como margem segura


def calcular_data_corte(hoje: datetime = None, atraso_dias: int = None) -> datetime:
    """
    Calcula DATA_CORTE anti-leakage para o pipeline.

    Estratégia de fallback (baseada em literatura MLOps):
    1. Calcula corte normal: hoje - atraso_dias
    2. Se não conseguir calcular → usa último corte salvo no run_metadata.json
    3. Se não houver metadata anterior → usa atraso conservador de 14 dias
       (dobro do bottleneck operacional — degradação graciosa)

    Referências:
    - Codeco et al. 2018 (InfoDengue) — SINAN delay 15 semanas
    - PLOS NTD 2024 — 95% reporting cutoff Brazil
    - NASA POWER empirical test 27/03/2026
    """
    if hoje is None:
        hoje = datetime.now()
    if atraso_dias is None:
        atraso_dias = ATRASO_OPERACIONAL_DIAS

    try:
        data_corte = hoje - timedelta(days=atraso_dias)
        return data_corte

    except Exception:
        # Fallback 1: usar último corte salvo
        metadata_path = ROOT_DIR / 'metadata' / 'run_metadata.json'
        if metadata_path.exists():
            with open(metadata_path) as f:
                import json
                meta = json.load(f)
            ultimo_corte = meta.get('data_corte')
            if ultimo_corte:
                import logging
                logging.getLogger('dengue-mt.pipeline').warning(
                    f"DATA_CORTE calculado com fallback — usando último: {ultimo_corte}"
                )
                return datetime.strptime(ultimo_corte, '%Y-%m-%d')

        # Fallback 2: corte conservador dobrado (14 dias)
        import logging
        logging.getLogger('dengue-mt.pipeline').warning(
            "DATA_CORTE sem metadata anterior — usando fallback conservador: 14 dias"
        )
        return hoje - timedelta(days=14)