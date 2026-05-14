"""
===============================================================================
03_shap_analysis.py — Análise SHAP do LightGBM v5
===============================================================================
Interpretabilidade do modelo via SHAP (Lundberg & Lee, 2017).

Visualizações:
  1. Summary plot (beeswarm) — ranking + direção do efeito
  2. Bar plot — top 20 features por |SHAP| médio
  3. Dependence plots — relações não-lineares das top features
  4. SHAP temporal — importância por fase do ciclo epidêmico

Referências:
  - Lundberg & Lee (NeurIPS 2017) — SHAP original
  - Rahman et al. (Health Sci Rep 2025) — SHAP + LightGBM para dengue
  - Sebastianelli et al. (2024) — NDVI/NDWI como preditores de dengue

Saída:
  - reports/shap/fig01_shap_summary.png
  - reports/shap/fig02_shap_bar_top20.png
  - reports/shap/fig03_shap_dependence_grid.png
  - reports/shap/fig04_shap_temporal.png
  - reports/shap/shap_values.csv
===============================================================================
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import lightgbm as lgb
import shap
import matplotlib.pyplot as plt
from pathlib import Path

from config_backtesting import (
    carregar_gold, preparar_features,
    LGBM_PARAMS, TARGET, LOG_TARGET, COLS_EXCLUIR,
)

# ── Config ──
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = PROJECT_ROOT / "reports" / "shap"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Nomes legíveis para features (para os gráficos)
FEATURE_LABELS = {
    "casos_lag1": "Casos (lag 1 SE)",
    "casos_lag2": "Casos (lag 2 SE)",
    "casos_lag4": "Casos (lag 4 SE)",
    "casos_mm4": "Casos MM4",
    "casos_mm8": "Casos MM8",
    "temp_media": "Temperatura média (°C)",
    "temp_max": "Temperatura máxima (°C)",
    "temp_min": "Temperatura mínima (°C)",
    "umidade_media": "Umidade relativa (%)",
    "precipitacao": "Precipitação (mm)",
    "precipitacao_mm4": "Precipitação MM4",
    "ndvi": "NDVI",
    "ndwi": "NDWI",
    "oni_index": "ONI (El Niño/La Niña)",
    "trends_dengue": "Google Trends",
    "casos_mesmo_mes_ano_ant": "Casos mesmo mês ano anterior",
    "temp_amplitude": "Amplitude térmica (°C)",
    "semana_do_ano": "Semana do ano",
    "mes": "Mês",
    "radiacao_solar": "Radiação solar (MJ/m²)",
}


def renomear_features(cols):
    """Aplica nomes legíveis às features, mantendo original se não mapeada."""
    return [FEATURE_LABELS.get(c, c) for c in cols]

# 1. PREPARAÇÃO — TREINAR MODELO COMPLETO

def treinar_modelo_completo(df):
    """
    Treina LightGBM no dataset completo para calcular SHAP values.
    
    Nota: SHAP é calculado sobre o modelo treinado com todos os dados
    disponíveis — diferente do backtesting que usa expanding window.
    Isso é padrão na literatura (Rahman et al. 2025, Sebastianelli 2024).
    """
    # Agregar por semana
    df_agg = (
        df.groupby("data_se")
        .agg({TARGET: "sum"})
        .reset_index()
        .sort_values("data_se")
    )

    feature_cols_media = [
        c for c in df.columns
        if c not in COLS_EXCLUIR and c != TARGET
    ]
    df_features = (
        df.groupby("data_se")[feature_cols_media]
        .mean()
        .reset_index()
    )
    df_agg = df_agg.merge(df_features, on="data_se", how="left")

    feature_cols = [c for c in df_agg.columns if c not in COLS_EXCLUIR and c != TARGET]

    X = df_agg[feature_cols].values
    y = df_agg[TARGET].values

    if LOG_TARGET:
        y = np.log1p(y)

    print(f"  Treino: {X.shape[0]} semanas × {X.shape[1]} features")

    modelo = lgb.LGBMRegressor(**LGBM_PARAMS)
    modelo.fit(X, y)

    return modelo, X, y, feature_cols, df_agg

# 2. CALCULAR SHAP VALUES

def calcular_shap(modelo, X, feature_cols):
    """
    Calcula SHAP values usando TreeExplainer (exato para árvores).
    
    TreeExplainer é O(TLD²) onde T=árvores, L=folhas, D=profundidade.
    Para LightGBM é muito rápido — segundos para nosso dataset.
    
    Referência: Lundberg et al. (Nature MI 2020) — TreeSHAP
    """
    print("  Calculando SHAP values (TreeExplainer)...")
    explainer = shap.TreeExplainer(modelo)
    shap_values = explainer.shap_values(X)

    print(f"  SHAP matrix: {shap_values.shape}")
    print(f"  Base value (E[f(x)]): {explainer.expected_value:.4f}")

    # Importância média absoluta
    shap_importance = np.abs(shap_values).mean(axis=0)
    df_importance = pd.DataFrame({
        "feature": feature_cols,
        "shap_mean_abs": shap_importance,
    }).sort_values("shap_mean_abs", ascending=False)

    print(f"\n  Top 10 features por |SHAP| médio:")
    for i, row in df_importance.head(10).iterrows():
        print(f"    {row['feature']:<35} {row['shap_mean_abs']:.4f}")

    return shap_values, explainer, df_importance

# 3. VISUALIZAÇÕES

def plot_summary_beeswarm(shap_values, X, feature_cols):
    """
    Fig 1 — SHAP Summary Plot (beeswarm).
    Ranking global com direção do efeito.
    
    Cada ponto = 1 semana epidemiológica.
    Cor = valor da feature (vermelho=alto, azul=baixo).
    Posição horizontal = impacto na previsão.
    """
    fig, ax = plt.subplots(figsize=(12, 10))

    labels = renomear_features(feature_cols)

    shap.summary_plot(
        shap_values,
        features=X,
        feature_names=labels,
        max_display=20,
        show=False,
        plot_size=None,
    )

    plt.title(
        "SHAP Summary — LightGBM v5\n"
        "Importância e direção do efeito por feature",
        fontsize=14, fontweight="bold",
    )
    plt.tight_layout()

    path = REPORTS_DIR / "fig01_shap_summary.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  ✅ {path.name}")
    return path


def plot_bar_top20(df_importance, feature_cols):
    """
    Fig 2 — Bar plot das top 20 features por |SHAP| médio.
    Versão limpa para o artigo.
    """
    top20 = df_importance.head(20).copy()
    top20["label"] = renomear_features(top20["feature"].tolist())

    fig, ax = plt.subplots(figsize=(10, 8))

    # Colorir por grupo
    cores = []
    for feat in top20["feature"]:
        if "casos" in feat or "lag" in feat or "mm" in feat:
            cores.append("#E53935")   # Epidemiológico = vermelho
        elif any(k in feat for k in ["temp", "umidade", "precip", "radiacao", "amplitude"]):
            cores.append("#1E88E5")   # Climático = azul
        elif any(k in feat for k in ["ndvi", "ndwi"]):
            cores.append("#43A047")   # Vegetação = verde
        elif "oni" in feat:
            cores.append("#FB8C00")   # ENSO = laranja
        elif "trends" in feat:
            cores.append("#8E24AA")   # Infoveillance = roxo
        else:
            cores.append("#757575")   # Outros = cinza

    ax.barh(
        range(len(top20) - 1, -1, -1),
        top20["shap_mean_abs"].values,
        color=cores,
        height=0.7,
    )
    ax.set_yticks(range(len(top20) - 1, -1, -1))
    ax.set_yticklabels(top20["label"].values)
    ax.set_xlabel("|SHAP| médio (impacto na previsão)")
    ax.set_title(
        "Top 20 Features — Importância SHAP\n"
        "LightGBM v5 (Lundberg & Lee, 2017)",
        fontsize=13, fontweight="bold",
    )

    # Legenda manual
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#E53935", label="Epidemiológico"),
        Patch(facecolor="#1E88E5", label="Climático"),
        Patch(facecolor="#43A047", label="Vegetação (NDVI/NDWI)"),
        Patch(facecolor="#FB8C00", label="ENSO (ONI)"),
        Patch(facecolor="#8E24AA", label="Infoveillance"),
        Patch(facecolor="#757575", label="Outros"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=9)

    plt.tight_layout()
    path = REPORTS_DIR / "fig02_shap_bar_top20.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✅ {path.name}")
    return path


def plot_dependence_grid(shap_values, X, feature_cols, df_importance):
    """
    Fig 3 — Grid de dependence plots para as top 6 features.
    Mostra relações não-lineares capturadas pelo modelo.
    
    Referência: Rahman et al. (2025) — SHAP dependence para
    temperatura, umidade e precipitação em dengue.
    """
    top6 = df_importance.head(6)["feature"].tolist()
    labels = renomear_features(top6)

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()

    for i, (feat, label) in enumerate(zip(top6, labels)):
        idx = feature_cols.index(feat)
        ax = axes[i]

        shap.dependence_plot(
            idx,
            shap_values,
            features=X,
            feature_names=renomear_features(feature_cols),
            ax=ax,
            show=False,
        )
        ax.set_title(label, fontsize=11, fontweight="bold")

    fig.suptitle(
        "SHAP Dependence — Relações não-lineares (top 6 features)\n"
        "Cor = feature de interação automática",
        fontsize=14, fontweight="bold", y=1.02,
    )
    plt.tight_layout()

    path = REPORTS_DIR / "fig03_shap_dependence_grid.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✅ {path.name}")
    return path


def plot_shap_temporal(shap_values, df_agg, feature_cols, df_importance):
    """
    Fig 4 — Importância SHAP por fase do ciclo epidêmico.
    
    Divide o ano em 3 fases:
      - Pré-surto (out-dez): condições se formando
      - Surto (jan-mai): pico epidêmico
      - Entressafra (jun-set): casos mínimos
    
    Mostra como diferentes features dominam em cada fase.
    Original — não vi isso na literatura de dengue.
    """
    top10 = df_importance.head(10)["feature"].tolist()
    top10_idx = [feature_cols.index(f) for f in top10]

    # Criar coluna de fase
    meses = df_agg["data_se"].dt.month.values
    fases = np.where(
        (meses >= 1) & (meses <= 5), "Surto (Jan-Mai)",
        np.where(
            (meses >= 6) & (meses <= 9), "Entressafra (Jun-Set)",
            "Pré-surto (Out-Dez)"
        )
    )

    # SHAP médio por fase para top 10
    dados_fase = []
    for fase in ["Pré-surto (Out-Dez)", "Surto (Jan-Mai)", "Entressafra (Jun-Set)"]:
        mask = fases == fase
        for feat, idx in zip(top10, top10_idx):
            shap_medio = np.abs(shap_values[mask, idx]).mean()
            dados_fase.append({
                "fase": fase,
                "feature": feat,
                "label": FEATURE_LABELS.get(feat, feat),
                "shap_medio": shap_medio,
            })

    df_fase = pd.DataFrame(dados_fase)

    # Plot grouped bar
    fig, ax = plt.subplots(figsize=(14, 7))

    fases_ordem = ["Pré-surto (Out-Dez)", "Surto (Jan-Mai)", "Entressafra (Jun-Set)"]
    cores_fase = {"Pré-surto (Out-Dez)": "#FF9800", "Surto (Jan-Mai)": "#F44336", "Entressafra (Jun-Set)": "#4CAF50"}
    n_features = len(top10)
    bar_width = 0.25
    x = np.arange(n_features)

    for i, fase in enumerate(fases_ordem):
        df_f = df_fase[df_fase["fase"] == fase].set_index("feature").loc[top10]
        ax.bar(
            x + i * bar_width,
            df_f["shap_medio"].values,
            width=bar_width,
            color=cores_fase[fase],
            label=fase,
            alpha=0.85,
        )

    labels = renomear_features(top10)
    ax.set_xticks(x + bar_width)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
    ax.set_ylabel("|SHAP| médio")
    ax.set_title(
        "Importância SHAP por fase do ciclo epidêmico\n"
        "Como diferentes features dominam em cada período",
        fontsize=13, fontweight="bold",
    )
    ax.legend(fontsize=10)
    plt.tight_layout()

    path = REPORTS_DIR / "fig04_shap_temporal.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✅ {path.name}")
    return path

# 4. MAIN

def main():
    print("=" * 60)
    print("ANÁLISE SHAP — LightGBM v5")
    print("Lundberg & Lee (NeurIPS 2017)")
    print("=" * 60)

    # 1. Carregar e treinar
    print("\n▶ Carregando Gold e treinando modelo completo...")
    df = carregar_gold()
    modelo, X, y, feature_cols, df_agg = treinar_modelo_completo(df)

    # 2. Calcular SHAP
    print("\n▶ Calculando SHAP values...")
    shap_values, explainer, df_importance = calcular_shap(modelo, X, feature_cols)

    # 3. Visualizações
    print("\n▶ Gerando visualizações...")
    plot_summary_beeswarm(shap_values, X, feature_cols)
    plot_bar_top20(df_importance, feature_cols)
    plot_dependence_grid(shap_values, X, feature_cols, df_importance)
    plot_shap_temporal(shap_values, df_agg, feature_cols, df_importance)

    # 4. Salvar dados
    df_importance.to_csv(REPORTS_DIR / "shap_values.csv", index=False)
    print(f"\n✅ {REPORTS_DIR / 'shap_values.csv'}")

    # Resumo
    print(f"\n{'='*60}")
    print("RESUMO")
    print(f"{'='*60}")
    print(f"  Features analisadas: {len(feature_cols)}")
    print(f"  Semanas avaliadas: {X.shape[0]}")
    print(f"\n  Top 5 features por impacto:")
    for _, row in df_importance.head(5).iterrows():
        label = FEATURE_LABELS.get(row["feature"], row["feature"])
        print(f"    {label:<35} |SHAP|={row['shap_mean_abs']:.4f}")
    print(f"\n  Figuras em: {REPORTS_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()