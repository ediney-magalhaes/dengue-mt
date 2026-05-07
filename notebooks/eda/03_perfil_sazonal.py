"""
===============================================================================
03_perfil_sazonal.py — Perfil Sazonal e Distribuição de Casos
===============================================================================
Análise:
  - Perfil sazonal médio por Semana Epidemiológica (média ± desvio)
  - Distribuição dos casos: histograma + transformação log1p
  - Boxplot por ano — evolução interanual

Referências:
  - Benedum et al. (2020) — padrão sazonal de dengue e pico epidêmico
  - Chen & Moraga (2025) — distribuição de casos e transformações

Saída:
  - reports/eda/fig04_perfil_sazonal.png
  - reports/eda/fig05_distribuicao_casos.png
===============================================================================
"""

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from config_eda import (
    carregar_gold, salvar_figura, aplicar_estilo,
    MUNICIPIOS, CORES,
)


def plot_perfil_sazonal(df):
    """
    Perfil sazonal médio por Semana Epidemiológica.
    Banda de incerteza: média ± 1 desvio padrão.
    Mediana pontilhada para comparar com a média (efeito dos surtos extremos).
    """
    fig, ax = plt.subplots(figsize=(13, 5))

    for mun_id, nome in MUNICIPIOS.items():
        dm = df[df['municipio_id'] == mun_id].copy()
        # Extrair número da semana (2 últimos dígitos do formato YYYYSS)
        dm['se_numero'] = dm['semana_epidemiologica'] % 100
        perfil = dm.groupby('se_numero')['casos_confirmados'].agg(
            ['mean', 'std', 'median']
        ).reset_index()

        cor = CORES[mun_id]

        # Média com banda de ±1σ
        ax.plot(perfil['se_numero'], perfil['mean'],
                color=cor, linewidth=2, label=f'{nome} (média)')
        ax.fill_between(
            perfil['se_numero'],
            np.maximum(perfil['mean'] - perfil['std'], 0),
            perfil['mean'] + perfil['std'],
            alpha=0.12, color=cor,
        )

        # Mediana pontilhada
        ax.plot(perfil['se_numero'], perfil['median'],
                color=cor, linewidth=1.2, linestyle='--', alpha=0.6,
                label=f'{nome} (mediana)')

    # Anotar períodos epidemiológicos
    ax.axvspan(1, 17, alpha=0.06, color='red')
    ax.axvspan(18, 26, alpha=0.06, color='orange')
    ax.axvspan(27, 44, alpha=0.06, color='green')
    ax.axvspan(45, 52, alpha=0.06, color='orange')

    ax.text(9, ax.get_ylim()[1] * 0.92, 'Pico epidêmico\n(verão/outono)',
            ha='center', fontsize=8, color='darkred', fontstyle='italic')
    ax.text(35, ax.get_ylim()[1] * 0.92, 'Entressafra\n(inverno)',
            ha='center', fontsize=8, color='darkgreen', fontstyle='italic')

    ax.set_xlabel('Semana Epidemiológica (SE)')
    ax.set_ylabel('Casos confirmados (média semanal)')
    ax.set_title(
        'Perfil Sazonal Médio — Dengue por Semana Epidemiológica (2018–2025)\n'
        'Banda: média ± 1 desvio padrão',
        fontweight='bold',
    )
    ax.legend(loc='upper right', ncol=2)
    ax.set_xlim(1, 52)

    # Imprimir SE de pico
    print("\n  SE de pico (média máxima):")
    for mun_id, nome in MUNICIPIOS.items():
        dm = df[df['municipio_id'] == mun_id].copy()
        dm['se_numero'] = dm['semana_epidemiologica'] % 100
        perfil = dm.groupby('se_numero')['casos_confirmados'].mean()
        se_pico = perfil.idxmax()
        val_pico = perfil.max()
        print(f"    {nome}: SE {se_pico} ({val_pico:.1f} casos/semana)")

    return salvar_figura(fig, 'fig04_perfil_sazonal.png')


def plot_distribuicao_casos(df):
    """
    Distribuição dos casos: histograma (esquerda) e boxplot anual (direita).
    Inset com distribuição log1p para justificar a transformação no modelo.
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 5),
                             gridspec_kw={'width_ratios': [1, 1.5]})

    # ── Histograma ──
    ax = axes[0]
    for mun_id, nome in MUNICIPIOS.items():
        dm = df[df['municipio_id'] == mun_id]
        ax.hist(dm['casos_confirmados'], bins=50, alpha=0.5,
                color=CORES[mun_id], label=nome, edgecolor='white')
    ax.set_xlabel('Casos confirmados (semanal)')
    ax.set_ylabel('Frequência')
    ax.set_title('Distribuição original', fontweight='bold')
    ax.legend()

    # Inset com log1p
    axins = ax.inset_axes([0.42, 0.42, 0.52, 0.52])
    for mun_id, nome in MUNICIPIOS.items():
        dm = df[df['municipio_id'] == mun_id]
        axins.hist(np.log1p(dm['casos_confirmados']), bins=40, alpha=0.5,
                   color=CORES[mun_id], edgecolor='white')
    axins.set_title('Transformação log(1+x)', fontsize=8, fontweight='bold')
    axins.tick_params(labelsize=7)
    axins.set_xlabel('log(1 + casos)', fontsize=7)

    # ── Boxplot por ano ──
    ax = axes[1]
    df_plot = df.copy()
    df_plot['ano'] = df_plot['data_se'].dt.year
    df_plot['municipio'] = df_plot['municipio_id'].map(MUNICIPIOS)

    sns.boxplot(
        data=df_plot, x='ano', y='casos_confirmados',
        hue='municipio', ax=ax,
        palette=[CORES[5103403], CORES[5108402]],
        fliersize=2, linewidth=0.8,
    )
    ax.set_xlabel('Ano')
    ax.set_ylabel('Casos confirmados (semanal)')
    ax.set_title('Distribuição por ano', fontweight='bold')
    ax.legend(title='', loc='upper right')

    fig.suptitle(
        'Distribuição de Casos Confirmados — Cuiabá e Várzea Grande (2018–2025)',
        fontsize=13, fontweight='bold', y=1.03,
    )
    plt.tight_layout()

    # Imprimir coeficiente de variação
    print("\n  Coeficiente de variação (CV = σ/μ):")
    for mun_id, nome in MUNICIPIOS.items():
        dm = df[df['municipio_id'] == mun_id]['casos_confirmados']
        cv = dm.std() / dm.mean()
        print(f"    {nome}: CV = {cv:.2f} ({cv*100:.0f}%)")

    return salvar_figura(fig, 'fig05_distribuicao_casos.png')


def main():
    aplicar_estilo()
    df = carregar_gold()

    print("\n📊 Gerando gráficos de sazonalidade e distribuição...")
    plot_perfil_sazonal(df)
    plot_distribuicao_casos(df)

    print("\n✅ 03_perfil_sazonal concluído!")
    print("─" * 40)


if __name__ == '__main__':
    main()