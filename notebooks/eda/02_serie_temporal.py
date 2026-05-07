"""
===============================================================================
02_serie_temporal.py — Série Temporal e Decomposição STL
===============================================================================
Análise:
  - Série temporal completa de casos 2018-2025 (Cuiabá × Várzea Grande)
  - Decomposição STL (Seasonal-Trend using Loess): tendência + sazonalidade + resíduo

Referências:
  - Chen & Moraga (2025) — visualização de séries epidemiológicas, Rio de Janeiro
  - Kaur et al. (2023) — STL decomposition para séries de dengue
  - Choi et al. (2016) — sazonalidade climática da dengue, Hanoi

Saída:
  - reports/eda/fig02_serie_temporal_casos.png
  - reports/eda/fig03_decomposicao_stl.png
===============================================================================
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from statsmodels.tsa.seasonal import STL

from config_eda import (
    carregar_gold, salvar_figura, aplicar_estilo,
    MUNICIPIOS, CORES,
)


def plot_serie_temporal(df):
    """
    Série temporal de casos confirmados por município.
    Anota picos anuais relevantes (> percentil 75).
    """
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    for ax, (mun_id, nome) in zip(axes, MUNICIPIOS.items()):
        dm = df[df['municipio_id'] == mun_id].copy()
        cor = CORES[mun_id]

        # Área preenchida + linha
        ax.fill_between(dm['data_se'], dm['casos_confirmados'],
                        alpha=0.25, color=cor)
        ax.plot(dm['data_se'], dm['casos_confirmados'],
                color=cor, linewidth=0.8, label=nome)

        # Anotar picos anuais significativos
        q75 = dm['casos_confirmados'].quantile(0.75)
        for ano in dm['data_se'].dt.year.unique():
            dm_ano = dm[dm['data_se'].dt.year == ano]
            if len(dm_ano) == 0:
                continue
            idx_max = dm_ano['casos_confirmados'].idxmax()
            val_max = dm_ano.loc[idx_max, 'casos_confirmados']
            if val_max > q75:
                ax.annotate(
                    f"{val_max:.0f}",
                    xy=(dm_ano.loc[idx_max, 'data_se'], val_max),
                    xytext=(0, 8), textcoords='offset points',
                    fontsize=8, ha='center', va='bottom',
                    color=cor, fontweight='bold',
                )

        ax.set_ylabel('Casos confirmados\n(semanal)')
        ax.set_title(nome, fontweight='bold', loc='left')
        ax.legend(loc='upper right')

    axes[1].xaxis.set_major_locator(mdates.YearLocator())
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    axes[1].set_xlabel('Ano')

    fig.suptitle(
        'Série Temporal — Casos Confirmados de Dengue por Semana Epidemiológica\n'
        'Cuiabá e Várzea Grande (MT), 2018–2025',
        fontsize=14, fontweight='bold', y=1.03,
    )
    plt.tight_layout()

    return salvar_figura(fig, 'fig02_serie_temporal_casos.png')


def plot_decomposicao_stl(df):
    """
    STL Decomposition — Seasonal and Trend decomposition using Loess.
    Período sazonal = 52 semanas (ciclo anual).
    Modo robusto para reduzir influência de outliers (surtos extremos).
    """
    fig, axes = plt.subplots(4, 2, figsize=(14, 12), sharex=True)

    for col, (mun_id, nome) in enumerate(MUNICIPIOS.items()):
        dm = df[df['municipio_id'] == mun_id].copy()
        serie = dm.set_index('data_se')['casos_confirmados']
        serie = serie.asfreq('W-SUN')
        serie = serie.ffill()  # Preencher gaps eventuais

        # STL: período sazonal de 52 semanas (1 ano epidemiológico)
        stl = STL(serie, period=52, robust=True)
        resultado = stl.fit()

        cor = CORES[mun_id]
        componentes = [
            ('Observado', serie),
            ('Tendência', resultado.trend),
            ('Sazonalidade', resultado.seasonal),
            ('Resíduo', resultado.resid),
        ]

        for row, (titulo, dados) in enumerate(componentes):
            ax = axes[row, col]
            ax.plot(dados.index, dados.values, color=cor, linewidth=0.8)

            # Preencher componente sazonal para destaque visual
            if row == 2:
                ax.fill_between(dados.index, dados.values, alpha=0.25, color=cor)

            # Preencher resíduos positivos/negativos
            if row == 3:
                ax.fill_between(dados.index, dados.values, 0,
                                where=dados.values > 0, alpha=0.2, color='red')
                ax.fill_between(dados.index, dados.values, 0,
                                where=dados.values < 0, alpha=0.2, color='blue')

            if col == 0:
                ax.set_ylabel(titulo, fontsize=10)
            if row == 0:
                ax.set_title(nome, fontweight='bold')

    for ax in axes[3]:
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        ax.set_xlabel('Ano')

    fig.suptitle(
        'Decomposição STL — Tendência, Sazonalidade e Resíduo\n'
        'Período sazonal = 52 semanas | Modo robusto',
        fontsize=14, fontweight='bold', y=1.02,
    )
    plt.tight_layout()

    # Imprimir força da sazonalidade
    print("\n  Força da sazonalidade (variance ratio):")
    for mun_id, nome in MUNICIPIOS.items():
        dm = df[df['municipio_id'] == mun_id].copy()
        serie = dm.set_index('data_se')['casos_confirmados'].asfreq('W-SUN').ffill()
        stl = STL(serie, period=52, robust=True).fit()
        var_sazonal = stl.seasonal.var()
        var_total = serie.var()
        ratio = var_sazonal / var_total
        print(f"    {nome}: {ratio:.3f} ({ratio*100:.1f}% da variância total)")

    return salvar_figura(fig, 'fig03_decomposicao_stl.png')


def main():
    aplicar_estilo()
    df = carregar_gold()

    print("\n📊 Gerando gráficos de série temporal...")
    plot_serie_temporal(df)
    plot_decomposicao_stl(df)

    print("\n✅ 02_serie_temporal concluído!")
    print("─" * 40)


if __name__ == '__main__':
    main()