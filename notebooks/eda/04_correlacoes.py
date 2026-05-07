"""
===============================================================================
04_correlacoes.py — Correlação Cruzada, Heatmap e Autocorrelação
===============================================================================
Análise:
  - Correlação cruzada (CCF) entre variáveis climáticas e casos com lags
  - Heatmap de correlação entre todas as features do modelo
  - Top correlações com o target (casos_confirmados)
  - ACF e PACF de casos confirmados

Referências:
  - Benedum et al. (2020) — lags precipitação 8-15 SE, temperatura 0-3 SE
  - Hii et al. (2012) — temperatura lag 2-4 SE, precipitação lag 1-3 SE
  - Choi et al. (2016) — temperatura e chuva lideram 8-10 semanas
  - Chen & Moraga (2025) — correlação cruzada clima × dengue

Saída:
  - reports/eda/fig06_correlacao_cruzada.png
  - reports/eda/fig07_heatmap_correlacao.png
  - reports/eda/fig08_autocorrelacao.png
===============================================================================
"""

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf

from config_eda import (
    carregar_gold, salvar_figura, aplicar_estilo,
    MUNICIPIOS, CORES, COLS_METADATA,
)


def plot_correlacao_cruzada(df):
    """
    Cross-correlation function (CCF) entre variáveis climáticas e casos.
    Usa features lag1 como proxy dos valores originais.
    A CCF revela o lag ótimo observado nos dados — deve ser comparado
    com os lags escolhidos no modelo (baseados na literatura).
    """
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))

    variaveis = {
        'temp_media_lag1':  'Temperatura média (°C)',
        'precip_lag1':      'Precipitação (mm)',
        'umidade_lag1':     'Umidade relativa (%)',
        'oni_lag4':         'ONI Index (ENSO)',
        'ndvi_lag2':        'NDVI (vegetação)',
        'trends_lag1':      'Google Trends',
    }

    max_lag = 20  # Até 20 SE

    for idx, (var, titulo) in enumerate(variaveis.items()):
        row, col = divmod(idx, 3)
        ax = axes[row, col]

        for mun_id, nome in MUNICIPIOS.items():
            dm = df[df['municipio_id'] == mun_id].copy()
            dm = dm.dropna(subset=[var, 'casos_confirmados'])

            # CCF: correlação de var(t) com casos(t+lag)
            correlacoes = []
            for lag in range(max_lag + 1):
                if lag == 0:
                    corr = dm[var].corr(dm['casos_confirmados'])
                else:
                    corr = (
                        dm[var].iloc[:-lag].reset_index(drop=True)
                        .corr(dm['casos_confirmados'].iloc[lag:].reset_index(drop=True))
                    )
                correlacoes.append(corr)

            ax.plot(range(max_lag + 1), correlacoes,
                    color=CORES[mun_id], linewidth=1.5, label=nome)

            # Marcar lag de máxima correlação
            lag_max = np.argmax(np.abs(correlacoes))
            ax.plot(lag_max, correlacoes[lag_max], 'o',
                    color=CORES[mun_id], markersize=5)

        # Intervalo de confiança 95%
        n = len(df[df['municipio_id'] == 5103403])
        ci = 1.96 / np.sqrt(n)
        ax.axhline(ci, color='gray', linestyle=':', linewidth=0.5)
        ax.axhline(-ci, color='gray', linestyle=':', linewidth=0.5)
        ax.axhline(0, color='black', linewidth=0.5)

        ax.set_title(titulo, fontweight='bold', fontsize=10)
        ax.set_xlabel('Lag (semanas)')
        if col == 0:
            ax.set_ylabel('Correlação de Pearson')

    axes[0, 0].legend(loc='upper right', fontsize=8)

    fig.suptitle(
        'Correlação Cruzada — Variáveis Climáticas × Casos de Dengue\n'
        'Ref: Benedum et al. (2020), Hii et al. (2012)',
        fontsize=13, fontweight='bold', y=1.03,
    )
    plt.tight_layout()

    # Imprimir lags ótimos
    print("\n  Lags de máxima correlação (|r|):")
    for var, titulo in variaveis.items():
        for mun_id, nome in MUNICIPIOS.items():
            dm = df[df['municipio_id'] == mun_id].dropna(subset=[var, 'casos_confirmados'])
            corrs = []
            for lag in range(max_lag + 1):
                if lag == 0:
                    c = dm[var].corr(dm['casos_confirmados'])
                else:
                    c = (dm[var].iloc[:-lag].reset_index(drop=True)
                         .corr(dm['casos_confirmados'].iloc[lag:].reset_index(drop=True)))
                corrs.append(c)
            lag_best = np.argmax(np.abs(corrs))
            print(f"    {titulo:30s} | {nome:15s} | lag={lag_best:2d} SE | r={corrs[lag_best]:+.3f}")

    return salvar_figura(fig, 'fig06_correlacao_cruzada.png')


def plot_heatmap_correlacao(df):
    """
    Heatmap de correlação entre features do modelo.
    Identifica multicolinearidade e agrupamentos naturais.
    """
    drop_cols = COLS_METADATA + ['casos_estimados', 'incidencia_100k']
    features = [c for c in df.columns if c not in drop_cols]
    df_feat = df[features].select_dtypes(include=[np.number])

    corr = df_feat.corr()

    fig, ax = plt.subplots(figsize=(18, 16))

    mask = np.triu(np.ones_like(corr, dtype=bool))
    sns.heatmap(
        corr, mask=mask, cmap='RdBu_r', center=0,
        vmin=-1, vmax=1, square=True,
        linewidths=0.3, linecolor='white',
        cbar_kws={'shrink': 0.6, 'label': 'Correlação de Pearson'},
        annot=False, ax=ax,
    )

    ax.set_title(
        'Matriz de Correlação — Features do Modelo Gold v5\n'
        f'{len(df_feat.columns)} features',
        fontsize=14, fontweight='bold', pad=20,
    )
    ax.tick_params(axis='both', labelsize=7)

    plt.tight_layout()

    # Top correlações com target
    print("\n  Top 15 correlações com casos_confirmados:")
    corr_abs = corr['casos_confirmados'].drop('casos_confirmados').abs().sort_values(ascending=False)
    for feat in corr_abs.head(15).index:
        val = corr['casos_confirmados'][feat]
        sinal = '+' if val > 0 else '-'
        print(f"    {sinal}{abs(val):.3f}  {feat}")

    # Pares altamente correlacionados (possível multicolinearidade)
    print("\n  Pares com |r| > 0.90 (multicolinearidade):")
    n_pares = 0
    for i in range(len(corr.columns)):
        for j in range(i + 1, len(corr.columns)):
            if abs(corr.iloc[i, j]) > 0.90:
                print(f"    {corr.columns[i]:30s} × {corr.columns[j]:30s} = {corr.iloc[i,j]:+.3f}")
                n_pares += 1
    if n_pares == 0:
        print("    Nenhum par com |r| > 0.90")

    return salvar_figura(fig, 'fig07_heatmap_correlacao.png')


def plot_autocorrelacao(df):
    """
    ACF e PACF — justifica lags autoregressivos no modelo.
    PACF indica os lags diretamente relevantes após remover efeitos intermediários.
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 8))

    for col, (mun_id, nome) in enumerate(MUNICIPIOS.items()):
        dm = df[df['municipio_id'] == mun_id]['casos_confirmados'].dropna()

        plot_acf(dm, lags=52, ax=axes[0, col],
                 title=f'{nome} — ACF (Autocorrelação)',
                 color=CORES[mun_id],
                 vlines_kwargs={'color': CORES[mun_id]})

        plot_pacf(dm, lags=52, ax=axes[1, col],
                  title=f'{nome} — PACF (Autocorrelação Parcial)',
                  color=CORES[mun_id],
                  vlines_kwargs={'color': CORES[mun_id]},
                  method='ywm')

    fig.suptitle(
        'Autocorrelação (ACF) e Autocorrelação Parcial (PACF) — Casos de Dengue\n'
        'Justifica uso de lags autoregressivos (lag 1-4 SE) como features',
        fontsize=13, fontweight='bold', y=1.03,
    )
    plt.tight_layout()

    return salvar_figura(fig, 'fig08_autocorrelacao.png')


def main():
    aplicar_estilo()
    df = carregar_gold()

    print("\n📊 Gerando gráficos de correlação...")
    plot_correlacao_cruzada(df)
    plot_heatmap_correlacao(df)
    plot_autocorrelacao(df)

    print("\n✅ 04_correlacoes concluído!")
    print("─" * 40)


if __name__ == '__main__':
    main()