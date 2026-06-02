"""
===============================================================================
04_shap_direct_cqr.py — Análise SHAP dos modelos Direct Multi-Step CQR
===============================================================================
Interpretabilidade dos 12 modelos LightGBM Direct CQR via SHAP.

Estratégia:
  - Calcula SHAP apenas para os modelos q50 (mediana) de cada horizonte
  - Gera análise global (ambos municípios) e por município separado
  - 4 horizontes: h=1, h=2, h=4, h=8 semanas à frente

Visualizações por horizonte (global + por município):
  1. Beeswarm plot  — ranking + direção do efeito
  2. Bar plot       — top 20 features por |SHAP| médio
  3. Dependence     — relações não-lineares das top 6 features
  4. Temporal       — importância SHAP por fase do ciclo epidêmico

Visualização comparativa (nova):
  5. Comparativo entre horizontes — como a importância muda de h=1 a h=8

Referências:
  - Lundberg & Lee (NeurIPS 2017) — SHAP original
  - Lundberg et al. (Nature MI 2020) — TreeSHAP
  - Romano et al. (2019) — Conformalized Quantile Regression
  - Rahman et al. (Health Sci Rep 2025) — SHAP + LightGBM para dengue
  - Taieb & Hyndman (2014) — Direct multi-step forecasting
  - ADR-024 — log1p/expm1 como par obrigatório
  - ADR-030 — Direct Multi-Step + CQR em produção

Saída:
  reports/shap/direct_cqr/
  ├── global/
  │   ├── fig01_h{h}_beeswarm.png       (4 arquivos)
  │   ├── fig02_h{h}_bar_top20.png      (4 arquivos)
  │   ├── fig03_h{h}_dependence.png     (4 arquivos)
  │   ├── fig04_h{h}_temporal.png       (4 arquivos)
  │   └── fig05_comparativo_horizontes.png
  ├── municipios/
  │   ├── fig01_h{h}_{mun}_beeswarm.png (8 arquivos)
  │   └── fig02_h{h}_{mun}_bar_top20.png (8 arquivos)
  └── dados/
      ├── shap_importance_h{h}.csv      (4 arquivos)
      ├── shap_importance_h{h}_{mun}.csv (8 arquivos)
      └── shap_importance_consolidado.csv

Uso:
  conda activate dengue-mt
  python notebooks/backtesting/04_shap_direct_cqr.py

Quando rodar novamente:
  Após cada retreino dos modelos (quando pipeline reportar "Retreino: executado")
===============================================================================
"""

import sys
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path

# ── Ajustar sys.path para importar src/ ──────────────────────────────────────
# O script fica em notebooks/backtesting/ → raiz é dois níveis acima
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
import joblib
import shap
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import datetime

from src.config import (
    HORIZONTES_DIRECT, MODELS_DIR,
    DIRECT_METADATA_PATH, model_direct_path,
)
from src.features.build_features import carregar_gold, build_features

# ── Diretórios de saída ───────────────────────────────────────────────────────
SHAP_DIR       = PROJECT_ROOT / 'reports' / 'shap' / 'direct_cqr'
DIR_GLOBAL     = SHAP_DIR / 'global'
DIR_MUNICIPIOS = SHAP_DIR / 'municipios'
DIR_DADOS      = SHAP_DIR / 'dados'

for d in [DIR_GLOBAL, DIR_MUNICIPIOS, DIR_DADOS]:
    d.mkdir(parents=True, exist_ok=True)

# ── Municípios ────────────────────────────────────────────────────────────────
MUNICIPIOS = {
    5103403: 'Cuiabá',
    5108402: 'Várzea Grande',
}

# ── Nomes legíveis para features ──────────────────────────────────────────────
FEATURE_LABELS = {
    # Epidemiológicas — momentum autoregressivo
    'casos_lag1':              'Casos (lag 1 SE)',
    'casos_lag2':              'Casos (lag 2 SE)',
    'casos_lag4':              'Casos (lag 4 SE)',
    'casos_mm4':               'Casos MM4',
    'casos_mm8':               'Casos MM8',
    'rt_index':                'Índice Rt',
    'prob_rt_acima_1':         'P(Rt > 1)',
    'nivel_alerta':            'Nível de alerta',
    'receptivo':               'Receptividade',
    'transmissao':             'Transmissão ativa',
    'notif_acum_4se':          'Notificações acum. 4 SE',
    'casos_mesmo_mes_ano_ant': 'Casos mesmo mês ano anterior',
    # Climáticas
    'temp_media':              'Temperatura média (°C)',
    'temp_max':                'Temperatura máxima (°C)',
    'temp_min':                'Temperatura mínima (°C)',
    'temp_amplitude':          'Amplitude térmica (°C)',
    'umidade_media':           'Umidade relativa (%)',
    'precipitacao':            'Precipitação (mm)',
    'precipitacao_mm4':        'Precipitação MM4',
    'radiacao_solar':          'Radiação solar (MJ/m²)',
    # ENSO
    'oni_index':               'ONI (El Niño/La Niña)',
    'fase_enso':               'Fase ENSO',
    # Infoveillance
    'trends_dengue':           'Google Trends',
    # Vegetação (MODIS)
    'ndvi':                    'NDVI',
    'ndwi':                    'NDWI',
    # Temporais
    'semana_do_ano':           'Semana do ano',
    'mes':                     'Mês',
    'populacao':               'População',
}

# ── Cores por grupo de feature ────────────────────────────────────────────────
def cor_feature(feat: str) -> str:
    if any(k in feat for k in ['ndvi', 'ndwi', 'evi']):
        return '#43A047'   # Vegetação = verde
    if any(k in feat for k in ['oni', 'fase_enso']):
        return '#FB8C00'   # ENSO = laranja
    if 'trends' in feat:
        return '#8E24AA'   # Infoveillance = roxo
    if any(k in feat for k in ['temp', 'umidade', 'precip', 'radiacao']):
        return '#1E88E5'   # Climático = azul
    if any(k in feat for k in ['casos', 'rt_index', 'prob_rt', 'nivel_alerta',
                                'receptivo', 'transmissao', 'notif_acum',
                                'populacao']):
        return '#E53935'   # Epidemiológico = vermelho
    return '#757575'       # Outros = cinza

LEGENDA_CORES = [
    mpatches.Patch(facecolor='#E53935', label='Epidemiológico'),
    mpatches.Patch(facecolor='#1E88E5', label='Climático'),
    mpatches.Patch(facecolor='#43A047', label='Vegetação (NDVI/NDWI)'),
    mpatches.Patch(facecolor='#FB8C00', label='ENSO (ONI)'),
    mpatches.Patch(facecolor='#8E24AA', label='Infoveillance'),
    mpatches.Patch(facecolor='#757575', label='Outros'),
]

def label(feat: str) -> str:
    return FEATURE_LABELS.get(feat, feat)

def renomear(cols: list) -> list:
    return [label(c) for c in cols]

# 1. CARREGAMENTO

def carregar_modelo(h: int) -> object:
    """Carrega modelo q50 para o horizonte h."""
    path = model_direct_path(h, 0.50)
    if not path.exists():
        raise FileNotFoundError(f"Modelo não encontrado: {path}")
    modelo = joblib.load(path)
    print(f"  ✅ Modelo carregado: {path.name}")
    return modelo


def preparar_dados(df: pd.DataFrame, h: int):
    """
    Prepara X e metadados para o horizonte h.
    Retorna X completo, municipio_ids e data_se para filtros.
    """
    df = df.copy()
    df['data_se'] = pd.to_datetime(df['data_se'])
    df = df.sort_values('data_se').reset_index(drop=True)

    # Target deslocado h semanas (para filtrar NaN no final)
    y_shifted = df.groupby('municipio_id')['casos_confirmados'].shift(-h)
    mask_valido = y_shifted.notna()

    X_full = build_features(df)
    X_h    = X_full[mask_valido].reset_index(drop=True)
    meta_h = df[mask_valido][['data_se', 'municipio_id']].reset_index(drop=True)

    return X_h, meta_h

# 2. CÁLCULO SHAP

def calcular_shap(modelo, X: pd.DataFrame) -> tuple:
    """
    Calcula SHAP values via TreeExplainer (exato para árvores).

    Nota sobre escala: modelo foi treinado em log1p(casos).
    Os SHAP values estão no espaço log1p — interpretamos como
    'contribuição relativa de cada feature na previsão transformada'.
    Para o dashboard e artigo, isso é suficiente: o ranking de
    importância não muda com a transformação monotônica expm1.

    Referência: Lundberg et al. (Nature MI 2020) — TreeSHAP
    """
    explainer   = shap.TreeExplainer(modelo)
    shap_values = explainer.shap_values(X)

    # Importância média absoluta
    importancia = np.abs(shap_values).mean(axis=0)
    df_imp = pd.DataFrame({
        'feature':       X.columns.tolist(),
        'shap_mean_abs': importancia,
    }).sort_values('shap_mean_abs', ascending=False).reset_index(drop=True)

    print(f"    SHAP matrix: {shap_values.shape} | "
          f"Base value: {explainer.expected_value:.4f} (log1p)")

    return shap_values, explainer, df_imp

# 3. VISUALIZAÇÕES

def plot_beeswarm(shap_values, X, titulo: str, path: Path):
    """Fig 1 — Beeswarm: ranking global com direção do efeito."""
    fig, ax = plt.subplots(figsize=(12, 10))
    shap.summary_plot(
        shap_values,
        features=X,
        feature_names=renomear(X.columns.tolist()),
        max_display=20,
        show=False,
        plot_size=None,
    )
    plt.title(titulo, fontsize=13, fontweight='bold', pad=12)
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"    ✅ {path.name}")


def plot_bar(df_imp: pd.DataFrame, titulo: str, path: Path):
    """Fig 2 — Bar plot top 20 por |SHAP| médio."""
    top20 = df_imp.head(20).copy()
    top20['label'] = renomear(top20['feature'].tolist())
    cores = [cor_feature(f) for f in top20['feature']]

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.barh(
        range(len(top20) - 1, -1, -1),
        top20['shap_mean_abs'].values,
        color=cores,
        height=0.7,
    )
    ax.set_yticks(range(len(top20) - 1, -1, -1))
    ax.set_yticklabels(top20['label'].values, fontsize=9)
    ax.set_xlabel('|SHAP| médio (impacto na previsão em log1p)')
    ax.set_title(titulo, fontsize=13, fontweight='bold')
    ax.legend(handles=LEGENDA_CORES, loc='lower right', fontsize=8)
    plt.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"    ✅ {path.name}")


def plot_dependence(shap_values, X, df_imp: pd.DataFrame,
                    titulo: str, path: Path):
    """
    Fig 3 — Dependence plots das top 6 features.

    Nota: shap.dependence_plot não tolera NaN nas features de interação
    automática. Imputamos a mediana antes de passar o array — apenas para
    fins de visualização, sem alterar os SHAP values já calculados.
    """
    top6   = df_imp.head(6)['feature'].tolist()
    labels = renomear(top6)

    # Imputar NaN com mediana — somente para o plot de dependência
    X_plot = X.copy()
    for col in X_plot.columns:
        if X_plot[col].isna().any():
            X_plot[col] = X_plot[col].fillna(X_plot[col].median())
    X_arr = X_plot.values.astype(float)

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()

    for i, (feat, lbl) in enumerate(zip(top6, labels)):
        idx = X.columns.tolist().index(feat)
        shap.dependence_plot(
            idx,
            shap_values,
            features=X_arr,
            feature_names=renomear(X.columns.tolist()),
            ax=axes[i],
            show=False,
        )
        axes[i].set_title(lbl, fontsize=11, fontweight='bold')

    fig.suptitle(titulo, fontsize=13, fontweight='bold', y=1.01)
    plt.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"    ✅ {path.name}")


def plot_temporal(shap_values, X, meta: pd.DataFrame,
                  df_imp: pd.DataFrame, titulo: str, path: Path):
    """
    Fig 4 — Importância SHAP por fase do ciclo epidêmico.

    3 fases calibradas para MT (clima tropical semiúmido):
      - Pré-surto (out-dez): período chuvoso começa, condições se formando
      - Surto (jan-mai):     pico epidêmico — alto calor + alta umidade
      - Entressafra (jun-set): período seco, casos mínimos
    """
    top10     = df_imp.head(10)['feature'].tolist()
    top10_idx = [X.columns.tolist().index(f) for f in top10]

    meses = meta['data_se'].dt.month.values
    fases = np.where(
        (meses >= 1) & (meses <= 5),  'Surto (Jan-Mai)',
        np.where(
            (meses >= 6) & (meses <= 9), 'Entressafra (Jun-Set)',
            'Pré-surto (Out-Dez)'
        )
    )

    fases_ordem = ['Pré-surto (Out-Dez)', 'Surto (Jan-Mai)', 'Entressafra (Jun-Set)']
    cores_fase  = {
        'Pré-surto (Out-Dez)':   '#FF9800',
        'Surto (Jan-Mai)':        '#F44336',
        'Entressafra (Jun-Set)':  '#4CAF50',
    }

    dados_fase = []
    for fase in fases_ordem:
        mask = fases == fase
        if mask.sum() == 0:
            continue
        for feat, idx in zip(top10, top10_idx):
            dados_fase.append({
                'fase':       fase,
                'feature':    feat,
                'label':      label(feat),
                'shap_medio': float(np.abs(shap_values[mask, idx]).mean()),
            })

    df_fase = pd.DataFrame(dados_fase)

    fig, ax = plt.subplots(figsize=(14, 7))
    bar_width = 0.25
    x = np.arange(len(top10))

    for i, fase in enumerate(fases_ordem):
        df_f = df_fase[df_fase['fase'] == fase].set_index('feature')
        vals = [df_f.loc[f, 'shap_medio'] if f in df_f.index else 0.0 for f in top10]
        ax.bar(x + i * bar_width, vals, width=bar_width,
               color=cores_fase[fase], label=fase, alpha=0.85)

    ax.set_xticks(x + bar_width)
    ax.set_xticklabels(renomear(top10), rotation=45, ha='right', fontsize=9)
    ax.set_ylabel('|SHAP| médio')
    ax.set_title(titulo, fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    plt.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"    ✅ {path.name}")


def plot_comparativo_horizontes(resultados: dict, path: Path):
    """
    Fig 5 — Comparativo de importância SHAP entre horizontes (h=1,2,4,8).

    Mostra como o modelo muda de estratégia conforme o horizonte aumenta:
    - h=1: domínio do momentum autoregressivo (casos_lag1, casos_mm4)
    - h=8: maior peso relativo de features climáticas e sazonais

    Este padrão é consistente com a literatura de previsão multi-step
    (Taieb & Hyndman, 2014): modelos de horizonte longo dependem menos
    de lags recentes e mais de padrões estruturais.
    """
    # Coletar top 15 features globais (união dos horizontes)
    todas_features = set()
    for h, dados in resultados.items():
        todas_features.update(dados['df_imp']['feature'].head(15).tolist())
    todas_features = sorted(todas_features)

    # Montar matriz de importância: features × horizontes
    matrix = {}
    for h, dados in resultados.items():
        df_imp = dados['df_imp'].set_index('feature')
        matrix[h] = {f: df_imp.loc[f, 'shap_mean_abs']
                     if f in df_imp.index else 0.0
                     for f in todas_features}

    df_matrix = pd.DataFrame(matrix).T  # linhas = horizontes, colunas = features
    df_matrix = df_matrix[sorted(todas_features,
                                 key=lambda f: df_matrix[f].max(),
                                 reverse=True)]

    # Normalizar por feature (0-1) para comparação relativa
    df_norm = df_matrix.div(df_matrix.max(axis=0).replace(0, 1), axis=1)

    fig, axes = plt.subplots(1, 2, figsize=(20, 8))

    # Painel A: valores absolutos
    ax = axes[0]
    x = np.arange(len(todas_features))
    bar_width = 0.2
    cores_h = {1: '#1565C0', 2: '#1E88E5', 4: '#FB8C00', 8: '#E53935'}

    for i, h in enumerate([1, 2, 4, 8]):
        vals = [matrix[h][f] for f in df_matrix.columns]
        ax.bar(x + i * bar_width, vals, width=bar_width,
               color=cores_h[h], label=f'h={h} SE', alpha=0.85)

    ax.set_xticks(x + bar_width * 1.5)
    ax.set_xticklabels(renomear(df_matrix.columns.tolist()),
                       rotation=45, ha='right', fontsize=8)
    ax.set_ylabel('|SHAP| médio (log1p)')
    ax.set_title('Importância SHAP por horizonte\n(valores absolutos)',
                 fontsize=12, fontweight='bold')
    ax.legend(fontsize=10)

    # Painel B: importância relativa normalizada (heatmap)
    ax = axes[1]
    im = ax.imshow(df_norm.values, aspect='auto', cmap='YlOrRd',
                   vmin=0, vmax=1)
    ax.set_xticks(range(len(df_matrix.columns)))
    ax.set_xticklabels(renomear(df_matrix.columns.tolist()),
                       rotation=45, ha='right', fontsize=8)
    ax.set_yticks(range(4))
    ax.set_yticklabels([f'h={h} SE' for h in [1, 2, 4, 8]], fontsize=10)
    ax.set_title('Importância relativa normalizada\n(vermelho = mais importante no horizonte)',
                 fontsize=12, fontweight='bold')
    plt.colorbar(im, ax=ax, label='Importância relativa (0-1)')

    fig.suptitle(
        'Como o modelo muda de estratégia conforme o horizonte aumenta\n'
        'Análise SHAP — Direct Multi-Step CQR (q50) | Dengue MT',
        fontsize=14, fontweight='bold', y=1.02
    )
    plt.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  ✅ {path.name}")

# 4. ANÁLISE POR MUNICÍPIO

def analisar_municipio(shap_values, X, meta: pd.DataFrame,
                       municipio_id: int, nome: str, h: int):
    """Filtra dados de um município e gera figuras beeswarm + bar."""
    mask = meta['municipio_id'].values == municipio_id
    if mask.sum() < 20:
        print(f"    ⚠️  {nome}: apenas {mask.sum()} registros — pulando")
        return None

    sv_mun = shap_values[mask]
    X_mun  = X[mask].reset_index(drop=True)

    imp_mun = np.abs(sv_mun).mean(axis=0)
    df_imp_mun = pd.DataFrame({
        'feature':       X.columns.tolist(),
        'shap_mean_abs': imp_mun,
    }).sort_values('shap_mean_abs', ascending=False).reset_index(drop=True)

    slug = nome.lower().replace(' ', '_').replace('á', 'a').replace('ã', 'a')

    # Beeswarm por município
    plot_beeswarm(
        sv_mun, X_mun,
        titulo=f'SHAP Beeswarm — h={h} SE | {nome}\n'
               f'Top 20 features por importância e direção do efeito',
        path=DIR_MUNICIPIOS / f'fig01_h{h}_{slug}_beeswarm.png',
    )

    # Bar por município
    plot_bar(
        df_imp_mun,
        titulo=f'Top 20 Features — h={h} SE | {nome}\n'
               f'Importância SHAP (Lundberg & Lee, 2017)',
        path=DIR_MUNICIPIOS / f'fig02_h{h}_{slug}_bar_top20.png',
    )

    # Salvar CSV por município
    df_imp_mun.to_csv(
        DIR_DADOS / f'shap_importance_h{h}_{slug}.csv', index=False
    )

    return df_imp_mun

# 5. MAIN

def main():
    print('=' * 65)
    print('ANÁLISE SHAP — Direct Multi-Step CQR (q50)')
    print('Lundberg & Lee (NeurIPS 2017) | Taieb & Hyndman (2014)')
    print(f'Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M")}')
    print('=' * 65)

    # ── 1. Carregar Gold ──────────────────────────────────────────────────────
    print('\n▶ Carregando Gold dataset...')
    df = carregar_gold()
    print(f'  Gold: {df.shape[0]} registros × {df.shape[1]} colunas')
    print(f'  Período: {df["data_se"].min()} → {df["data_se"].max()}')
    print(f'  Municípios: {df["municipio_id"].unique().tolist()}')

    # ── 2. Loop por horizonte ─────────────────────────────────────────────────
    resultados = {}  # armazena df_imp global por horizonte para o comparativo

    for h in HORIZONTES_DIRECT:
        print(f'\n{"─"*65}')
        print(f'▶ Horizonte h={h} SE (previsão {h} semanas à frente)')
        print(f'{"─"*65}')

        # Carregar modelo q50
        print(f'\n  Carregando modelo...')
        modelo = carregar_modelo(h)

        # Preparar dados
        print(f'  Preparando features...')
        X_h, meta_h = preparar_dados(df, h)
        print(f'  X_h: {X_h.shape[0]} registros × {X_h.shape[1]} features')

        # Calcular SHAP global
        print(f'\n  Calculando SHAP values (TreeExplainer)...')
        shap_values, explainer, df_imp = calcular_shap(modelo, X_h)

        # Armazenar para comparativo
        resultados[h] = {
            'shap_values': shap_values,
            'X':           X_h,
            'meta':        meta_h,
            'df_imp':      df_imp,
        }

        # Top 10 no console
        print(f'\n  Top 10 features (global, h={h}):')
        for _, row in df_imp.head(10).iterrows():
            print(f'    {label(row["feature"]):<35} |SHAP|={row["shap_mean_abs"]:.4f}')

        # ── Figuras globais ───────────────────────────────────────────────────
        print(f'\n  Gerando figuras globais...')

        plot_beeswarm(
            shap_values, X_h,
            titulo=f'SHAP Beeswarm — h={h} SE (ambos municípios)\n'
                   f'Top 20 features | Importância e direção do efeito',
            path=DIR_GLOBAL / f'fig01_h{h}_beeswarm.png',
        )

        plot_bar(
            df_imp,
            titulo=f'Top 20 Features — h={h} SE (global)\n'
                   f'Importância SHAP (Lundberg & Lee, 2017)',
            path=DIR_GLOBAL / f'fig02_h{h}_bar_top20.png',
        )

        plot_dependence(
            shap_values, X_h, df_imp,
            titulo=f'SHAP Dependence — h={h} SE | Top 6 features\n'
                   f'Relações não-lineares capturadas pelo modelo',
            path=DIR_GLOBAL / f'fig03_h{h}_dependence.png',
        )

        plot_temporal(
            shap_values, X_h, meta_h, df_imp,
            titulo=f'Importância SHAP por fase epidêmica — h={h} SE\n'
                   f'Como diferentes features dominam em cada período',
            path=DIR_GLOBAL / f'fig04_h{h}_temporal.png',
        )

        # ── CSV global ────────────────────────────────────────────────────────
        df_imp.to_csv(DIR_DADOS / f'shap_importance_h{h}.csv', index=False)
        print(f'    ✅ shap_importance_h{h}.csv')

        # ── Figuras por município ─────────────────────────────────────────────
        print(f'\n  Gerando figuras por município...')
        for mun_id, mun_nome in MUNICIPIOS.items():
            print(f'    → {mun_nome} ({mun_id})')
            analisar_municipio(shap_values, X_h, meta_h, mun_id, mun_nome, h)

    # ── 3. Figura comparativa entre horizontes ────────────────────────────────
    print(f'\n{"─"*65}')
    print('▶ Gerando figura comparativa entre horizontes...')
    plot_comparativo_horizontes(
        resultados,
        path=DIR_GLOBAL / 'fig05_comparativo_horizontes.png',
    )

    # ── 4. CSV consolidado ────────────────────────────────────────────────────
    print('\n▶ Salvando CSV consolidado...')
    dfs_consolidado = []
    for h, dados in resultados.items():
        df_h = dados['df_imp'].copy()
        df_h['horizonte'] = h
        df_h['label'] = df_h['feature'].map(lambda f: label(f))
        dfs_consolidado.append(df_h)

    df_consolidado = pd.concat(dfs_consolidado, ignore_index=True)
    df_consolidado.to_csv(DIR_DADOS / 'shap_importance_consolidado.csv', index=False)
    print(f'  ✅ shap_importance_consolidado.csv '
          f'({len(df_consolidado)} linhas)')

    # ── 5. Resumo final ───────────────────────────────────────────────────────
    print(f'\n{"="*65}')
    print('RESUMO')
    print(f'{"="*65}')
    print(f'\n  Feature mais importante por horizonte:')
    for h, dados in resultados.items():
        top1 = dados['df_imp'].iloc[0]
        print(f'    h={h} SE → {label(top1["feature"]):<35} '
              f'|SHAP|={top1["shap_mean_abs"]:.4f}')

    total_figs = len(HORIZONTES_DIRECT) * 4 + 1  # 4 globais por h + comparativo
    total_mun  = len(HORIZONTES_DIRECT) * len(MUNICIPIOS) * 2  # beeswarm + bar
    print(f'\n  Figuras globais:      {total_figs}')
    print(f'  Figuras município:    {total_mun}')
    print(f'  CSVs gerados:         {len(HORIZONTES_DIRECT) * 3 + 1}')
    print(f'\n  Diretório de saída: {SHAP_DIR}')
    print(f'\n  Quando rodar novamente:')
    print(f'  → Após retreino executado pelo pipeline semanal')
    print(f'{"="*65}')


if __name__ == '__main__':
    main()