"""
===============================================================================
07_vigilancia_notificacao.py — Indicadores de Vigilância e Notificação
===============================================================================
Análise:
  - Razão casos_estimados / casos_confirmados ao longo do tempo
    (proxy de subnotificação — se cai, a vigilância melhorou)
  - Rt (número reprodutivo) e prob_rt_maior_1 por município
  - Nível de alerta do InfoDengue comparado entre municípios
  - Incidência por 100k habitantes — normaliza pela população
  - Sincronicidade dos surtos entre Cuiabá e Várzea Grande

Contexto:
  Cuiabá e Várzea Grande são municípios conurbados, separados pelo Rio Cuiabá
  (~200m de largura). Compartilham clima, bioma e dinâmica urbana, mas apresentam
  padrões epidemiológicos distintos. Esta análise investiga se as diferenças são
  reais ou refletem viés de vigilância/notificação.

Referências:
  - Codeco et al. (2018) — InfoDengue: nowcasting e Rt para dengue Brasil
  - Bastos et al. (2019) — subnotificação e ajuste por atraso de notificação
  - Lowe et al. (2021) — fatores socioeconômicos na heterogeneidade espacial

Saída:
  - reports/eda/fig14_razao_nowcasting.png
  - reports/eda/fig15_rt_comparativo.png
  - reports/eda/fig16_incidencia_100k.png
  - reports/eda/fig17_sincronicidade_surtos.png
===============================================================================
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy import stats

from config_eda import (
    carregar_gold, salvar_figura, aplicar_estilo,
    MUNICIPIOS, CORES,
)


def plot_razao_nowcasting(df):
    """
    Razão casos_estimados / casos_confirmados ao longo do tempo.
    Proxy para avaliar a qualidade da vigilância epidemiológica.

    Interpretação:
      - Razão > 1: subnotificação (InfoDengue estima mais do que é confirmado)
      - Razão ≈ 1: vigilância captando bem
      - Razão < 1: sobrenotificação ou casos descartados após confirmação
      - Queda na razão ao longo do tempo: melhoria na captação
    """
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    for ax, (mun_id, nome) in zip(axes, MUNICIPIOS.items()):
        dm = df[df['municipio_id'] == mun_id].copy()

        # Evitar divisão por zero
        dm['razao_nowcast'] = np.where(
            dm['casos_confirmados'] > 0,
            dm['casos_estimados'] / dm['casos_confirmados'],
            np.nan
        )

        cor = CORES[mun_id]

        # Razão bruta
        ax.scatter(dm['data_se'], dm['razao_nowcast'],
                   alpha=0.3, s=8, color=cor, edgecolors='none')

        # Média móvel 8 semanas para suavizar
        mm8 = dm['razao_nowcast'].rolling(8, center=True, min_periods=4).median()
        ax.plot(dm['data_se'], mm8, color=cor, linewidth=2,
                label=f'{nome} (mediana móvel 8 SE)')

        # Linha de referência
        ax.axhline(1.0, color='black', linestyle='--', linewidth=0.8,
                   alpha=0.5, label='Razão = 1 (sem subnotificação)')

        ax.set_ylabel('Casos estimados /\nCasos confirmados')
        ax.set_title(nome, fontweight='bold', loc='left')
        ax.legend(loc='upper right', fontsize=8)
        ax.set_ylim(0, max(5, dm['razao_nowcast'].quantile(0.95) * 1.2))

    axes[1].xaxis.set_major_locator(mdates.YearLocator())
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    axes[1].set_xlabel('Ano')

    fig.suptitle(
        'Razão Nowcasting — Casos Estimados / Casos Confirmados\n'
        'Proxy de subnotificação (InfoDengue, Codeco et al. 2018)',
        fontsize=13, fontweight='bold', y=1.03,
    )
    plt.tight_layout()

    # Estatísticas por período
    print("\n  Razão nowcasting (mediana por período):")
    for mun_id, nome in MUNICIPIOS.items():
        dm = df[df['municipio_id'] == mun_id].copy()
        dm['razao_nowcast'] = np.where(
            dm['casos_confirmados'] > 0,
            dm['casos_estimados'] / dm['casos_confirmados'],
            np.nan
        )
        dm['periodo'] = pd.cut(
            dm['data_se'].dt.year,
            bins=[2017, 2020, 2023, 2027],
            labels=['2018-2020', '2021-2023', '2024-2026']
        )
        for periodo in ['2018-2020', '2021-2023', '2024-2026']:
            subset = dm[dm['periodo'] == periodo]['razao_nowcast']
            mediana = subset.median()
            print(f"    {nome:15s} | {periodo}: mediana = {mediana:.2f}")

    return salvar_figura(fig, 'fig14_razao_nowcasting.png')


def plot_rt_comparativo(df):
    """
    Rt (número reprodutivo efetivo) e probabilidade Rt > 1.
    Rt > 1 indica epidemia em expansão.

    Nota: usamos rt_index_lag1 e prob_rt_maior_1_lag1 (lagados 1 SE)
    porque são assim que entram no modelo. O lag de 1 SE é operacional
    (dados publicados com atraso).
    """
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    # ── Rt ──
    ax = axes[0]
    for mun_id, nome in MUNICIPIOS.items():
        dm = df[df['municipio_id'] == mun_id].copy()
        cor = CORES[mun_id]

        ax.plot(dm['data_se'], dm['rt_index_lag1'],
                color=cor, linewidth=0.8, alpha=0.7, label=nome)

    ax.axhline(1.0, color='red', linestyle='--', linewidth=1, alpha=0.8,
               label='Rt = 1 (limiar epidêmico)')
    ax.fill_between(df['data_se'].unique(),
                    1.0, ax.get_ylim()[1] if ax.get_ylim()[1] > 1 else 2,
                    alpha=0.05, color='red')
    ax.set_ylabel('Rt (número\nreprodutivo)')
    ax.set_title('Número Reprodutivo Efetivo (Rt)', fontweight='bold', loc='left')
    ax.legend(loc='upper right', fontsize=8, ncol=3)

    # ── Prob Rt > 1 ──
    ax = axes[1]
    for mun_id, nome in MUNICIPIOS.items():
        dm = df[df['municipio_id'] == mun_id].copy()
        cor = CORES[mun_id]

        ax.fill_between(dm['data_se'], dm['prob_rt_maior_1_lag1'],
                        alpha=0.3, color=cor)
        ax.plot(dm['data_se'], dm['prob_rt_maior_1_lag1'],
                color=cor, linewidth=0.8, label=nome)

    ax.axhline(0.5, color='orange', linestyle='--', linewidth=0.8, alpha=0.7,
               label='P(Rt>1) = 50%')
    ax.set_ylabel('P(Rt > 1)')
    ax.set_title('Probabilidade de Rt > 1', fontweight='bold', loc='left')
    ax.legend(loc='upper right', fontsize=8)
    ax.set_ylim(0, 1.05)

    axes[1].xaxis.set_major_locator(mdates.YearLocator())
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    axes[1].set_xlabel('Ano')

    fig.suptitle(
        'Indicadores Epidemiológicos — Rt e P(Rt > 1) por Município\n'
        'Fonte: InfoDengue (lag 1 SE)',
        fontsize=13, fontweight='bold', y=1.03,
    )
    plt.tight_layout()

    # Resumo: semanas com Rt > 1
    print("\n  Semanas com Rt > 1 (epidemia ativa):")
    for mun_id, nome in MUNICIPIOS.items():
        dm = df[df['municipio_id'] == mun_id]
        n_total = len(dm.dropna(subset=['rt_index_lag1']))
        n_acima = (dm['rt_index_lag1'] > 1).sum()
        pct = n_acima / n_total * 100 if n_total > 0 else 0
        print(f"    {nome:15s}: {n_acima}/{n_total} semanas ({pct:.1f}%)")

    return salvar_figura(fig, 'fig15_rt_comparativo.png')


def plot_incidencia_100k(df):
    """
    Incidência por 100 mil habitantes — normaliza pela população.
    Permite comparação justa entre Cuiabá (~620k) e Várzea Grande (~290k).
    """
    fig, axes = plt.subplots(2, 1, figsize=(14, 7))

    # ── Série temporal de incidência ──
    ax = axes[0]
    for mun_id, nome in MUNICIPIOS.items():
        dm = df[df['municipio_id'] == mun_id].copy()
        cor = CORES[mun_id]

        ax.fill_between(dm['data_se'], dm['incidencia_100k'],
                        alpha=0.25, color=cor)
        ax.plot(dm['data_se'], dm['incidencia_100k'],
                color=cor, linewidth=0.8, label=nome)

    ax.set_ylabel('Incidência\n(por 100 mil hab.)')
    ax.set_title('Incidência Semanal por 100 mil Habitantes',
                 fontweight='bold', loc='left')
    ax.legend(loc='upper right')
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))

    # ── Acumulado anual por 100k ──
    ax = axes[1]
    df_plot = df.copy()
    df_plot['ano'] = df_plot['data_se'].dt.year

    for mun_id, nome in MUNICIPIOS.items():
        dm = df_plot[df_plot['municipio_id'] == mun_id]
        anual = dm.groupby('ano')['incidencia_100k'].sum()
        cor = CORES[mun_id]
        ax.plot(anual.index, anual.values, 'o-',
                color=cor, linewidth=2, markersize=6, label=nome)

        for ano, val in anual.items():
            ax.annotate(f'{val:.0f}', xy=(ano, val),
                        xytext=(0, 8), textcoords='offset points',
                        ha='center', fontsize=7, color=cor, fontweight='bold')
    ax.set_xticks(list(range(df_plot['ano'].min(), df_plot['ano'].max() + 1)))
    ax.set_ylabel('Incidência acumulada\n(por 100 mil hab./ano)')
    ax.set_xlabel('Ano')
    ax.set_title('Incidência Acumulada Anual', fontweight='bold', loc='left')
    ax.legend(loc='upper left')

    fig.suptitle(
        'Incidência de Dengue por 100 mil Habitantes\n'
        'Normaliza a comparação entre Cuiabá (~620k) e Várzea Grande (~290k)',
        fontsize=13, fontweight='bold', y=1.03,
    )
    plt.tight_layout()

    # Resumo
    print("\n  Incidência acumulada anual (por 100k hab.):")
    for mun_id, nome in MUNICIPIOS.items():
        dm = df_plot[df_plot['municipio_id'] == mun_id]
        anual = dm.groupby('ano')['incidencia_100k'].sum()
        for ano, val in anual.items():
            print(f"    {nome:15s} | {ano}: {val:.1f} / 100k")

    return salvar_figura(fig, 'fig16_incidencia_100k.png')


def plot_sincronicidade(df):
    """
    Análise de sincronicidade entre os surtos de Cuiabá e Várzea Grande.
    Cross-correlation com lag para verificar se um município lidera o outro.
    """
    pivot = df.pivot_table(
        index='data_se',
        columns='municipio_id',
        values='casos_confirmados',
    ).dropna()

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # ── Séries sobrepostas normalizadas (z-score) ──
    ax = axes[0]
    for mun_id, nome in MUNICIPIOS.items():
        serie = pivot[mun_id]
        serie_z = (serie - serie.mean()) / serie.std()
        ax.plot(pivot.index, serie_z,
                color=CORES[mun_id], linewidth=0.8, alpha=0.7, label=nome)

    ax.set_ylabel('Casos (z-score)')
    ax.set_xlabel('Ano')
    ax.set_title('Séries Normalizadas Sobrepostas', fontweight='bold')
    ax.legend(loc='upper right')
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))

    # ── Cross-correlation ──
    ax = axes[1]
    max_lag = 12

    cuiaba = pivot[5103403].values
    vg = pivot[5108402].values

    correlacoes = []
    lags_range = range(-max_lag, max_lag + 1)
    for lag in lags_range:
        if lag == 0:
            c = np.corrcoef(cuiaba, vg)[0, 1]
        elif lag > 0:
            c = np.corrcoef(cuiaba[:-lag], vg[lag:])[0, 1]
        else:
            c = np.corrcoef(cuiaba[-lag:], vg[:lag])[0, 1]
        correlacoes.append(c)

    ax.bar(list(lags_range), correlacoes, color='#34495e', alpha=0.7,
           edgecolor='white')

    # Marcar lag de máxima correlação
    lag_max = list(lags_range)[np.argmax(correlacoes)]
    corr_max = max(correlacoes)
    ax.bar(lag_max, corr_max, color='#e74c3c', alpha=0.9, edgecolor='white')

    ci = 1.96 / np.sqrt(len(cuiaba))
    ax.axhline(ci, color='gray', linestyle='--', linewidth=0.5)
    ax.axhline(-ci, color='gray', linestyle='--', linewidth=0.5)

    ax.set_xlabel('Lag (semanas)\n← VG lidera | Cuiabá lidera →')
    ax.set_ylabel('Correlação cruzada')
    ax.set_title(f'Cross-Correlation (lag máx = {lag_max}, r = {corr_max:.3f})',
                 fontweight='bold')

    fig.suptitle(
        'Sincronicidade dos Surtos — Cuiabá × Várzea Grande\n'
        'Municípios conurbados separados pelo Rio Cuiabá (~200m)',
        fontsize=13, fontweight='bold', y=1.04,
    )
    plt.tight_layout()

    # Interpretação
    if lag_max == 0:
        print("\n  Sincronicidade: surtos simultâneos (lag 0)")
    elif lag_max > 0:
        print(f"\n  Cuiabá lidera Várzea Grande em {lag_max} semana(s)")
    else:
        print(f"\n  Várzea Grande lidera Cuiabá em {abs(lag_max)} semana(s)")
    print(f"  Correlação máxima: r = {corr_max:.4f}")

    # Correlação por período
    print("\n  Correlação por período:")
    for periodo, (inicio, fim) in {'2018-2020': ('2018', '2020'),
                                    '2021-2023': ('2021', '2023'),
                                    '2024-2026': ('2024', '2026')}.items():
        mask = (pivot.index >= inicio) & (pivot.index < str(int(fim) + 1))
        subset = pivot[mask]
        if len(subset) > 10:
            r = subset[5103403].corr(subset[5108402])
            print(f"    {periodo}: r = {r:.3f}")

    return salvar_figura(fig, 'fig17_sincronicidade_surtos.png')


def main():
    aplicar_estilo()
    df = carregar_gold()

    print("\n📊 Gerando análises de vigilância e notificação...")
    plot_razao_nowcasting(df)
    plot_rt_comparativo(df)
    plot_incidencia_100k(df)
    plot_sincronicidade(df)

    print("\n✅ 07_vigilancia_notificacao concluído!")
    print("─" * 40)


if __name__ == '__main__':
    main()