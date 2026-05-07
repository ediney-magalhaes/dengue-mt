"""
===============================================================================
06_analise_componentes.py — Análise de Componentes Principais (PCA)
===============================================================================
Análise:
  - PCA das features do modelo — quantas dimensões independentes existem?
  - Variância explicada acumulada (scree plot)
  - Biplot dos 2 primeiros componentes — agrupamento natural das features
  - Loadings: quais features dominam cada componente
  - Comparação da estrutura dimensional entre municípios

Referências:
  - Jolliffe & Cadima (2016) — Principal component analysis: a review
  - Kaur et al. (2023) — PCA em dados epidemiológicos espaço-temporais
  - Sebastianelli et al. (2024) — redução dimensional para dengue Brasil

Saída:
  - reports/eda/fig11_pca_variancia_explicada.png
  - reports/eda/fig12_pca_biplot.png
  - reports/eda/fig13_pca_loadings.png
===============================================================================
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

from config_eda import (
    carregar_gold, salvar_figura, aplicar_estilo,
    MUNICIPIOS, CORES, COLS_METADATA,
    FEATURES_TEMPERATURA, FEATURES_PRECIP_UMIDADE,
    FEATURES_ONI, FEATURES_MODIS, FEATURES_TRENDS,
    FEATURES_AUTOREGRESSIVO, FEATURES_EPIDEMIO,
    FEATURES_MEDIAS_MOVEIS,
)


# Mapeamento feature → grupo (para colorir no biplot)
def _grupo_da_feature(feat):
    """Retorna o grupo temático de uma feature."""
    if feat in FEATURES_TEMPERATURA:
        return 'Temperatura'
    elif feat in FEATURES_PRECIP_UMIDADE:
        return 'Precip/Umidade'
    elif feat in FEATURES_MEDIAS_MOVEIS:
        return 'Médias Móveis'
    elif feat in FEATURES_ONI:
        return 'ONI/ENSO'
    elif feat in FEATURES_MODIS:
        return 'MODIS'
    elif feat in FEATURES_TRENDS:
        return 'Trends'
    elif feat in FEATURES_AUTOREGRESSIVO:
        return 'Autoregressivo'
    elif feat in FEATURES_EPIDEMIO:
        return 'Epidemiológico'
    else:
        return 'Outro'


CORES_GRUPO = {
    'Temperatura':    '#e74c3c',
    'Precip/Umidade': '#3498db',
    'Médias Móveis':  '#9b59b6',
    'ONI/ENSO':       '#2ecc71',
    'MODIS':          '#f39c12',
    'Trends':         '#e67e22',
    'Autoregressivo': '#1abc9c',
    'Epidemiológico': '#34495e',
    'Outro':          '#95a5a6',
}


def preparar_features(df):
    """Seleciona features numéricas do modelo e padroniza (z-score)."""
    drop_cols = COLS_METADATA + [
        'casos_confirmados', 'casos_estimados', 'incidencia_100k',
    ]
    features = [c for c in df.columns if c not in drop_cols]
    df_feat = df[features].select_dtypes(include=[np.number])

    # Remover colunas com muitos nulos (>20%) para PCA robusto
    pct_nulos = df_feat.isnull().mean()
    cols_ok = pct_nulos[pct_nulos < 0.20].index.tolist()
    df_feat = df_feat[cols_ok]

    # Dropna das linhas restantes
    df_clean = df_feat.dropna()

    # Padronização z-score (essencial para PCA)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df_clean)

    print(f"\n  Features selecionadas para PCA: {len(cols_ok)}")
    print(f"  Registros após dropna: {len(df_clean)} / {len(df)}")

    return X_scaled, cols_ok, df_clean.index


def plot_variancia_explicada(X_scaled, feature_names):
    """
    Scree plot — variância explicada por componente.
    Responde: quantas dimensões independentes existem nos dados?
    """
    pca = PCA()
    pca.fit(X_scaled)

    var_explicada = pca.explained_variance_ratio_
    var_acumulada = np.cumsum(var_explicada)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Scree plot
    ax = axes[0]
    n_show = min(20, len(var_explicada))
    ax.bar(range(1, n_show + 1), var_explicada[:n_show] * 100,
           color='#3498db', alpha=0.7, edgecolor='white')
    ax.plot(range(1, n_show + 1), var_explicada[:n_show] * 100,
            'o-', color='#2c3e50', markersize=5, linewidth=1.5)
    ax.set_xlabel('Componente Principal')
    ax.set_ylabel('Variância Explicada (%)')
    ax.set_title('Scree Plot', fontweight='bold')
    ax.set_xticks(range(1, n_show + 1))

    # Variância acumulada
    ax = axes[1]
    ax.plot(range(1, len(var_acumulada) + 1), var_acumulada * 100,
            'o-', color='#2c3e50', markersize=3, linewidth=1.5)
    ax.fill_between(range(1, len(var_acumulada) + 1),
                    var_acumulada * 100, alpha=0.1, color='#3498db')

    # Linhas de referência
    for pct in [80, 90, 95]:
        n_comp = np.argmax(var_acumulada >= pct / 100) + 1
        ax.axhline(pct, color='gray', linestyle='--', linewidth=0.5, alpha=0.7)
        ax.axvline(n_comp, color='gray', linestyle=':', linewidth=0.5, alpha=0.7)
        ax.annotate(f'{pct}% → {n_comp} PC',
                    xy=(n_comp, pct), xytext=(n_comp + 1, pct - 3),
                    fontsize=8, color='#e74c3c', fontweight='bold')

    ax.set_xlabel('Número de Componentes')
    ax.set_ylabel('Variância Acumulada (%)')
    ax.set_title('Variância Acumulada', fontweight='bold')
    ax.set_xlim(1, len(var_acumulada))
    ax.set_ylim(0, 102)

    fig.suptitle(
        f'Análise de Componentes Principais — {len(feature_names)} Features do Gold v5\n'
        'Quantas dimensões independentes existem nos dados?',
        fontsize=13, fontweight='bold', y=1.04,
    )
    plt.tight_layout()

    # Imprimir resumo
    print("\n  Variância explicada por componente:")
    for i in range(min(10, len(var_explicada))):
        print(f"    PC{i+1}: {var_explicada[i]*100:.1f}%  (acum: {var_acumulada[i]*100:.1f}%)")

    for pct in [80, 90, 95]:
        n = np.argmax(var_acumulada >= pct / 100) + 1
        print(f"\n  → {pct}% da variância explicada com {n} de {len(feature_names)} componentes")

    return salvar_figura(fig, 'fig11_pca_variancia_explicada.png'), pca


def plot_biplot(X_scaled, feature_names, df, indices):
    """
    Biplot — projeção das observações e das features nos 2 primeiros PCs.
    Mostra como as features se agrupam e como os municípios se separam.
    """
    pca = PCA(n_components=2)
    scores = pca.fit_transform(X_scaled)

    # Loadings (correlação feature × componente)
    loadings = pca.components_.T * np.sqrt(pca.explained_variance_)

    fig, ax = plt.subplots(figsize=(12, 10))

    # Plotar observações coloridas por município
    mun_ids = df.loc[indices, 'municipio_id'].values
    for mun_id, nome in MUNICIPIOS.items():
        mask = mun_ids == mun_id
        ax.scatter(scores[mask, 0], scores[mask, 1],
                   c=CORES[mun_id], alpha=0.25, s=15,
                   label=nome, edgecolors='white', linewidth=0.2)

    # Plotar vetores das features (loadings)
    scale = 4  # Escalar para visibilidade
    for i, feat in enumerate(feature_names):
        grupo = _grupo_da_feature(feat)
        cor = CORES_GRUPO[grupo]

        ax.arrow(0, 0, loadings[i, 0] * scale, loadings[i, 1] * scale,
                 head_width=0.08, head_length=0.05,
                 fc=cor, ec=cor, alpha=0.7, linewidth=1)

        # Rótulo (só features com loadings relevantes)
        magnitude = np.sqrt(loadings[i, 0]**2 + loadings[i, 1]**2)
        if magnitude > np.percentile(
            [np.sqrt(loadings[j, 0]**2 + loadings[j, 1]**2)
             for j in range(len(feature_names))], 60
        ):
            ax.text(loadings[i, 0] * scale * 1.08,
                    loadings[i, 1] * scale * 1.08,
                    feat.replace('_lag', ' L').replace('_mm', ' MM'),
                    fontsize=6, color=cor, fontweight='bold', alpha=0.8)

    # Legenda dos grupos
    patches = [mpatches.Patch(color=cor, label=grupo, alpha=0.7)
               for grupo, cor in CORES_GRUPO.items()
               if grupo != 'Outro']
    leg1 = ax.legend(handles=patches, loc='upper left', fontsize=7,
                     title='Grupo de features', title_fontsize=8,
                     ncol=2, framealpha=0.9)
    ax.add_artist(leg1)

    # Legenda dos municípios
    ax.legend(loc='lower right', fontsize=9, framealpha=0.9)

    var1 = pca.explained_variance_ratio_[0] * 100
    var2 = pca.explained_variance_ratio_[1] * 100
    ax.set_xlabel(f'PC1 ({var1:.1f}% variância)')
    ax.set_ylabel(f'PC2 ({var2:.1f}% variância)')
    ax.set_title(
        'Biplot PCA — Features e Observações nos 2 Primeiros Componentes\n'
        'Vetores = direção e magnitude da contribuição de cada feature',
        fontweight='bold',
    )
    ax.axhline(0, color='gray', linewidth=0.3)
    ax.axvline(0, color='gray', linewidth=0.3)

    return salvar_figura(fig, 'fig12_pca_biplot.png')


def plot_loadings_top(X_scaled, feature_names):
    """
    Loadings dos 3 primeiros componentes — quais features dominam cada PC.
    """
    pca = PCA(n_components=5)
    pca.fit(X_scaled)

    fig, axes = plt.subplots(1, 3, figsize=(16, 7))

    for pc_idx in range(3):
        ax = axes[pc_idx]
        loadings = pca.components_[pc_idx]
        var_pct = pca.explained_variance_ratio_[pc_idx] * 100

        # Ordenar por magnitude absoluta
        ordem = np.argsort(np.abs(loadings))[::-1]
        top_n = 15  # Top 15 features

        feats_top = [feature_names[i] for i in ordem[:top_n]]
        vals_top = [loadings[i] for i in ordem[:top_n]]
        cores_top = [CORES_GRUPO[_grupo_da_feature(f)] for f in feats_top]

        # Barras horizontais
        y_pos = range(len(feats_top))
        ax.barh(y_pos, vals_top, color=cores_top, alpha=0.8,
                edgecolor='white', height=0.7)

        ax.set_yticks(y_pos)
        ax.set_yticklabels(
            [f.replace('_lag', ' L').replace('_mm', ' MM') for f in feats_top],
            fontsize=8,
        )
        ax.invert_yaxis()
        ax.set_xlabel('Loading')
        ax.set_title(f'PC{pc_idx + 1} ({var_pct:.1f}%)', fontweight='bold')
        ax.axvline(0, color='black', linewidth=0.5)

    fig.suptitle(
        'Top 15 Features por Componente Principal\n'
        'Cores = grupo temático da feature',
        fontsize=13, fontweight='bold', y=1.03,
    )
    plt.tight_layout()

    # Imprimir interpretação
    print("\n  Interpretação dos componentes:")
    for pc_idx in range(3):
        loadings = pca.components_[pc_idx]
        var_pct = pca.explained_variance_ratio_[pc_idx] * 100
        ordem = np.argsort(np.abs(loadings))[::-1]
        top3 = [feature_names[i] for i in ordem[:3]]
        print(f"    PC{pc_idx+1} ({var_pct:.1f}%): dominado por {', '.join(top3)}")

    return salvar_figura(fig, 'fig13_pca_loadings.png')


def main():
    aplicar_estilo()
    df = carregar_gold()

    print("\n📊 Preparando PCA...")
    X_scaled, feature_names, indices = preparar_features(df)

    print("\n📊 Gerando gráficos de PCA...")
    plot_variancia_explicada(X_scaled, feature_names)
    plot_biplot(X_scaled, feature_names, df, indices)
    plot_loadings_top(X_scaled, feature_names)

    print("\n✅ 06_analise_componentes concluído!")
    print("─" * 40)


if __name__ == '__main__':
    main()