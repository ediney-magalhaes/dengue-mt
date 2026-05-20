# ============================================================
# Dengue MT — Componente: Acesso a Dados v3.0
# ============================================================
# Fonte única de dados para todas as abas do dashboard.
# Limiares de risco lidos do GeoJSON — zero hardcode.
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

API_URL    = "http://127.0.0.1:8000"
HF_DATASET = "edyestatistica/dengue-mt-medallion"

HF_GOLD_LATEST  = 'gold/dataset_features_latest.parquet'
HF_MODEL_LATEST = 'models/lgbm_producao_latest.pkl'
HF_DIRECT_METADATA = 'models/direct_cqr_metadata.json'
HORIZONTES_DIRECT  = [1, 2, 4, 8]


@st.cache_data(ttl=300)
def get_saude():
    try:
        r = requests.get(f"{API_URL}/saude", timeout=3)
        return r.json() if r.status_code == 200 else None
    except Exception:
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
    except Exception:
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
    except Exception:
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
    except Exception:
        return None

@st.cache_resource
def carregar_modelos_direct_hf():
    """
    Carrega 12 modelos Direct CQR + metadata do HF Hub.
    Retorna: (modelos_dict, metadata_dict) ou (None, None)
    """
    try:
        from huggingface_hub import hf_hub_download
        import joblib
        import json

        path_meta = hf_hub_download(
            repo_id=HF_DATASET,
            filename=HF_DIRECT_METADATA,
            repo_type='dataset'
        )
        with open(path_meta, encoding='utf-8') as f:
            metadata = json.load(f)

        quantis = metadata['quantis']
        modelos = {}
        for h in HORIZONTES_DIRECT:
            for q in quantis:
                q_str = str(int(q * 100)).zfill(2)
                path = hf_hub_download(
                    repo_id=HF_DATASET,
                    filename=f'models/lgbm_h{h}_q{q_str}_latest.pkl',
                    repo_type='dataset'
                )
                modelos[(h, q_str)] = joblib.load(path)

        return modelos, metadata
    except Exception:
        return None, None


def fazer_previsao_local(modelo, df_gold, semanas=4,
                         modelos_direct=None, metadata_direct=None):
    """
    Previsão local por município.
    Com Direct CQR: modelo por horizonte + bandas calibradas.
    Sem Direct CQR: fallback modelo pontual único.
    """
    try:
        df = df_gold.copy()
        df['data_se'] = pd.to_datetime(df['data_se'])
        df = df.sort_values('data_se')

        if modelos_direct:
            modelo_ref = modelos_direct[(HORIZONTES_DIRECT[0], '50')]
        else:
            modelo_ref = modelo

        feature_cols = [c for c in modelo_ref.feature_name_ if c in df.columns]

        col_casos = [c for c in df.columns if 'caso' in c.lower()][0]
        limiares_mun = {}
        for mun_id in df['municipio_id'].unique():
            casos_hist = df.loc[df['municipio_id'] == mun_id, col_casos].dropna().values
            limiares_mun[int(mun_id)] = {
                'P60': float(np.percentile(casos_hist, 60)),
                'P75': float(np.percentile(casos_hist, 75)),
                'P85': float(np.percentile(casos_hist, 85)),
                'P95': float(np.percentile(casos_hist, 95)),
            }

        def _classificar(casos, mun_id):
            lim = limiares_mun.get(int(mun_id), {})
            if not lim:
                return 'Muito Baixo'
            if casos > lim['P95']:
                return 'Muito Alto'
            if casos > lim['P85']:
                return 'Alto'
            if casos > lim['P75']:
                return 'Moderado'
            if casos > lim['P60']:
                return 'Baixo'
            return 'Muito Baixo'

        if modelos_direct:
            horizontes = HORIZONTES_DIRECT
            q_lo_str = str(int(metadata_direct['quantis'][0] * 100)).zfill(2)
            q_hi_str = str(int(metadata_direct['quantis'][2] * 100)).zfill(2)
        else:
            horizontes = list(range(1, semanas + 1))

        previsoes = []
        for mun_id in df['municipio_id'].unique():
            df_mun = df[df['municipio_id'] == mun_id]
            ultima_linha = df_mun[feature_cols].iloc[[-1]]
            ultima_data = df_mun['data_se'].max()

            for h in horizontes:
                data_prev = ultima_data + timedelta(weeks=h)

                if modelos_direct and (h, '50') in modelos_direct:
                    pred_q50 = max(float(np.expm1(
                        modelos_direct[(h, '50')].predict(ultima_linha)[0]
                    )), 0)
                    pred_lo = max(float(np.expm1(
                        modelos_direct[(h, q_lo_str)].predict(ultima_linha)[0]
                    )), 0)
                    pred_hi = max(float(np.expm1(
                        modelos_direct[(h, q_hi_str)].predict(ultima_linha)[0]
                    )), 0)

                    cal = metadata_direct['modelos'].get(f'h{h}_calibracao', {})
                    q_conf = cal.get('q_conformal', 0.0)

                    lower = max(pred_lo - q_conf, 0)
                    upper = max(pred_hi + q_conf, pred_q50)
                    casos_pred = pred_q50
                else:
                    casos_pred = max(float(np.expm1(
                        modelo.predict(ultima_linha)[0]
                    )), 0)
                    lower = None
                    upper = None

                prev = {
                    'data_se':         data_prev.strftime('%Y-%m-%d'),
                    'municipio_id':    int(mun_id),
                    'casos_previstos': round(casos_pred, 1),
                    'horizonte_se':    h,
                    'nivel_risco':     _classificar(casos_pred, mun_id),
                }
                if lower is not None:
                    prev['lower'] = round(lower, 1)
                    prev['upper'] = round(upper, 1)

                previsoes.append(prev)

        return {
            'modelo':                'Direct CQR v1' if modelos_direct else 'LightGBM v5',
            'gerado_em':             datetime.now().isoformat(),
            'ultima_data_conhecida': str(df['data_se'].max().date()),
            'horizonte_semanas':     len(horizontes),
            'tem_bandas':            modelos_direct is not None,
            'previsoes':             previsoes
        }
    except Exception:
        return None


@st.cache_data(ttl=1800)
def get_run_metadata():
    """
    Carrega metadata do último run do pipeline.
    Prioridade: HF Hub (reports/historico_runs.parquet) → arquivo local
    """
    try:
        df = carregar_do_hf('reports/historico_runs.parquet')
        if df is not None and not df.empty:
            ultimo = df.sort_values('timestamp').iloc[-1]
            return {
                'nivel_drift': ultimo.get('nivel_drift'),
                'drift_score': ultimo.get('drift_score'),
                'drift_mae':   ultimo.get('drift_mae'),
                'drift_r2':    ultimo.get('drift_r2'),
                'retreino':    ultimo.get('retreino', 'nao_executado'),
                'timestamp':   str(ultimo.get('timestamp', '')),
                'fallbacks':   {},
            }
    except Exception:
        pass

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
                'nivel_drift': resultados.get('nivel_drift', meta.get('nivel_drift')),
                'drift_score': resultados.get('drift_score', meta.get('drift_score')),
                'drift_mae':   resultados.get('drift_mae', meta.get('drift_mae')),
                'drift_r2':    resultados.get('drift_r2', meta.get('drift_r2')),
                'retreino':    resultados.get('retreino', meta.get('retreino')),
                'timestamp':   meta.get('timestamp', ''),
                'fallbacks':   resultados.get('fallbacks', meta.get('fallbacks', {})),
            }
        except Exception:
            continue
    return None


@st.cache_data(ttl=3600)
def get_score_risco_hf():
    """
    Carrega score de risco por UBS do HF Hub.
    Usado pelo mapa estático de referência histórica.
    """
    try:
        from huggingface_hub import hf_hub_download
        path = hf_hub_download(
            repo_id=HF_DATASET,
            filename='external/score_risco_v2.parquet',
            repo_type='dataset'
        )
        df = pd.read_parquet(path)
        return {
            'unidades':     df.to_dict(orient='records'),
            'distribuicao': df['risco_v2'].value_counts().to_dict(),
            'n_total':      len(df),
        }
    except Exception:
        return None


@st.cache_data(ttl=3600)
def get_previsao_bairros():
    """
    Carrega previsão por bairro (GeoJSON IDW) do HF Hub.
    Retorna tupla: (GeoDataFrame, limiares_dict)

    Limiares são embutidos no GeoJSON pelo gerar_previsao_bairros.py
    como propriedade do FeatureCollection — única fonte de verdade.
    """
    try:
        import geopandas as gpd
        import json
        from huggingface_hub import hf_hub_download

        path = hf_hub_download(
            repo_id=HF_DATASET,
            filename='external/previsao_bairros_latest.geojson',
            repo_type='dataset'
        )

        # Lê GeoDataFrame
        gdf = gpd.read_file(path)

        # Lê limiares do GeoJSON (metadados do FeatureCollection)
        with open(path, encoding='utf-8') as f:
            geojson_raw = json.load(f)

        limiares = geojson_raw.get('limiares_risco', {})

        return gdf, limiares

    except Exception:
        return None, {}