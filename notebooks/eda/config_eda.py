"""
===============================================================================
config_eda.py — Configurações compartilhadas para EDA
===============================================================================
Projeto: Predição de Dengue — Cuiabá e Várzea Grande (MT)
Autor: Ediney Magalhães — IFMT 2026
Dataset: Gold v5 (54 features × 824+ registros × 2 municípios)
===============================================================================
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# PATHS
# ============================================================
# Raiz do projeto (2 níveis acima de notebooks/eda/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GOLD_PATH = PROJECT_ROOT / 'data' / 'gold' / 'dataset_features_v5_latest.parquet'
OUTPUT_DIR = PROJECT_ROOT / 'reports' / 'eda'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# MUNICÍPIOS
# ============================================================
MUNICIPIOS = {
    5103403: 'Cuiabá',
    5108402: 'Várzea Grande',
}

CORES = {
    5103403: '#1f77b4',   # Cuiabá — azul
    5108402: '#d62728',   # Várzea Grande — vermelho
}

# ============================================================
# GRUPOS DE FEATURES
# ============================================================
FEATURES_TARGET = ['casos_confirmados', 'casos_estimados', 'incidencia_100k']

FEATURES_EPIDEMIO = [
    'rt_index_lag1', 'nivel_alerta_lag1', 'receptivo_lag1',
    'transmissao_lag1', 'prob_rt_maior_1_lag1', 'notif_acum_ano_lag1',
]

FEATURES_TEMPERATURA = [
    'temp_media_lag1', 'temp_media_lag2', 'temp_media_lag3', 'temp_media_lag4',
    'temp_max_lag1', 'temp_max_lag2', 'temp_min_lag1', 'temp_min_lag2',
]

FEATURES_PRECIP_UMIDADE = [
    'precip_lag1', 'precip_lag2', 'precip_lag3', 'precip_lag4',
    'umidade_lag1', 'umidade_lag2',
    'radiacao_lag1', 'radiacao_lag2',
    'umidade_nasa_lag1', 'umidade_nasa_lag2',
]

FEATURES_MEDIAS_MOVEIS = [
    'temp_media_mm4', 'temp_media_mm8',
    'precip_acum4', 'precip_acum8',
    'casos_mm4',
]

FEATURES_ONI = [
    'oni_lag4', 'oni_lag6', 'oni_lag8',
    'fase_enso_num_lag4', 'fase_enso_num_lag6',
]

FEATURES_MODIS = [
    'ndvi_lag2', 'ndvi_lag3', 'ndvi_lag4',
    'evi_lag2', 'evi_lag3',
]

FEATURES_TRENDS = ['trends_lag1', 'trends_lag2']

FEATURES_AUTOREGRESSIVO = [
    'casos_lag1', 'casos_lag2', 'casos_lag3', 'casos_lag4',
]

COLS_METADATA = [
    'municipio_id', 'municipio_nome', 'data_se',
    'semana_epidemiologica', 'dbt_updated_at', 'populacao',
]

# ============================================================
# ESTILO MATPLOTLIB — Publicação científica
# ============================================================
def aplicar_estilo():
    """Aplica estilo consistente para todas as figuras da EDA."""
    plt.rcParams.update({
        'figure.dpi': 150,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'font.size': 11,
        'axes.titlesize': 13,
        'axes.labelsize': 11,
        'xtick.labelsize': 9,
        'ytick.labelsize': 9,
        'legend.fontsize': 9,
        'figure.facecolor': 'white',
        'axes.facecolor': 'white',
        'axes.grid': True,
        'grid.alpha': 0.3,
        'axes.spines.top': False,
        'axes.spines.right': False,
    })


# ============================================================
# LOADER
# ============================================================
def carregar_gold():
    """Carrega Gold v5 do Parquet local."""
    if not GOLD_PATH.exists():
        raise FileNotFoundError(
            f"Gold não encontrado em {GOLD_PATH}\n"
            f"Rode 'python scripts/exportar_gold.py' primeiro."
        )

    df = pd.read_parquet(GOLD_PATH)
    df['data_se'] = pd.to_datetime(df['data_se'])
    df = df.sort_values(['municipio_id', 'data_se']).reset_index(drop=True)

    print(f"Gold carregado: {df.shape[0]} registros × {df.shape[1]} colunas")
    print(f"Período: {df['data_se'].min().date()} → {df['data_se'].max().date()}")
    for mun_id, nome in MUNICIPIOS.items():
        n = len(df[df['municipio_id'] == mun_id])
        print(f"  {nome}: {n} semanas epidemiológicas")

    return df


def salvar_figura(fig, nome_arquivo):
    """Salva figura no diretório reports/eda/ com log."""
    path = OUTPUT_DIR / nome_arquivo
    fig.savefig(path)
    print(f"  ✅ Salvo: {path.relative_to(PROJECT_ROOT)}")
    plt.close(fig)
    return path