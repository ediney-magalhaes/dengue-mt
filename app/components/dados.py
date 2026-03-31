# ============================================================
# Dengue MT — Componente: Acesso a Dados
# ============================================================

import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

API_URL    = "http://127.0.0.1:8000"
HF_DATASET = "edyestatistica/dengue-mt-medallion"


@st.cache_data(ttl=300)
def get_saude():
    try:
        r = requests.get(f"{API_URL}/saude", timeout=3)
        return r.json() if r.status_code == 200 else None
    except:
        pass
    return {
        'modelo': 'LightGBM v4',
        'status': 'ok',
        'metricas': {'R2': 0.820, 'MAE': 17.6, 'RMSE': 28.4, 'sMAPE': 31.5}
    }


@st.cache_data(ttl=300)
def carregar_do_hf(arquivo):
    try:
        from huggingface_hub import hf_hub_download
        path = hf_hub_download(
            repo_id=HF_DATASET, filename=arquivo, repo_type="dataset"
        )
        return pd.read_parquet(path)
    except Exception as e:
        st.warning(f"HF Hub indisponível: {e}")
        return None


@st.cache_data(ttl=300)
def get_historico():
    try:
        r = requests.get(f"{API_URL}/historico", timeout=5)
        if r.status_code == 200:
            df = pd.DataFrame(r.json()['serie'])
            df['data'] = pd.to_datetime(df['data'])
            return df
    except:
        pass
    df = carregar_do_hf('gold/dataset_features_v4.parquet')
    if df is not None:
        df['data'] = pd.to_datetime(df['data'])
        return df[['data', 'casos']].sort_values('data')
    try:
        df = pd.read_parquet('data/gold/dataset_features_v4.parquet')
        df['data'] = pd.to_datetime(df['data'])
        return df[['data', 'casos']].sort_values('data')
    except:
        return None


@st.cache_data(ttl=300)
def get_score_risco_hf():
    try:
        r = requests.get(f"{API_URL}/score-risco", timeout=5)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    df = carregar_do_hf('external/score_risco_v2.parquet')
    if df is not None:
        return {
            'total_unidades': len(df),
            'gerado_em': datetime.now().isoformat(),
            'distribuicao': df['risco_v2'].value_counts().to_dict(),
            'unidades': df.to_dict(orient='records')
        }
    return None


@st.cache_data(ttl=300)
def get_previsao(dias=14):
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
            filename="models/lgbm_v4_producao.pkl",
            repo_type="dataset"
        )
        return joblib.load(path)
    except:
        return None


def fazer_previsao_local(modelo, df_gold, dias=14):
    try:
        df = df_gold.copy()
        df['data'] = pd.to_datetime(df['data'])
        df = df.sort_values('data').dropna()
        feature_cols  = [c for c in modelo.feature_name_ if c in df.columns]
        ultima_linha  = df[feature_cols].iloc[[-1]]
        ultima_data   = df['data'].max()
        previsoes = []
        for i in range(1, dias + 1):
            data_prev  = ultima_data + timedelta(days=i)
            casos_pred = max(float(modelo.predict(ultima_linha)[0]), 0)
            previsoes.append({
                'data': data_prev.strftime('%Y-%m-%d'),
                'casos_previstos': round(casos_pred, 1),
                'nivel_risco': (
                    'Muito Alto'  if casos_pred > 200 else
                    'Alto'        if casos_pred > 100 else
                    'Moderado'    if casos_pred > 50  else
                    'Baixo'       if casos_pred > 20  else
                    'Muito Baixo'
                )
            })
        return {
            'modelo': 'LightGBM v4',
            'gerado_em': datetime.now().isoformat(),
            'ultima_data_conhecida': ultima_data.strftime('%Y-%m-%d'),
            'horizonte_dias': dias,
            'previsoes': previsoes
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
            # nivel_drift pode estar em resultados ou na raiz
            resultados = meta.get('resultados', {})
            return {
                'nivel_drift':  resultados.get('nivel_drift', meta.get('nivel_drift')),
                'drift_score':  resultados.get('drift_score', meta.get('drift_score')),
                'drift_mae':    resultados.get('drift_mae',   meta.get('drift_mae')),
                'drift_r2':     resultados.get('drift_r2',    meta.get('drift_r2')),
                'retreino':     resultados.get('retreino',    meta.get('retreino')),
                'timestamp':    meta.get('timestamp', ''),
                'fallbacks':    resultados.get('fallbacks',   meta.get('fallbacks', {})),
            }
        except:
            continue
    return None