# ============================================================
# Dengue MT — Configurações Globais
# ============================================================

from pathlib import Path
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