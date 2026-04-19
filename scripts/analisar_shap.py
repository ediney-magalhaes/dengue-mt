"""
Análise SHAP — LightGBM v5
Importância de features para o artigo
Referência: Chen & Moraga 2025 (BMC Public Health) —
SHAP-driven lagged climate variable selection for dengue
"""
import pandas as pd
import numpy as np
import lightgbm as lgb
import shap
import matplotlib.pyplot as plt
from pathlib import Path

GOLD_PATH  = Path('data/gold/dataset_features_v5_latest.parquet')
OUTPUT_DIR = Path('reports/shap')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DROP_COLS = [
    'municipio_nome', 'data_se', 'dbt_updated_at',
    'casos_estimados', 'incidencia_100k', 'semana_epidemiologica'
]
TARGET = 'casos_confirmados'

MUNICIPIOS = {
    5103403: 'Cuiabá',
    5108402: 'Várzea Grande'
}

PARAMS = {
    'objective':         'regression',
    'metric':            'mae',
    'n_estimators':      500,
    'learning_rate':     0.05,
    'num_leaves':        31,
    'min_child_samples': 20,
    'subsample':         0.8,
    'colsample_bytree':  0.8,
    'random_state':      42,
    'verbose':           -1
}


def treinar_modelo(X, y):
    modelo = lgb.LGBMRegressor(**PARAMS)
    modelo.fit(X, np.log1p(y))
    return modelo


def calcular_shap(modelo, X, municipio_nome):
    print(f'\n  Calculando SHAP para {municipio_nome}...')
    explainer = shap.TreeExplainer(modelo)
    shap_vals  = explainer.shap_values(X)

    # Importância média absoluta
    imp = pd.DataFrame({
        'feature':   X.columns,
        'shap_mean': np.abs(shap_vals).mean(axis=0)
    }).sort_values('shap_mean', ascending=False)

    imp['shap_pct'] = (imp['shap_mean'] / imp['shap_mean'].sum() * 100).round(2)
    imp['rank']     = range(1, len(imp) + 1)

    return shap_vals, imp


def plotar_beeswarm(shap_vals, X, municipio_nome, municipio_id):
    plt.figure(figsize=(12, 10))
    shap.summary_plot(
        shap_vals, X,
        max_display=20,
        show=False,
        plot_type='dot'
    )
    plt.title(f'SHAP — Top 20 Features\n{municipio_nome}',
              fontsize=14, pad=15)
    plt.tight_layout()
    path = OUTPUT_DIR / f'shap_beeswarm_{municipio_id}.png'
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  Salvo: {path}')


def plotar_barras(imp, municipio_nome, municipio_id):
    top20 = imp.head(20).copy()
    plt.figure(figsize=(10, 8))
    plt.barh(top20['feature'][::-1], top20['shap_mean'][::-1], color='steelblue')
    plt.xlabel('SHAP médio absoluto (escala log)', fontsize=12)
    plt.title(f'Importância SHAP — Top 20 Features\n{municipio_nome}',
              fontsize=14)
    plt.tight_layout()
    path = OUTPUT_DIR / f'shap_barras_{municipio_id}.png'
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  Salvo: {path}')


if __name__ == '__main__':
    print('=== Análise SHAP — LightGBM v5 ===\n')

    df = pd.read_parquet(GOLD_PATH)
    df = df.sort_values(['municipio_id', 'data_se']).reset_index(drop=True)

    resumo = []

    for municipio_id, municipio_nome in MUNICIPIOS.items():
        print(f'\n{"="*50}')
        print(f'Município: {municipio_nome} ({municipio_id})')
        print(f'{"="*50}')

        df_mun = df[df['municipio_id'] == municipio_id].copy()
        X = df_mun.drop(columns=DROP_COLS + [TARGET, 'municipio_id'],
                        errors='ignore')
        y = df_mun[TARGET]

        # Treina modelo
        modelo = treinar_modelo(X, y)

        # Calcula SHAP
        shap_vals, imp = calcular_shap(modelo, X, municipio_nome)

        # Salva importância CSV
        path_csv = OUTPUT_DIR / f'shap_importance_{municipio_id}.csv'
        imp.to_csv(path_csv, index=False)
        print(f'  CSV salvo: {path_csv}')

        # Plots
        plotar_beeswarm(shap_vals, X, municipio_nome, municipio_id)
        plotar_barras(imp, municipio_nome, municipio_id)

        # Top 10 para console
        print(f'\n  Top 10 features:')
        print(f'  {"Rank":>4} {"Feature":<30} {"SHAP%":>8}')
        print(f'  {"-"*45}')
        for _, row in imp.head(10).iterrows():
            print(f'  {int(row["rank"]):>4} {row["feature"]:<30} '
                  f'{row["shap_pct"]:>7.1f}%')

        resumo.append({
            'municipio':   municipio_nome,
            'top1_feature': imp.iloc[0]['feature'],
            'top1_pct':     imp.iloc[0]['shap_pct'],
            'top5_pct':     imp.head(5)['shap_pct'].sum()
        })

    # Resumo final
    print(f'\n{"="*50}')
    print('RESUMO')
    print(f'{"="*50}')
    for r in resumo:
        print(f'\n{r["municipio"]}:')
        print(f'  Feature mais importante: {r["top1_feature"]} '
              f'({r["top1_pct"]:.1f}%)')
        print(f'  Top 5 features: {r["top5_pct"]:.1f}% da importância total')

    print(f'\nArquivos salvos em: {OUTPUT_DIR}')