import sys
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import mean_absolute_error, r2_score
from pathlib import Path

DATA_DIR   = Path('data')
MODELS_DIR = Path('models')

# Carregar Gold
df = pd.read_parquet(DATA_DIR / 'gold' / 'dataset_features_v4.parquet')
df['data'] = pd.to_datetime(df['data'])
df = df.sort_values('data').reset_index(drop=True)

print(f"Gold bruto: {len(df)} registros | {df['data'].min().date()} → {df['data'].max().date()}")

# Agregar por data (soma casos, média features)
colunas = {c: ('sum' if c == 'casos' else 'mean') for c in df.columns if c != 'data'}
df = df.groupby('data').agg(colunas).reset_index()
df = df.sort_values('data').reset_index(drop=True)

print(f"Gold agregado: {len(df)} registros | {df['data'].min().date()} → {df['data'].max().date()}")

# Carregar modelo
modelo = joblib.load(MODELS_DIR / 'lgbm_v4_producao.pkl')
feature_cols = [c for c in modelo.feature_name_ if c in df.columns]
print(f"Features: {len(feature_cols)}/59")

# Filtrar 2025+
mask = df['data'] >= pd.Timestamp('2025-01-01')
df_test = df[mask].copy()
# Não dropar — modelo LightGBM lida com NaN nativamente
df_test = df_test[df_test['casos'].notna()]

print(f"\nPeríodo 2025+: {len(df_test)} registros")
print(f"De: {df_test['data'].min().date()} → {df_test['data'].max().date()}")

if df_test.empty:
    print("ERRO: sem dados de 2025+")
    sys.exit(1)

X_test = df_test[feature_cols]
y_test = df_test['casos']
preds  = np.maximum(modelo.predict(X_test), 0)

print(f"\nMAE: {mean_absolute_error(y_test, preds):.1f} casos/semana")
print(f"R²:  {r2_score(y_test, preds):.3f}")

print("\nÚltimas 15 semanas — real vs previsto:")
df_result = df_test[['data', 'casos']].copy()
df_result['previsto'] = preds.astype(int)
df_result['erro_abs'] = (df_result['casos'] - df_result['previsto']).abs().astype(int)
print(df_result.tail(15).to_string(index=False))