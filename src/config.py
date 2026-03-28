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
ATRASO_OPERACIONAL_DIAS = 7


def calcular_data_corte(hoje: datetime = None, atraso_dias: int = None) -> datetime:
    """
    Calcula DATA_CORTE anti-leakage para o pipeline.
    
    Baseado em:
    - Codeco et al. 2018 (InfoDengue) — SINAN delay 15 semanas
    - PLOS Neglected Tropical Diseases 2024 — 95% reporting cutoff
    - NASA POWER empirical test — dado < 7d retorna -999
    - Google Trends — semana aberta = data leakage operacional
    
    Returns:
        datetime: data máxima segura para usar como input do modelo
    """
    if hoje is None:
        hoje = datetime.now()
    if atraso_dias is None:
        atraso_dias = ATRASO_OPERACIONAL_DIAS
    
    data_corte = hoje - timedelta(days=atraso_dias)
    return data_corte