"""
===============================================================================
config_intervalos.py — Configurações para Intervalos de Predição (CQR)
===============================================================================
Compartilha paths e parâmetros com config_backtesting.py.
Adiciona configurações específicas do Conformalized Quantile Regression.

Referências:
  - Romano, Patterson & Candès (NeurIPS 2019) — CQR
  - Cordier et al. (COPA/PMLR 2023) — MAPIE library
  - PMC/medRxiv 2025 — Conformal prediction para dengue no Brasil
===============================================================================
"""

from config_backtesting import (
    PROJECT_ROOT, GOLD_PATH, MUNICIPIOS, COLS_EXCLUIR,
    LGBM_PARAMS, TARGET, LOG_TARGET, TESTE_INICIO,
    carregar_gold, preparar_features, calcular_metricas,
)
from pathlib import Path

# ── Diretório de saída ──
REPORTS_DIR = PROJECT_ROOT / "reports" / "intervalos"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Configurações do CQR ──
# Níveis de confiança para os intervalos
ALPHA_LEVELS = [0.10, 0.20]  # 90% e 80% de cobertura

# Fração dos dados de teste usada para calibração do conformal
# Romano et al. (2019) recomenda 20-30% do teste para calibração
CALIBRATION_FRACTION = 0.25

# Quantis para regressão quantílica (simétricos em torno da mediana)
# alpha=0.10 → quantis 0.05 e 0.95
# alpha=0.20 → quantis 0.10 e 0.90
def get_quantiles(alpha):
    """Retorna (lower_quantile, upper_quantile) para dado alpha."""
    return alpha / 2, 1 - alpha / 2

# ── Parâmetros LightGBM para regressão quantílica ──
def get_lgbm_quantile_params(quantile):
    """
    Retorna parâmetros LightGBM para regressão quantílica.
    
    LightGBM suporta nativamente objective='quantile' com
    parâmetro alpha definindo o quantil desejado.
    Referência: Ke et al. (2017) — LightGBM, Seção 2.
    """
    params = LGBM_PARAMS.copy()
    params["objective"] = "quantile"
    params["alpha"] = quantile
    # Remover metric MAE — não se aplica a quantile loss
    params["metric"] = "quantile"
    return params