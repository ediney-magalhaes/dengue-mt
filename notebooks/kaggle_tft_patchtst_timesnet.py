"""
kaggle_tft_patchtst_timesnet.py
--------------------------------
Treina TFT, PatchTST e TimesNet com GPU no Kaggle
Série histórica: 2007-2024 | 888 semanas | 142 municípios

Como usar no Kaggle:
    1. Fazer upload dos arquivos parquet como dataset
    2. Criar notebook com GPU P100
    3. Executar este script
"""

# ============================================================
# INSTALAÇÃO
# ============================================================
import subprocess
subprocess.run(['pip', 'install', 'neuralforecast', 'pytorch-forecasting', 
                'lightning', '-q'], check=True)

import pandas as pd
import numpy as np
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
import matplotlib.pyplot as plt
import torch
import warnings
warnings.filterwarnings('ignore')

print(f"GPU disponível: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")

# ============================================================
# CARREGAR DADOS
# ============================================================
# Ajustar path conforme estrutura do Kaggle
serie = pd.read_parquet('/kaggle/input/dengue-mt/serie_semanal_historica_2007_2024.parquet')
municipios = pd.read_parquet('/kaggle/input/dengue-mt/serie_municipios_historica_2007_2024.parquet')

serie['semana'] = pd.to_datetime(serie['semana'])
municipios['semana'] = pd.to_datetime(municipios['semana'])

print(f"Série MT: {len(serie)} semanas")
print(f"Municípios: {municipios['ID_MUNICIP'].nunique()} municípios × {municipios['semana'].nunique()} semanas")

# ============================================================
# PREPARAR FORMATO NEURALFORECAST
# ============================================================
h = 8           # horizonte 8 semanas (~2 meses)
n_test = 52     # último ano para teste

# Série única MT
df_nf = serie[['semana', 'casos']].copy()
df_nf.columns = ['ds', 'y']
df_nf['unique_id'] = 'MT'
df_nf['y'] = df_nf['y'].astype(float)

df_train = df_nf.iloc[:-n_test]
df_test  = df_nf.iloc[-n_test:]

print(f"\nTreino: {len(df_train)} | Teste: {len(df_test)}")
print(f"Período teste: {df_test['ds'].iloc[0].date()} → {df_test['ds'].iloc[-1].date()}")

# ============================================================
# TREINAR MODELOS
# ============================================================
from neuralforecast import NeuralForecast
from neuralforecast.models import TFT, PatchTST, TimesNet, NHITS
from neuralforecast.losses.pytorch import MAE as NMAE

MODELOS = {
    'TFT': TFT(
        h=h, input_size=104,  # 2 anos de encoder
        max_steps=500,
        hidden_size=128,
        loss=NMAE(),
        scaler_type='standard',
        random_seed=42,
        enable_progress_bar=True,
    ),
    'PatchTST': PatchTST(
        h=h, input_size=104,
        max_steps=500,
        loss=NMAE(),
        scaler_type='standard',
        random_seed=42,
        enable_progress_bar=True,
    ),
    'TimesNet': TimesNet(
        h=h, input_size=104,
        max_steps=500,
        loss=NMAE(),
        scaler_type='standard',
        random_seed=42,
        enable_progress_bar=True,
    ),
    'NHITS_baseline': NHITS(
        h=h, input_size=104,
        max_steps=500,
        loss=NMAE(),
        scaler_type='standard',
        random_seed=42,
        enable_progress_bar=True,
    ),
}

resultados = {}

for nome, modelo in MODELOS.items():
    print(f"\n{'='*50}")
    print(f"Treinando {nome}...")
    
    all_preds = []
    all_real = []
    
    for i in range(0, n_test - h + 1, h):
        df_temp = df_nf.iloc[:len(df_train) + i].copy()
        nf = NeuralForecast(models=[modelo], freq='W')
        nf.fit(df_temp)
        pred = nf.predict().reset_index(drop=True)
        
        y_p = np.clip(pred[nome].values, 0, None)
        y_r = df_nf['y'].iloc[len(df_train)+i : len(df_train)+i+h].values
        
        all_preds.extend(y_p[:len(y_r)])
        all_real.extend(y_r)
    
    all_preds = np.array(all_preds)
    all_real  = np.array(all_real)
    
    mae = mean_absolute_error(all_real, all_preds)
    r2  = r2_score(all_real, all_preds)
    
    resultados[nome] = {'mae': mae, 'r2': r2, 
                        'preds': all_preds, 'real': all_real}
    print(f"{nome}: MAE={mae:.2f} | R²={r2:.3f}")

# ============================================================
# RESULTADOS FINAIS
# ============================================================
print(f"\n{'='*50}")
print(f"RANKING FINAL:")
print(f"{'Modelo':<20} {'R²':>8} {'MAE':>8}")
print(f"{'-'*38}")
for nome, res in sorted(resultados.items(), key=lambda x: x[1]['r2'], reverse=True):
    print(f"{nome:<20} {res['r2']:>8.3f} {res['mae']:>8.2f}")

# Salvar resultados
ranking = pd.DataFrame([
    {'modelo': nome, 'r2': res['r2'], 'mae': res['mae']}
    for nome, res in resultados.items()
])
ranking.to_csv('/kaggle/working/ranking_kaggle_gpu.csv', index=False)
print(f"\nResultados salvos!")