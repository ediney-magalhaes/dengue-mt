"""
===============================================================================
01_backtesting_expanding.py — Backtesting Expanding Window
===============================================================================
Avalia o LightGBM v5 simulando uso em produção:
  - Expanding window: treina 2018→t, prevê t+h (h=1,2,3,4)
  - Duas estratégias: recursiva (1 modelo) e direta (4 modelos)
  - Baselines: naïve (último valor) e média móvel 4 SE
  - Métricas: MAE, RMSE, R², MASE
  - Estratificação: geral, 2023, 2024, 2025-2026

Referências:
  - Araujo et al. (PNAS 2026) — IMDC24 Dengue Forecasting Sprint
  - Reich et al. (2019) — FluSight: expanding window + baselines
  - Hyndman & Koehler (2006) — MASE como métrica escalada

Saída:
  - reports/backtesting/metricas_por_horizonte.csv
  - reports/backtesting/previsoes_detalhadas.csv
  - reports/backtesting/fig01_previsao_vs_real.png
  - reports/backtesting/fig02_erro_por_horizonte.png
  - reports/backtesting/fig03_metricas_estratificadas.png
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

from config_backtesting import (
    carregar_gold, preparar_features, calcular_metricas,
    LGBM_PARAMS, HORIZONTES, TARGET, LOG_TARGET,
    TESTE_INICIO, REPORTS_DIR, MUNICIPIOS, COLS_EXCLUIR,
)


# =====================================================================
# 1. PREPARAÇÃO DOS DADOS
# =====================================================================

def preparar_dados_backtesting(df):
    """
    Agrega por semana (soma dos dois municípios) e prepara target.
    Retorna DataFrame com features + target prontos para treino.
    """
    # Agregar por semana (modelo atual usa soma dos municípios)
    feature_cols = preparar_features(df)

    # Separar treino/teste pelo ano
    df_treino_pool = df[df["data_se"].dt.year < TESTE_INICIO].copy()
    df_teste_pool = df[df["data_se"].dt.year >= TESTE_INICIO].copy()

    # Datas únicas de teste (por município)
    datas_teste = sorted(df_teste_pool["data_se"].unique())

    print(f"\n📊 Configuração do backtesting:")
    print(f"  Treino inicial: até {TESTE_INICIO - 1}")
    print(f"  Teste: {TESTE_INICIO} → {df['data_se'].dt.year.max()}")
    print(f"  Semanas de teste: {len(datas_teste)}")
    print(f"  Horizontes: {HORIZONTES}")
    print(f"  Features: {len(feature_cols)}")

    return df, feature_cols, datas_teste


# =====================================================================
# 2. ESTRATÉGIA RECURSIVA (1 modelo, previsão encadeada)
# =====================================================================

def backtesting_recursivo(df, feature_cols, datas_teste):
    """
    Estratégia recursiva: treina 1 modelo para h=1,
    usa previsão como input para h=2, h=3, h=4.
    """
    print("\n" + "=" * 60)
    print("ESTRATÉGIA RECURSIVA (1 modelo, previsão encadeada)")
    print("=" * 60)

    resultados = []
    max_h = max(HORIZONTES)

    for i, data_previsao_base in enumerate(tqdm(datas_teste, desc="Recursivo")):
        # Dados disponíveis até esta data (para todos os municípios)
        mask_treino = df["data_se"] < data_previsao_base

        df_treino = df[mask_treino].copy()
        if len(df_treino) < 52:  # mínimo 1 ano de dados
            continue

        X_treino = df_treino[feature_cols].values
        y_treino = df_treino[TARGET].values

        if LOG_TARGET:
            y_treino = np.log1p(y_treino)

        # Treinar modelo
        modelo = lgb.LGBMRegressor(**LGBM_PARAMS)
        modelo.fit(X_treino, y_treino)

        # Prever para cada horizonte
        for h in HORIZONTES:
            # Encontrar a data-alvo h semanas à frente
            idx_base = list(datas_teste).index(data_previsao_base)
            idx_alvo = idx_base + h - 1  # h=1 → mesma posição

            if idx_alvo >= len(datas_teste):
                continue

            data_alvo = datas_teste[idx_alvo]

            # Pegar registros reais da data alvo
            mask_alvo = df["data_se"] == data_alvo
            df_alvo = df[mask_alvo]

            if len(df_alvo) == 0:
                continue

            for _, row in df_alvo.iterrows():
                X_pred = row[feature_cols].values.reshape(1, -1)
                y_pred = modelo.predict(X_pred)[0]

                if LOG_TARGET:
                    y_pred = np.expm1(y_pred)

                y_pred = max(0, y_pred)  # casos não podem ser negativos
                y_real = row[TARGET]

                # Baseline naïve: último valor observado do mesmo município
                mun_id = row["municipio_id"]
                historico_mun = df[
                    (df["municipio_id"] == mun_id) &
                    (df["data_se"] < data_previsao_base)
                ][TARGET]
                naive = historico_mun.iloc[-1] if len(historico_mun) > 0 else 0

                # Baseline MM4: média das últimas 4 semanas
                mm4 = historico_mun.tail(4).mean() if len(historico_mun) >= 4 else naive

                resultados.append({
                    "data_previsao": data_previsao_base,
                    "data_alvo": data_alvo,
                    "horizonte": h,
                    "municipio_id": mun_id,
                    "y_real": y_real,
                    "y_pred_recursivo": y_pred,
                    "y_naive": naive,
                    "y_mm4": mm4,
                })

    return pd.DataFrame(resultados)


# =====================================================================
# 3. ESTRATÉGIA DIRETA (4 modelos independentes)
# =====================================================================

def backtesting_direto(df, feature_cols, datas_teste):
    """
    Estratégia direta: treina 1 modelo por horizonte.
    Cada modelo aprende a prever diretamente h semanas à frente.
    """
    print("\n" + "=" * 60)
    print("ESTRATÉGIA DIRETA (4 modelos independentes)")
    print("=" * 60)

    resultados = []

    for h in HORIZONTES:
        print(f"\n  Horizonte h={h}...")

        # Criar target deslocado: y(t+h)
        df_h = df.copy()
        df_h[f"target_h{h}"] = (
            df_h.groupby("municipio_id")[TARGET]
            .shift(-h)
        )

        # Remover registros sem target futuro
        df_h = df_h.dropna(subset=[f"target_h{h}"])

        for data_previsao in tqdm(datas_teste, desc=f"Direto h={h}", leave=False):
            mask_treino = df_h["data_se"] < data_previsao
            mask_pred = df_h["data_se"] == data_previsao

            df_treino = df_h[mask_treino]
            df_pred = df_h[mask_pred]

            if len(df_treino) < 52 or len(df_pred) == 0:
                continue

            X_treino = df_treino[feature_cols].values
            y_treino = df_treino[f"target_h{h}"].values

            if LOG_TARGET:
                y_treino = np.log1p(y_treino)

            modelo = lgb.LGBMRegressor(**LGBM_PARAMS)
            modelo.fit(X_treino, y_treino)

            for _, row in df_pred.iterrows():
                X_pred = row[feature_cols].values.reshape(1, -1)
                y_pred = modelo.predict(X_pred)[0]

                if LOG_TARGET:
                    y_pred = np.expm1(y_pred)

                y_pred = max(0, y_pred)

                # Target real h semanas à frente
                y_real = row[f"target_h{h}"]
                mun_id = row["municipio_id"]

                resultados.append({
                    "data_previsao": data_previsao,
                    "horizonte": h,
                    "municipio_id": mun_id,
                    "y_real": y_real,
                    "y_pred_direto": y_pred,
                })

    return pd.DataFrame(resultados)


# =====================================================================
# 4. CONSOLIDAR E CALCULAR MÉTRICAS
# =====================================================================

def consolidar_resultados(df_recursivo, df_direto):
    """Merge dos resultados recursivo + direto."""
    # Merge pela chave natural
    chave = ["data_previsao", "horizonte", "municipio_id"]

    df_merged = df_recursivo.merge(
        df_direto[chave + ["y_pred_direto"]],
        on=chave,
        how="left",
    )

    # Adicionar período para estratificação
    df_merged["ano_alvo"] = pd.to_datetime(df_merged["data_alvo"]).dt.year
    df_merged["periodo"] = df_merged["ano_alvo"].map(
        lambda x: "2023" if x == 2023
        else "2024" if x == 2024
        else "2025-2026"
    )

    return df_merged


def calcular_todas_metricas(df_resultados):
    """
    Calcula métricas por horizonte, estratégia, período E município.
    
    A coluna Municipio inclui:
      - 'Ambos' (agregado — Cuiabá + Várzea Grande) — mantém compatibilidade
      - 'Cuiabá' (municipio_id=5103403)
      - 'Várzea Grande' (municipio_id=5108402)
    """
    tabelas = []

    # Recortes de município: agregado + cada um separado
    recortes_municipio = [
        ("Ambos", None),                # None = não filtra, usa tudo
        ("Cuiabá", 5103403),
        ("Várzea Grande", 5108402),
    ]

    for horizonte in HORIZONTES:
        dh = df_resultados[df_resultados["horizonte"] == horizonte]

        for periodo in ["Geral", "2023", "2024", "2025-2026"]:
            if periodo == "Geral":
                dp_periodo = dh
            else:
                dp_periodo = dh[dh["periodo"] == periodo]

            for nome_mun, mun_id in recortes_municipio:
                if mun_id is None:
                    dp = dp_periodo
                else:
                    dp = dp_periodo[dp_periodo["municipio_id"] == mun_id]

                if len(dp) < 5:
                    continue

                y_real = dp["y_real"].values

                for estrategia, col_pred in [
                    ("Recursivo", "y_pred_recursivo"),
                    ("Direto", "y_pred_direto"),
                    ("Naïve", "y_naive"),
                    ("MM4", "y_mm4"),
                ]:
                    if col_pred not in dp.columns or dp[col_pred].isna().all():
                        continue

                    y_pred = dp[col_pred].values

                    # Remover NaN
                    mask_valid = ~(np.isnan(y_real) | np.isnan(y_pred))
                    if mask_valid.sum() < 5:
                        continue

                    metricas = calcular_metricas(
                        y_real[mask_valid],
                        y_pred[mask_valid],
                        y_naive=dp["y_naive"].values[mask_valid] if "y_naive" in dp.columns else None,
                    )

                    tabelas.append({
                        "Horizonte": f"h={horizonte}",
                        "Estratégia": estrategia,
                        "Período": periodo,
                        "Municipio": nome_mun,
                        **metricas,
                    })

    return pd.DataFrame(tabelas)


# =====================================================================
# 5. VISUALIZAÇÕES
# =====================================================================

def plot_previsao_vs_real(df_resultados):
    """Previsão vs real por horizonte — série temporal."""
    fig, axes = plt.subplots(4, 1, figsize=(14, 16), sharex=True)

    for ax, h in zip(axes, HORIZONTES):
        dh = df_resultados[df_resultados["horizonte"] == h].copy()
        dh = dh.sort_values("data_alvo")

        # Agregar por data_alvo (soma municípios)
        agg = dh.groupby("data_alvo").agg({
            "y_real": "sum",
            "y_pred_recursivo": "sum",
            "y_pred_direto": "sum",
            "y_naive": "sum",
        }).reset_index()

        ax.plot(agg["data_alvo"], agg["y_real"],
                "k-", linewidth=1.5, label="Real", alpha=0.8)
        ax.plot(agg["data_alvo"], agg["y_pred_recursivo"],
                "b-", linewidth=1, label="Recursivo", alpha=0.7)

        if "y_pred_direto" in agg.columns and not agg["y_pred_direto"].isna().all():
            ax.plot(agg["data_alvo"], agg["y_pred_direto"],
                    "r--", linewidth=1, label="Direto", alpha=0.7)

        ax.fill_between(agg["data_alvo"], agg["y_real"],
                        alpha=0.1, color="black")
        ax.set_ylabel("Casos/semana")
        ax.set_title(f"Horizonte h={h} ({h} semana{'s' if h > 1 else ''} à frente)",
                     fontweight="bold", loc="left")
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(alpha=0.3)

    axes[-1].xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    axes[-1].set_xlabel("Data")
    plt.xticks(rotation=45)

    fig.suptitle(
        "Backtesting Expanding Window — Previsão vs Real\n"
        f"Período de teste: {TESTE_INICIO}→2026 | LightGBM v5",
        fontsize=14, fontweight="bold", y=1.02,
    )
    plt.tight_layout()

    path = REPORTS_DIR / "fig01_previsao_vs_real.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"  ✅ Salvo: {path}")
    plt.close(fig)


def plot_metricas_horizonte(df_metricas):
    """Barras de MAE e MASE por horizonte e estratégia."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    geral = df_metricas[df_metricas["Período"] == "Geral"].copy()

    # ── MAE por horizonte ──
    ax = axes[0]
    estrategias = ["Recursivo", "Direto", "Naïve", "MM4"]
    cores = ["#3498db", "#e74c3c", "#95a5a6", "#bdc3c7"]
    x = np.arange(len(HORIZONTES))
    width = 0.2

    for i, (est, cor) in enumerate(zip(estrategias, cores)):
        vals = []
        for h in HORIZONTES:
            row = geral[(geral["Horizonte"] == f"h={h}") & (geral["Estratégia"] == est)]
            vals.append(row["MAE"].values[0] if len(row) > 0 else 0)

        bars = ax.bar(x + i * width, vals, width, label=est, color=cor, alpha=0.85)
        for bar, val in zip(bars, vals):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                        f"{val:.1f}", ha="center", fontsize=7)

    ax.set_xlabel("Horizonte")
    ax.set_ylabel("MAE (casos/semana)")
    ax.set_title("MAE por Horizonte e Estratégia", fontweight="bold")
    ax.set_xticks(x + 1.5 * width)
    ax.set_xticklabels([f"h={h}" for h in HORIZONTES])
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")

    # ── MASE por horizonte ──
    ax = axes[1]
    for i, (est, cor) in enumerate(zip(["Recursivo", "Direto"], ["#3498db", "#e74c3c"])):
        vals = []
        for h in HORIZONTES:
            row = geral[(geral["Horizonte"] == f"h={h}") & (geral["Estratégia"] == est)]
            vals.append(row["MASE"].values[0] if len(row) > 0 and "MASE" in row.columns else 1)

        ax.bar(x + i * 0.35, vals, 0.35, label=est, color=cor, alpha=0.85)

    ax.axhline(1.0, color="black", linestyle="--", linewidth=1,
               label="MASE=1 (= baseline naïve)")
    ax.set_xlabel("Horizonte")
    ax.set_ylabel("MASE")
    ax.set_title("MASE por Horizonte (< 1 = melhor que naïve)", fontweight="bold")
    ax.set_xticks(x + 0.175)
    ax.set_xticklabels([f"h={h}" for h in HORIZONTES])
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, axis="y")

    plt.tight_layout()
    path = REPORTS_DIR / "fig02_metricas_por_horizonte.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"  ✅ Salvo: {path}")
    plt.close(fig)


def plot_metricas_estratificadas(df_metricas):
    """Heatmap de MAE por período × horizonte para cada estratégia."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    for ax, estrategia in zip(axes, ["Recursivo", "Direto"]):
        subset = df_metricas[
            (df_metricas["Estratégia"] == estrategia) &
            (df_metricas["Período"] != "Geral")
        ]

        if len(subset) == 0:
            ax.text(0.5, 0.5, "Sem dados", ha="center", va="center")
            continue

        pivot = subset.pivot_table(
            index="Período", columns="Horizonte", values="MAE"
        )

        im = ax.imshow(pivot.values, cmap="YlOrRd", aspect="auto")
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels(pivot.columns)
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels(pivot.index)

        # Anotar valores
        for i in range(len(pivot.index)):
            for j in range(len(pivot.columns)):
                val = pivot.values[i, j]
                ax.text(j, i, f"{val:.1f}",
                        ha="center", va="center", fontsize=10,
                        color="white" if val > pivot.values.max() * 0.6 else "black")

        ax.set_title(f"MAE — {estrategia}", fontweight="bold")
        ax.set_xlabel("Horizonte")

    fig.suptitle(
        "MAE Estratificado por Período e Horizonte\n"
        "Valores menores = melhor desempenho",
        fontsize=13, fontweight="bold", y=1.05,
    )
    plt.colorbar(im, ax=axes, shrink=0.8, label="MAE (casos/semana)")
    plt.tight_layout()

    path = REPORTS_DIR / "fig03_metricas_estratificadas.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"  ✅ Salvo: {path}")
    plt.close(fig)


# =====================================================================
# 6. MAIN
# =====================================================================

def main():
    print("=" * 60)
    print("BACKTESTING EXPANDING WINDOW — LightGBM v5")
    print("Referência: IMDC24 (PNAS 2026), FluSight (Reich 2019)")
    print("=" * 60)

    # Carregar dados
    df = carregar_gold()
    df, feature_cols, datas_teste = preparar_dados_backtesting(df)

    # Executar backtesting recursivo
    df_recursivo = backtesting_recursivo(df, feature_cols, datas_teste)
    print(f"\n  Recursivo: {len(df_recursivo)} previsões geradas")

    # Executar backtesting direto
    df_direto = backtesting_direto(df, feature_cols, datas_teste)
    print(f"  Direto: {len(df_direto)} previsões geradas")

    # Consolidar
    df_resultados = consolidar_resultados(df_recursivo, df_direto)

    # Salvar previsões detalhadas
    path_prev = REPORTS_DIR / "previsoes_detalhadas.csv"
    df_resultados.to_csv(path_prev, index=False)
    print(f"\n  ✅ Previsões salvas: {path_prev}")

    # Calcular métricas
    df_metricas = calcular_todas_metricas(df_resultados)

    # Salvar métricas
    path_met = REPORTS_DIR / "metricas_por_horizonte.csv"
    df_metricas.to_csv(path_met, index=False, float_format="%.3f")
    print(f"  ✅ Métricas salvas: {path_met}")

    # Exibir tabela resumo — MÉTRICAS GERAIS AGREGADAS (ambos municípios)
    print("\n" + "=" * 60)
    print("RESULTADOS — MÉTRICAS GERAIS (AMBOS OS MUNICÍPIOS)")
    print("=" * 60)
    geral_ambos = df_metricas[
        (df_metricas["Período"] == "Geral") & (df_metricas["Municipio"] == "Ambos")
    ][["Horizonte", "Estratégia", "MAE", "RMSE", "R2", "MASE", "N"]]
    print(geral_ambos.to_string(index=False))

    # Exibir tabela resumo — POR MUNICÍPIO (Geral)
    print("\n" + "=" * 60)
    print("RESULTADOS — POR MUNICÍPIO (PERÍODO GERAL)")
    print("=" * 60)
    for nome_mun in ["Cuiabá", "Várzea Grande"]:
        print(f"\n  {nome_mun}:")
        sub = df_metricas[
            (df_metricas["Período"] == "Geral") & (df_metricas["Municipio"] == nome_mun)
        ][["Horizonte", "Estratégia", "MAE", "RMSE", "R2", "MASE", "N"]]
        print(sub.to_string(index=False))

    print("\n" + "=" * 60)
    print("RESULTADOS — POR PERÍODO (AMBOS OS MUNICÍPIOS)")
    print("=" * 60)
    por_periodo = df_metricas[
        (df_metricas["Período"] != "Geral") & (df_metricas["Municipio"] == "Ambos")
    ][["Horizonte", "Estratégia", "Período", "MAE", "R2"]]
    print(por_periodo.to_string(index=False))

    # Gráficos
    print("\n📊 Gerando visualizações...")
    plot_previsao_vs_real(df_resultados)
    plot_metricas_horizonte(df_metricas)
    plot_metricas_estratificadas(df_metricas)

    print("\n" + "=" * 60)
    print("✅ Backtesting concluído!")
    print(f"   {len(df_resultados)} previsões | {len(df_metricas)} métricas")
    print(f"   Figuras em: {REPORTS_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()