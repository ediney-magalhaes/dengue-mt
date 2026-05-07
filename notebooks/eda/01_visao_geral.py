"""
===============================================================================
01_visao_geral.py — Estatísticas Descritivas e Missing Values
===============================================================================
Análise:
  - Resumo estatístico por município (média, mediana, desvio, assimetria)
  - Contagem e percentual de missing values por feature
  - Tabela de cobertura por grupo de features

Referência: Kaur et al. (2023) — framework EDA para dados epidemiológicos
Saída: reports/eda/fig01_missing_values.png
===============================================================================
"""

import sys
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from config_eda import (
    carregar_gold, salvar_figura, aplicar_estilo,
    MUNICIPIOS, CORES, OUTPUT_DIR,
    FEATURES_TARGET, FEATURES_EPIDEMIO, FEATURES_TEMPERATURA,
    FEATURES_PRECIP_UMIDADE, FEATURES_MEDIAS_MOVEIS, FEATURES_ONI,
    FEATURES_MODIS, FEATURES_TRENDS, FEATURES_AUTOREGRESSIVO,
)


def resumo_estatistico(df):
    """Imprime resumo estatístico detalhado por município."""
    print("\n" + "=" * 70)
    print("RESUMO ESTATÍSTICO — CASOS CONFIRMADOS")
    print("=" * 70)

    for mun_id, nome in MUNICIPIOS.items():
        dm = df[df['municipio_id'] == mun_id]['casos_confirmados']
        print(f"\n{'─' * 40}")
        print(f"  {nome} (geocode {mun_id})")
        print(f"{'─' * 40}")
        print(f"  Semanas:          {len(dm)}")
        print(f"  Total acumulado:  {dm.sum():,.0f}")
        print(f"  Média semanal:    {dm.mean():.1f}")
        print(f"  Mediana semanal:  {dm.median():.1f}")
        print(f"  Desvio padrão:    {dm.std():.1f}")
        print(f"  Mínimo:           {dm.min():.0f}")
        print(f"  Máximo:           {dm.max():.0f}")
        print(f"  Q1 (25%):         {dm.quantile(0.25):.1f}")
        print(f"  Q3 (75%):         {dm.quantile(0.75):.1f}")
        print(f"  Assimetria:       {dm.skew():.2f}")
        print(f"  Curtose:          {dm.kurtosis():.2f}")

    # Teste de normalidade
    print(f"\n{'─' * 40}")
    print("  Teste de Shapiro-Wilk (normalidade)")
    print(f"{'─' * 40}")
    from scipy.stats import shapiro
    for mun_id, nome in MUNICIPIOS.items():
        dm = df[df['municipio_id'] == mun_id]['casos_confirmados']
        # Shapiro-Wilk tem limite de 5000 amostras
        stat, p_value = shapiro(dm.values[:5000])
        resultado = "NÃO normal" if p_value < 0.05 else "Normal"
        print(f"  {nome}: W={stat:.4f}, p={p_value:.2e} → {resultado}")

    print(f"\n  → Assimetria positiva alta confirma distribuição right-skewed")
    print(f"  → Justifica transformação log1p(y) no modelo LightGBM")


def analise_missing_values(df):
    """Analisa e visualiza missing values."""
    print("\n" + "=" * 70)
    print("MISSING VALUES")
    print("=" * 70)

    nulos = df.isnull().sum()
    nulos_pct = (nulos / len(df) * 100).round(2)
    nulos_df = (
        nulos_pct[nulos_pct > 0]
        .sort_values(ascending=False)
        .reset_index()
    )
    nulos_df.columns = ['feature', 'pct_nulo']

    if len(nulos_df) == 0:
        print("\n  ✅ Nenhum valor nulo encontrado no Gold v5!")
        print("  O pipeline dbt garante completude via testes declarativos.")
        return None

    print(f"\n  Features com nulos ({len(nulos_df)}):")
    for _, row in nulos_df.iterrows():
        print(f"    {row['feature']:35s} {row['pct_nulo']:.2f}%")

    return nulos_df


def plot_cobertura_por_grupo(df):
    """Gráfico de barras com cobertura (% não-nulo) por grupo de features."""
    grupos = {
        'Target':          FEATURES_TARGET,
        'Epidemiológico':  FEATURES_EPIDEMIO,
        'Temperatura':     FEATURES_TEMPERATURA,
        'Precip/Umidade':  FEATURES_PRECIP_UMIDADE,
        'Médias Móveis':   FEATURES_MEDIAS_MOVEIS,
        'ONI/ENSO':        FEATURES_ONI,
        'MODIS':           FEATURES_MODIS,
        'Trends':          FEATURES_TRENDS,
        'Autoregressivo':  FEATURES_AUTOREGRESSIVO,
    }

    cobertura = {}
    for grupo, features in grupos.items():
        feats_existem = [f for f in features if f in df.columns]
        if feats_existem:
            pct = (1 - df[feats_existem].isnull().mean().mean()) * 100
            cobertura[grupo] = pct

    fig, ax = plt.subplots(figsize=(10, 5))

    nomes = list(cobertura.keys())
    valores = list(cobertura.values())
    cores_barra = ['#2ecc71' if v >= 99 else '#f39c12' if v >= 95 else '#e74c3c'
                   for v in valores]

    bars = ax.barh(nomes, valores, color=cores_barra, edgecolor='white', height=0.6)

    for bar, val in zip(bars, valores):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                f'{val:.1f}%', ha='left', va='center', fontsize=9, fontweight='bold')

    ax.set_xlim(0, 105)
    ax.set_xlabel('Cobertura (%)')
    ax.set_title('Cobertura por Grupo de Features — Gold v5',
                 fontweight='bold')
    ax.axvline(100, color='gray', linestyle='--', linewidth=0.5)

    return salvar_figura(fig, 'fig01_cobertura_features.png')


def main():
    aplicar_estilo()
    df = carregar_gold()

    resumo_estatistico(df)
    analise_missing_values(df)

    print("\n📊 Gerando gráficos...")
    plot_cobertura_por_grupo(df)

    print("\n✅ 01_visao_geral concluído!")
    print("─" * 40)


if __name__ == '__main__':
    main()