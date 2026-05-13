"""
===============================================================================
02_intervalos_confianca.py — Intervalos de Predição via CQR
===============================================================================
Implementa Conformalized Quantile Regression (CQR) sobre o LightGBM v5
para gerar intervalos de predição com garantia de cobertura.

Abordagem:
  1. Treina 3 modelos LightGBM por passo: quantil inferior, mediana, superior
  2. Calibra os intervalos com conformal prediction (split conformal)
  3. Avalia cobertura empírica e largura dos intervalos
  4. Compara com intervalo fixo (bootstrap dos resíduos) como baseline

Referências:
  - Romano, Patterson & Candès (NeurIPS 2019) — CQR original
  - Cordier et al. (COPA/PMLR 2023) — MAPIE library
  - PMC 2025 — Conformal prediction para dengue no Brasil
  - Manna et al. (2025) — Residual-based conformal for LightGBM

Saída:
  - reports/intervalos/fig01_serie_com_intervalos.png
  - reports/intervalos/fig02_cobertura_por_periodo.png
  - reports/intervalos/fig03_largura_adaptativa.png
  - reports/intervalos/metricas_intervalos.csv
  - reports/intervalos/previsoes_com_intervalos.csv
===============================================================================
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import lightgbm as lgb
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from tqdm import tqdm

from config_intervalos import (
    carregar_gold, preparar_features, calcular_metricas,
    LGBM_PARAMS, TARGET, LOG_TARGET, TESTE_INICIO,
    COLS_EXCLUIR, MUNICIPIOS, REPORTS_DIR,
    ALPHA_LEVELS, CALIBRATION_FRACTION,
    get_quantiles, get_lgbm_quantile_params,
)

# 1. PREPARAÇÃO DOS DADOS

def preparar_dados(df):
    """
    Agrega Cuiabá + Várzea Grande por semana epidemiológica.
    Mesmo procedimento do backtesting para manter comparabilidade.
    """
    # Agregar por semana (soma dos dois municípios)
    df_agg = (
        df.groupby("data_se")
        .agg({TARGET: "sum"})
        .reset_index()
        .sort_values("data_se")
    )

    # Recalcular features agregadas — usar média para clima, soma para casos
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

    print(f"  Dados agregados: {len(df_agg)} semanas")
    print(f"  Período: {df_agg['data_se'].min().date()} → {df_agg['data_se'].max().date()}")

    return df_agg

# 2. CQR — CONFORMALIZED QUANTILE REGRESSION

def executar_cqr(df_agg, feature_cols, alpha=0.10):
    """
    Executa Conformalized Quantile Regression com expanding window.

    Etapas por passo t:
      1. Treina 3 modelos LightGBM (quantil lower, mediana, upper)
         com dados de 2018 até t-1
      2. Gera previsão pontual (mediana) e intervalo bruto (lower, upper)
      3. Acumula resíduos de calibração para ajuste conformal

    Após a passagem expanding, aplica calibração conformal global:
      - Calcula nonconformity scores nos dados de calibração
      - Ajusta os limites do intervalo com o quantil (1-alpha) dos scores

    Parâmetros:
        df_agg: DataFrame agregado com features + target
        feature_cols: lista de colunas preditoras
        alpha: nível de significância (0.10 = intervalo de 90%)

    Retorna:
        DataFrame com colunas: data_se, y_real, y_pred, lower, upper,
        lower_calibrado, upper_calibrado
    """
    q_lower, q_upper = get_quantiles(alpha)

    # Parâmetros dos 3 modelos quantílicos
    params_lower = get_lgbm_quantile_params(q_lower)
    params_median = get_lgbm_quantile_params(0.50)
    params_upper = get_lgbm_quantile_params(q_upper)

    # Split treino/teste por ano
    mask_teste = df_agg["data_se"].dt.year >= TESTE_INICIO
    datas_teste = df_agg.loc[mask_teste, "data_se"].values
    n_teste = len(datas_teste)

    # Split teste em calibração + avaliação
    n_calib = int(n_teste * CALIBRATION_FRACTION)
    datas_calib = datas_teste[:n_calib]
    datas_eval = datas_teste[n_calib:]

    print(f"\n  Alpha={alpha} → Intervalo de {100*(1-alpha):.0f}%")
    print(f"  Quantis: [{q_lower}, {q_upper}]")
    print(f"  Teste: {n_teste} semanas (calib={n_calib}, eval={n_teste - n_calib})")

    resultados = []

    for data_pred in tqdm(datas_teste, desc=f"CQR α={alpha}", leave=False):
        mask_treino = df_agg["data_se"] < data_pred
        mask_pred = df_agg["data_se"] == data_pred

        X_treino = df_agg.loc[mask_treino, feature_cols].values
        X_pred = df_agg.loc[mask_pred, feature_cols].values
        y_real = df_agg.loc[mask_pred, TARGET].values[0]

        y_treino = df_agg.loc[mask_treino, TARGET].values

        if LOG_TARGET:
            y_treino_log = np.log1p(y_treino)
        else:
            y_treino_log = y_treino

        if len(X_treino) < 52:
            continue

        # Treinar 3 modelos quantílicos
        modelo_lower = lgb.LGBMRegressor(**params_lower)
        modelo_median = lgb.LGBMRegressor(**params_median)
        modelo_upper = lgb.LGBMRegressor(**params_upper)

        modelo_lower.fit(X_treino, y_treino_log)
        modelo_median.fit(X_treino, y_treino_log)
        modelo_upper.fit(X_treino, y_treino_log)

        # Previsões
        pred_lower = modelo_lower.predict(X_pred)[0]
        pred_median = modelo_median.predict(X_pred)[0]
        pred_upper = modelo_upper.predict(X_pred)[0]

        # Inverter log1p → expm1 (ADR-024)
        if LOG_TARGET:
            pred_lower = np.expm1(pred_lower)
            pred_median = np.expm1(pred_median)
            pred_upper = np.expm1(pred_upper)

        # Garantir não-negatividade e ordenação
        pred_lower = max(0, pred_lower)
        pred_median = max(0, pred_median)
        pred_upper = max(0, pred_upper)

        # Garantir lower <= median <= upper
        pred_lower = min(pred_lower, pred_median)
        pred_upper = max(pred_upper, pred_median)

        resultados.append({
            "data_se": data_pred,
            "y_real": y_real,
            "y_pred": pred_median,
            "lower_bruto": pred_lower,
            "upper_bruto": pred_upper,
            "fase": "calibracao" if data_pred in datas_calib else "avaliacao",
        })

    df_res = pd.DataFrame(resultados)
    df_res["data_se"] = pd.to_datetime(df_res["data_se"])

    # ── Calibração conformal ──
    # Nonconformity scores: max(lower - y, y - upper)
    # Se y está dentro do intervalo, score é negativo (bom)
    # Se y está fora, score é positivo (ruim)
    df_calib = df_res[df_res["fase"] == "calibracao"].copy()

    scores = np.maximum(
        df_calib["lower_bruto"].values - df_calib["y_real"].values,
        df_calib["y_real"].values - df_calib["upper_bruto"].values,
    )

    # Quantil conformal: garante cobertura >= (1-alpha)
    # Fórmula: ceil((n+1)(1-alpha)) / n
    n_calib_real = len(scores)
    q_conformal = np.quantile(
        scores,
        np.ceil((n_calib_real + 1) * (1 - alpha)) / n_calib_real,
        method="higher",
    )

    print(f"  Ajuste conformal: q={q_conformal:.2f}")
    print(f"    (positivo = intervalos brutos eram estreitos demais)")
    print(f"    (negativo = intervalos brutos já eram conservadores)")

    # Aplicar ajuste conformal a TODAS as previsões
    df_res["lower_calibrado"] = (df_res["lower_bruto"] - q_conformal).clip(lower=0)
    df_res["upper_calibrado"] = df_res["upper_bruto"] + q_conformal
    df_res["largura_bruta"] = df_res["upper_bruto"] - df_res["lower_bruto"]
    df_res["largura_calibrada"] = df_res["upper_calibrado"] - df_res["lower_calibrado"]

    return df_res


# =====================================================================
# 3. BASELINE — INTERVALO FIXO (BOOTSTRAP RESÍDUOS)
# =====================================================================

def intervalo_fixo_baseline(df_agg, feature_cols, alpha=0.10):
    """
    Baseline: intervalo fixo baseado nos percentis dos resíduos históricos.
    Treina modelo pontual e usa erros do período de calibração para
    definir bandas constantes.
    """
    q_lower, q_upper = get_quantiles(alpha)

    mask_teste = df_agg["data_se"].dt.year >= TESTE_INICIO
    datas_teste = df_agg.loc[mask_teste, "data_se"].values
    n_calib = int(len(datas_teste) * CALIBRATION_FRACTION)

    resultados = []

    for data_pred in tqdm(datas_teste, desc=f"Fixo α={alpha}", leave=False):
        mask_treino = df_agg["data_se"] < data_pred
        mask_pred = df_agg["data_se"] == data_pred

        X_treino = df_agg.loc[mask_treino, feature_cols].values
        X_pred = df_agg.loc[mask_pred, feature_cols].values
        y_real = df_agg.loc[mask_pred, TARGET].values[0]

        y_treino = df_agg.loc[mask_treino, TARGET].values
        if LOG_TARGET:
            y_treino_log = np.log1p(y_treino)
        else:
            y_treino_log = y_treino

        if len(X_treino) < 52:
            continue

        modelo = lgb.LGBMRegressor(**LGBM_PARAMS)
        modelo.fit(X_treino, y_treino_log)

        pred = modelo.predict(X_pred)[0]
        if LOG_TARGET:
            pred = np.expm1(pred)
        pred = max(0, pred)

        resultados.append({
            "data_se": data_pred,
            "y_real": y_real,
            "y_pred_fixo": pred,
        })

    df_fixo = pd.DataFrame(resultados)
    df_fixo["data_se"] = pd.to_datetime(df_fixo["data_se"])

    # Calcular resíduos no período de calibração
    residuos_calib = (
        df_fixo.iloc[:n_calib]["y_real"].values
        - df_fixo.iloc[:n_calib]["y_pred_fixo"].values
    )

    # Percentis fixos dos resíduos
    lower_delta = np.quantile(residuos_calib, q_lower)
    upper_delta = np.quantile(residuos_calib, q_upper)

    print(f"\n  Baseline fixo: delta=[{lower_delta:.1f}, +{upper_delta:.1f}]")

    df_fixo["lower_fixo"] = (df_fixo["y_pred_fixo"] + lower_delta).clip(lower=0)
    df_fixo["upper_fixo"] = df_fixo["y_pred_fixo"] + upper_delta
    df_fixo["largura_fixa"] = df_fixo["upper_fixo"] - df_fixo["lower_fixo"]

    return df_fixo


# =====================================================================
# 4. MÉTRICAS DE INTERVALOS
# =====================================================================

def calcular_metricas_intervalos(df, col_lower, col_upper, col_real="y_real", label=""):
    """
    Métricas padrão para avaliação de intervalos de predição.

    - Cobertura empírica: % de valores reais dentro do intervalo
    - Largura média: tamanho médio do intervalo (quanto menor, melhor)
    - PICP: Prediction Interval Coverage Probability
    - MPIW: Mean Prediction Interval Width
    - CWC: Coverage Width Criterion (Khosravi et al. 2011)

    Referência: Khosravi et al. (2011) — Comprehensive review of neural
    network-based prediction intervals.
    """
    lower = df[col_lower].values
    upper = df[col_upper].values
    y_real = df[col_real].values

    cobertura = np.mean((y_real >= lower) & (y_real <= upper))
    largura_media = np.mean(upper - lower)
    largura_mediana = np.median(upper - lower)

    # Cobertura por fase (se existir coluna)
    metricas = {
        "metodo": label,
        "cobertura": cobertura,
        "largura_media": largura_media,
        "largura_mediana": largura_mediana,
        "n_amostras": len(y_real),
    }

    return metricas


# =====================================================================
# 5. VISUALIZAÇÕES
# =====================================================================

def plot_serie_com_intervalos(df_cqr, df_fixo, alpha, ax=None):
    """
    Gráfico principal: série temporal com bandas CQR vs fixo.
    Mostra a adaptatividade do CQR (bandas que respiram).
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(16, 6))

    # Apenas avaliação (excluir calibração)
    df_eval = df_cqr[df_cqr["fase"] == "avaliacao"].copy()
    df_fixo_eval = df_fixo.iloc[
        int(len(df_fixo) * CALIBRATION_FRACTION) :
    ].copy()

    dates = df_eval["data_se"].values

    # Intervalo CQR (adaptativo)
    ax.fill_between(
        dates,
        df_eval["lower_calibrado"],
        df_eval["upper_calibrado"],
        alpha=0.25,
        color="#2196F3",
        label=f"CQR {100*(1-alpha):.0f}%",
    )

    # Intervalo fixo (baseline)
    ax.fill_between(
        dates,
        df_fixo_eval["lower_fixo"],
        df_fixo_eval["upper_fixo"],
        alpha=0.15,
        color="#FF9800",
        label=f"Fixo {100*(1-alpha):.0f}%",
    )

    # Valores reais e previstos
    ax.plot(dates, df_eval["y_real"], "k-", linewidth=1.5, label="Real", zorder=5)
    ax.plot(
        dates, df_eval["y_pred"], "--", color="#2196F3", linewidth=1,
        label="Previsão (mediana)", zorder=4,
    )

    ax.set_xlabel("Semana Epidemiológica")
    ax.set_ylabel("Casos confirmados (CWB + VG)")
    ax.set_title(
        f"Intervalos de Predição — CQR vs Fixo ({100*(1-alpha):.0f}%)\n"
        f"Conformalized Quantile Regression (Romano et al., 2019)"
    )
    ax.legend(loc="upper left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b/%Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.xticks(rotation=45)

    return ax


def plot_cobertura_por_periodo(df_cqr, alpha):
    """
    Cobertura empírica por trimestre/semestre.
    Mostra se o CQR mantém cobertura nominal em diferentes fases
    do ciclo epidêmico (pico vs entressafra).
    """
    df_eval = df_cqr[df_cqr["fase"] == "avaliacao"].copy()
    df_eval["ano"] = df_eval["data_se"].dt.year
    df_eval["trimestre"] = df_eval["data_se"].dt.quarter
    df_eval["periodo"] = (
        df_eval["ano"].astype(str) + "-Q" + df_eval["trimestre"].astype(str)
    )

    # Cobertura por período
    df_eval["coberto"] = (
        (df_eval["y_real"] >= df_eval["lower_calibrado"])
        & (df_eval["y_real"] <= df_eval["upper_calibrado"])
    ).astype(int)

    cob_periodo = df_eval.groupby("periodo").agg(
        cobertura=("coberto", "mean"),
        n=("coberto", "count"),
        casos_medio=("y_real", "mean"),
    ).reset_index()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    # Cobertura
    cores = ["#4CAF50" if c >= (1 - alpha) else "#F44336" for c in cob_periodo["cobertura"]]
    ax1.bar(cob_periodo["periodo"], cob_periodo["cobertura"], color=cores, alpha=0.8)
    ax1.axhline(y=1 - alpha, color="red", linestyle="--", label=f"Nominal ({100*(1-alpha):.0f}%)")
    ax1.set_ylabel("Cobertura empírica")
    ax1.set_title(f"Cobertura por trimestre — CQR {100*(1-alpha):.0f}%")
    ax1.legend()
    ax1.set_ylim(0, 1.1)

    # Casos médios (contexto)
    ax2.bar(cob_periodo["periodo"], cob_periodo["casos_medio"], color="#9E9E9E", alpha=0.6)
    ax2.set_ylabel("Casos médios/semana")
    ax2.set_xlabel("Período")
    plt.xticks(rotation=45)
    plt.tight_layout()

    return fig


def plot_largura_adaptativa(df_cqr, df_fixo, alpha):
    """
    Compara largura do intervalo CQR (adaptativo) vs fixo ao longo do tempo.
    Evidencia como o CQR alarga nos picos e estreita nos vales.
    """
    df_eval = df_cqr[df_cqr["fase"] == "avaliacao"].copy()
    df_fixo_eval = df_fixo.iloc[
        int(len(df_fixo) * CALIBRATION_FRACTION) :
    ].copy()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    # Largura ao longo do tempo
    ax1.plot(
        df_eval["data_se"], df_eval["largura_calibrada"],
        color="#2196F3", label="CQR (adaptativo)", linewidth=1.5,
    )
    ax1.axhline(
        y=df_fixo_eval["largura_fixa"].iloc[0],
        color="#FF9800", linestyle="--", label="Fixo (constante)", linewidth=1.5,
    )
    ax1.set_ylabel("Largura do intervalo")
    ax1.set_title(f"Largura dos intervalos — Adaptativo vs Fixo ({100*(1-alpha):.0f}%)")
    ax1.legend()

    # Casos reais (contexto)
    ax2.fill_between(
        df_eval["data_se"], 0, df_eval["y_real"],
        alpha=0.3, color="#4CAF50", label="Casos reais",
    )
    ax2.set_ylabel("Casos confirmados")
    ax2.set_xlabel("Semana Epidemiológica")
    ax2.legend()

    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b/%Y"))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b/%Y"))
    plt.xticks(rotation=45)
    plt.tight_layout()

    return fig


# =====================================================================
# 6. MAIN
# =====================================================================

def main():
    print("=" * 60)
    print("INTERVALOS DE PREDIÇÃO — CQR (Romano et al., 2019)")
    print("MAPIE + LightGBM Quantile Regression")
    print("=" * 60)

    # Carregar dados
    df = carregar_gold()
    df_agg = preparar_dados(df)
    feature_cols = preparar_features(df_agg)

    # Armazenar resultados de todos os alphas
    todos_resultados = []
    todas_metricas = []

    for alpha in ALPHA_LEVELS:
        nivel = f"{100*(1-alpha):.0f}%"
        print(f"\n{'='*60}")
        print(f"NÍVEL DE CONFIANÇA: {nivel}")
        print(f"{'='*60}")

        # ── CQR (adaptativo) ──
        print("\n▶ Executando CQR (adaptativo)...")
        df_cqr = executar_cqr(df_agg, feature_cols, alpha=alpha)

        # ── Baseline fixo ──
        print("\n▶ Executando baseline fixo...")
        df_fixo = intervalo_fixo_baseline(df_agg, feature_cols, alpha=alpha)

        # ── Métricas ──
        # Avaliar apenas no período de avaliação (excluir calibração)
        df_cqr_eval = df_cqr[df_cqr["fase"] == "avaliacao"]
        df_fixo_eval = df_fixo.iloc[int(len(df_fixo) * CALIBRATION_FRACTION):]

        m_cqr = calcular_metricas_intervalos(
            df_cqr_eval, "lower_calibrado", "upper_calibrado",
            label=f"CQR {nivel}",
        )
        m_bruto = calcular_metricas_intervalos(
            df_cqr_eval, "lower_bruto", "upper_bruto",
            label=f"QR bruto {nivel}",
        )
        m_fixo = calcular_metricas_intervalos(
            df_fixo_eval, "lower_fixo", "upper_fixo",
            label=f"Fixo {nivel}",
        )

        print(f"\n📊 Resultados — {nivel}:")
        print(f"  {'Método':<20} {'Cobertura':>10} {'Largura média':>15}")
        print(f"  {'-'*47}")
        for m in [m_cqr, m_bruto, m_fixo]:
            print(
                f"  {m['metodo']:<20} {m['cobertura']:>9.1%}"
                f" {m['largura_media']:>14.1f}"
            )

        todas_metricas.extend([m_cqr, m_bruto, m_fixo])

        # ── Figuras ──
        print(f"\n📈 Gerando figuras...")

        # Fig 1 — Série com intervalos
        fig1, ax1 = plt.subplots(figsize=(16, 6))
        plot_serie_com_intervalos(df_cqr, df_fixo, alpha, ax=ax1)
        fig1.tight_layout()
        path1 = REPORTS_DIR / f"fig01_serie_intervalos_{nivel.replace('%','pct')}.png"
        fig1.savefig(path1, dpi=150, bbox_inches="tight")
        plt.close(fig1)
        print(f"  ✅ {path1.name}")

        # Fig 2 — Cobertura por período
        fig2 = plot_cobertura_por_periodo(df_cqr, alpha)
        path2 = REPORTS_DIR / f"fig02_cobertura_periodo_{nivel.replace('%','pct')}.png"
        fig2.savefig(path2, dpi=150, bbox_inches="tight")
        plt.close(fig2)
        print(f"  ✅ {path2.name}")

        # Fig 3 — Largura adaptativa
        fig3 = plot_largura_adaptativa(df_cqr, df_fixo, alpha)
        path3 = REPORTS_DIR / f"fig03_largura_adaptativa_{nivel.replace('%','pct')}.png"
        fig3.savefig(path3, dpi=150, bbox_inches="tight")
        plt.close(fig3)
        print(f"  ✅ {path3.name}")

        # Salvar previsões detalhadas
        df_cqr["alpha"] = alpha
        todos_resultados.append(df_cqr)

    # ── Salvar CSVs ──
    df_metricas = pd.DataFrame(todas_metricas)
    df_metricas.to_csv(REPORTS_DIR / "metricas_intervalos.csv", index=False)
    print(f"\n✅ {REPORTS_DIR / 'metricas_intervalos.csv'}")

    df_todos = pd.concat(todos_resultados, ignore_index=True)
    df_todos.to_csv(REPORTS_DIR / "previsoes_com_intervalos.csv", index=False)
    print(f"✅ {REPORTS_DIR / 'previsoes_com_intervalos.csv'}")

    # ── Resumo final ──
    print(f"\n{'='*60}")
    print("RESUMO FINAL")
    print(f"{'='*60}")
    print(df_metricas.to_string(index=False))
    print(f"\nFiguras salvas em: {REPORTS_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()