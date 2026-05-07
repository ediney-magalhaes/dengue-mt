"""
===============================================================================
05_multivariada.py — Séries Multivariadas e Comparação entre Municípios
===============================================================================
Análise:
  - Painel multivariado: casos + temperatura + precipitação + ONI (Cuiabá)
  - Correlação entre municípios (scatter + regressão)
  - Total anual comparativo (barras lado a lado)

Referências:
  - Choi et al. (2016) — visualização lag entre clima e dengue
  - Benedum et al. (2020) — El Niño correlacionado 3-6 meses com dengue

Saída:
  - reports/eda/fig09_serie_multivariada.png
  - reports/eda/fig10_comparacao_municipios.png
===============================================================================
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy import stats

from config_eda import (
    carregar_gold, salvar_figura, aplicar_estilo,
    MUNICIPIOS, CORES,
)


def plot_serie_multivariada(df):
    """
    Painel com série temporal de casos, temperatura, precipitação e ONI.
    Cuiabá como referência (maior volume de casos).
    Permite visualizar visualmente a defasagem entre clima e epidemia.
    """
    dm = df[df['municipio_id'] == 5103403].copy()

    fig, axes = plt.subplots(4, 1, figsize=(14, 10), sharex=True)

    # ── Casos ──
    ax = axes[0]
    ax.fill_between(dm['data_se'], dm['casos_confirmados'],
                    alpha=0.3, color=CORES[5103403])
    ax.plot(dm['data_se'], dm['casos_confirmados'],
            color=CORES[5103403], linewidth=0.8)
    ax.set_ylabel('Casos\nconfirmados')
    ax.set_title('Cuiabá — Séries Temporais Multivariadas (2018–2025)',
                 fontweight='bold', loc='left')

    # ── Temperatura ──
    ax = axes[1]
    ax.plot(dm['data_se'], dm['temp_media_lag1'],
            color='#e74c3c', linewidth=0.8, label='Temp. média (lag1)')
    ax.plot(dm['data_se'], dm['temp_max_lag1'],
            color='#e74c3c', linewidth=0.5, linestyle='--', alpha=0.5,
            label='Temp. máx (lag1)')
    ax.plot(dm['data_se'], dm['temp_min_lag1'],
            color='#3498db', linewidth=0.5, linestyle='--', alpha=0.5,
            label='Temp. mín (lag1)')
    ax.set_ylabel('Temperatura\n(°C)')
    ax.legend(loc='upper right', fontsize=7, ncol=3)

    # ── Precipitação ──
    ax = axes[2]
    ax.bar(dm['data_se'], dm['precip_lag1'],
           color='#3498db', alpha=0.5, width=5, label='Precip. semanal (lag1)')
    # Média móvel 8 semanas para suavizar
    ax.plot(dm['data_se'], dm['precip_acum8'],
            color='#2c3e50', linewidth=1.2, label='Precip. acum. 8 SE')
    ax.set_ylabel('Precipitação\n(mm)')
    ax.legend(loc='upper right', fontsize=7, ncol=2)

    # ── ONI Index ──
    ax = axes[3]
    ax.plot(dm['data_se'], dm['oni_lag4'], color='#2ecc71', linewidth=1.2)
    ax.axhline(0.5, color='red', linestyle='--', linewidth=0.5, alpha=0.7)
    ax.axhline(-0.5, color='blue', linestyle='--', linewidth=0.5, alpha=0.7)
    ax.fill_between(dm['data_se'], dm['oni_lag4'], 0.5,
                    where=dm['oni_lag4'] > 0.5, alpha=0.2, color='red',
                    label='El Niño (ONI > +0.5)')
    ax.fill_between(dm['data_se'], dm['oni_lag4'], -0.5,
                    where=dm['oni_lag4'] < -0.5, alpha=0.2, color='blue',
                    label='La Niña (ONI < -0.5)')
    ax.set_ylabel('ONI Index\n(lag 4 SE)')
    ax.legend(loc='upper right', fontsize=7, ncol=2)
    ax.set_xlabel('Ano')

    axes[3].xaxis.set_major_locator(mdates.YearLocator())
    axes[3].xaxis.set_major_formatter(mdates.DateFormatter('%Y'))

    plt.tight_layout()

    return salvar_figura(fig, 'fig09_serie_multivariada.png')


def plot_comparacao_municipios(df):
    """
    Comparação entre Cuiabá e Várzea Grande:
    - Scatter com regressão linear (esquerda)
    - Total anual em barras (direita)
    """
    # Pivot para ter ambos municípios por data
    pivot = df.pivot_table(
        index='data_se',
        columns='municipio_id',
        values='casos_confirmados',
    ).dropna()

    fig, axes = plt.subplots(1, 2, figsize=(14, 5),
                             gridspec_kw={'width_ratios': [1, 1.5]})

    # ── Scatter + regressão ──
    ax = axes[0]
    ax.scatter(pivot[5103403], pivot[5108402],
               alpha=0.35, s=15, color='#34495e',
               edgecolors='white', linewidth=0.3)

    max_val = max(pivot[5103403].max(), pivot[5108402].max())
    ax.plot([0, max_val], [0, max_val], 'k--', linewidth=0.8, alpha=0.4,
            label='Linha 1:1')

    # Regressão linear
    slope, intercept, r_value, p_value, _ = stats.linregress(
        pivot[5103403], pivot[5108402]
    )
    x_line = np.linspace(0, max_val, 100)
    ax.plot(x_line, slope * x_line + intercept, color='#e74c3c',
            linewidth=1.5, label=f'R²={r_value**2:.3f}, p<0.001')

    ax.set_xlabel('Cuiabá (casos/semana)')
    ax.set_ylabel('Várzea Grande (casos/semana)')
    ax.set_title('Correlação entre municípios', fontweight='bold')
    ax.legend(fontsize=8)

    print(f"\n  Correlação Cuiabá × Várzea Grande:")
    print(f"    R² = {r_value**2:.4f}")
    print(f"    Slope = {slope:.3f}")
    print(f"    p-value = {p_value:.2e}")

    # ── Barras anuais ──
    ax = axes[1]
    df_plot = df.copy()
    df_plot['ano'] = df_plot['data_se'].dt.year
    anual = df_plot.groupby(['ano', 'municipio_id'])['casos_confirmados'].sum().reset_index()

    largura = 0.35
    anos = sorted(anual['ano'].unique())
    x = np.arange(len(anos))

    for i, (mun_id, nome) in enumerate(MUNICIPIOS.items()):
        dados = anual[anual['municipio_id'] == mun_id].set_index('ano')
        valores = [dados.loc[a, 'casos_confirmados'] if a in dados.index else 0
                   for a in anos]
        offset = -largura / 2 + i * largura
        bars = ax.bar(x + offset, valores, largura,
                      color=CORES[mun_id], label=nome, alpha=0.85,
                      edgecolor='white')

        for bar, val in zip(bars, valores):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + max(valores) * 0.01,
                        f'{val:,.0f}', ha='center', va='bottom',
                        fontsize=7, rotation=45)

    ax.set_xticks(x)
    ax.set_xticklabels(anos)
    ax.set_xlabel('Ano')
    ax.set_ylabel('Casos acumulados no ano')
    ax.set_title('Total anual por município', fontweight='bold')
    ax.legend(loc='upper right')

    fig.suptitle(
        'Comparação entre Municípios — Cuiabá × Várzea Grande (2018–2025)',
        fontsize=13, fontweight='bold', y=1.03,
    )
    plt.tight_layout()

    # Imprimir totais anuais
    print("\n  Total anual de casos:")
    for ano in anos:
        linha = f"    {ano}: "
        for mun_id, nome in MUNICIPIOS.items():
            total = anual[(anual['ano'] == ano) & (anual['municipio_id'] == mun_id)]
            val = total['casos_confirmados'].values[0] if len(total) > 0 else 0
            linha += f"{nome}={val:,.0f}  "
        print(linha)

    return salvar_figura(fig, 'fig10_comparacao_municipios.png')


def main():
    aplicar_estilo()
    df = carregar_gold()

    print("\n📊 Gerando gráficos multivariados...")
    plot_serie_multivariada(df)
    plot_comparacao_municipios(df)

    print("\n✅ 05_multivariada concluído!")
    print("─" * 40)


if __name__ == '__main__':
    main()