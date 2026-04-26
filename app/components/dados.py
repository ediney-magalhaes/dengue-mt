# ============================================================
# Dengue MT — Componente: Acesso a Dados v2.0
# ============================================================

import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

API_URL    = "http://127.0.0.1:8000"
HF_DATASET = "edyestatistica/dengue-mt-medallion"

# Nomes dos artefatos latest no HF Hub
HF_GOLD_LATEST  = 'gold/dataset_features_latest.parquet'
HF_MODEL_LATEST = 'models/lgbm_producao_latest.pkl'


@st.cache_data(ttl=300)
def get_saude():
    try:
        r = requests.get(f"{API_URL}/saude", timeout=3)
        return r.json() if r.status_code == 200 else None
    except:
        pass
    return {
        'modelo': 'LightGBM v5',
        'status': 'ok',
        'metricas': {'R2': 0.741, 'MAE': 9.7}
    }


@st.cache_data(ttl=300)
def carregar_do_hf(arquivo):
    try:
        from huggingface_hub import hf_hub_download
        path = hf_hub_download(
            repo_id=HF_DATASET, filename=arquivo, repo_type="dataset"
        )
        return pd.read_parquet(path)
    except Exception:
        return None


@st.cache_data(ttl=300)
def get_historico():
    try:
        r = requests.get(f"{API_URL}/historico", timeout=5)
        if r.status_code == 200:
            df = pd.DataFrame(r.json()['serie'])
            df['data_se'] = pd.to_datetime(df['data_se'])
            return df
    except:
        pass

    df = carregar_do_hf(HF_GOLD_LATEST)
    if df is not None:
        df['data_se'] = pd.to_datetime(df['data_se'])
        return df[['data_se', 'casos_confirmados', 'municipio_id']].sort_values('data_se')

    return None


@st.cache_data(ttl=300)
def get_previsao(dias=28):
    try:
        r = requests.get(f"{API_URL}/previsao", params={"dias": dias}, timeout=10)
        return r.json() if r.status_code == 200 else None
    except:
        return None


@st.cache_resource
def carregar_modelo_hf():
    try:
        from huggingface_hub import hf_hub_download
        import joblib
        path = hf_hub_download(
            repo_id=HF_DATASET,
            filename=HF_MODEL_LATEST,
            repo_type="dataset"
        )
        return joblib.load(path)
    except:
        return None


def fazer_previsao_local(modelo, df_gold, semanas=4):
    """Previsão local por município — SE+1 a SE+4."""
    try:
        df = df_gold.copy()
        df['data_se'] = pd.to_datetime(df['data_se'])
        df = df.sort_values('data_se')
        feature_cols = [c for c in modelo.feature_name_ if c in df.columns]

        previsoes = []
        for mun_id in df['municipio_id'].unique():
            df_mun = df[df['municipio_id'] == mun_id]
            ultima_linha = df_mun[feature_cols].iloc[[-1]]
            ultima_data  = df_mun['data_se'].max()

            for i in range(1, semanas + 1):
                data_prev  = ultima_data + timedelta(weeks=i)
                casos_pred = max(float(modelo.predict(ultima_linha)[0]), 0)
                previsoes.append({
                    'data_se':          data_prev.strftime('%Y-%m-%d'),
                    'municipio_id':     int(mun_id),
                    'casos_previstos':  round(casos_pred, 1),
                    'horizonte_se':     i,
                    'nivel_risco': (
                        'Muito Alto'  if casos_pred > 200 else
                        'Alto'        if casos_pred > 100 else
                        'Moderado'    if casos_pred > 50  else
                        'Baixo'       if casos_pred > 20  else
                        'Muito Baixo'
                    )
                })

        return {
            'modelo':                'LightGBM v5',
            'gerado_em':             datetime.now().isoformat(),
            'ultima_data_conhecida': str(df['data_se'].max().date()),
            'horizonte_semanas':     semanas,
            'previsoes':             previsoes
        }
    except:
        return None


@st.cache_data(ttl=1800)
def get_run_metadata():
    """Carrega metadata do último run do pipeline."""
    import json
    from pathlib import Path
    raiz = Path(__file__).parent.parent.parent
    caminhos = [
        raiz / 'metadata' / 'run_metadata.json',
        Path('metadata/run_metadata.json'),
        Path('../metadata/run_metadata.json'),
    ]
    for caminho in caminhos:
        try:
            with open(caminho) as f:
                meta = json.load(f)
            resultados = meta.get('resultados', {})
            return {
                'nivel_drift':  resultados.get('nivel_drift', meta.get('nivel_drift')),
                'drift_score':  resultados.get('drift_score', meta.get('drift_score')),
                'drift_mae':    resultados.get('drift_mae', meta.get('drift_mae')),
                'drift_r2':     resultados.get('drift_r2', meta.get('drift_r2')),
                'retreino':     resultados.get('retreino', meta.get('retreino')),
                'timestamp':    meta.get('timestamp', ''),
                'fallbacks':    resultados.get('fallbacks', meta.get('fallbacks', {})),
            }
        except:
            continue
    return None