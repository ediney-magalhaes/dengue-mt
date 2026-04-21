import sys, pandas as pd, numpy as np, joblib
from datetime import timedelta
from pathlib import Path

DATA_DIR   = Path('data')
MODELS_DIR = Path('models')

modelo = joblib.load(MODELS_DIR / 'lgbm_v4_producao.pkl')
df = pd.read_parquet(DATA_DIR / 'gold' / 'dataset_features_v4.parquet')
df['data'] = pd.to_datetime(df['data'])
df = df.sort_values('data').reset_index(drop=True)

feature_cols = [c for c in modelo.feature_name_ if c in df.columns]
df2 = df.dropna(subset=feature_cols)

data_max  = df2['data'].max()
corte_cur = data_max - timedelta(days=90)
df_cur    = df2[df2['data'] >= corte_cur]

print(f'Gold total: {len(df)} | apos dropna features: {len(df2)}')
print(f'data_max: {data_max.date()} | corte_cur: {corte_cur.date()}')
print(f'df_cur (ultimos 90d): {len(df_cur)} registros')
print(f'Periodo df_cur: {df_cur["data"].min().date()} -> {df_cur["data"].max().date()}')

# Quais features do modelo estao faltando no Gold?
faltando = [c for c in modelo.feature_name_ if c not in df.columns]
print(f'\nFeatures faltando no Gold ({len(faltando)}):')
print(faltando)

# Quais features tem nulos?
nulos = df[feature_cols].isnull().sum()
nulos = nulos[nulos > 0].sort_values(ascending=False)
print(f'\nFeatures com nulos:')
print(nulos)
print(f'\nRegistros sem nenhum nulo: {df[feature_cols].dropna().shape[0]}')