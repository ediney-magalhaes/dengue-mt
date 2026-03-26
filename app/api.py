# ============================================================
# Dengue MT — API REST com FastAPI
# Autor: Ediney Magalhães — IFMT 2026
# ============================================================

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
import json

# ============================================================
# CONFIGURAÇÃO
# ============================================================
BASE_DIR = Path(__file__).parent.parent
MODELS_DIR = BASE_DIR / 'models'
DATA_DIR   = BASE_DIR / 'data'
REPORTS_DIR = BASE_DIR / 'reports'

app = FastAPI(
    title="Dengue MT — API de Previsão",
    description="API REST para previsão de surtos de dengue em Cuiabá e Várzea Grande/MT",
    version="1.0.0",
    docs_url="/docs"
)

# CORS — permite acesso do Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# ============================================================
# CARREGAR RECURSOS NA INICIALIZAÇÃO
# ============================================================
@app.on_event("startup")
async def carregar_recursos():
    global modelo, df_gold, df_score, resumo_v4
    
    try:
        modelo = joblib.load(MODELS_DIR / 'lgbm_v4_producao.pkl')
        print("Modelo v4 carregado")
    except Exception as e:
        print(f"Modelo não encontrado: {e}")
        modelo = None
    
    try:
        df_gold = pd.read_parquet(DATA_DIR / 'gold' / 'dataset_features_v4.parquet')
        df_gold['data'] = pd.to_datetime(df_gold['data'])
        df_gold = df_gold.sort_values('data').reset_index(drop=True)
        print(f"Gold dataset carregado: {df_gold.shape}")
    except Exception as e:
        print(f"Gold dataset não encontrado: {e}")
        df_gold = None
    
    try:
        df_score = pd.read_parquet(DATA_DIR / 'external' / 'score_risco_v2.parquet')
        print(f"Score risco carregado: {len(df_score)} unidades")
    except Exception as e:
        print(f"Score risco não encontrado: {e}")
        df_score = None

    try:
        with open(REPORTS_DIR / 'resumo_metricas_v4.json', encoding='utf-8') as f:
            resumo_v4 = json.load(f)
    except:
        resumo_v4 = {}

# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/")
def root():
    return {
        "projeto": "Dengue MT — Sistema Preditivo de Surtos",
        "versao": "1.0.0",
        "instituicao": "IFMT",
        "endpoints": ["/previsao", "/score-risco", "/saude", "/docs"]
    }


@app.get("/saude")
def status_modelo():
    """Retorna status do modelo e métricas de desempenho."""
    return {
        "status": "ok" if modelo else "modelo_nao_carregado",
        "modelo": "LightGBM v4",
        "features": resumo_v4.get('n_features', 59),
        "periodo_treino": resumo_v4.get('periodo', 'N/A'),
        "metricas": resumo_v4.get('metricas', {}),
        "ultima_atualizacao": datetime.now().isoformat()
    }


@app.get("/previsao")
def previsao(dias: int = 14):
    """
    Retorna previsão de casos de dengue para os próximos N dias.
    
    - **dias**: horizonte de previsão (padrão: 14 dias)
    """
    if modelo is None or df_gold is None:
        raise HTTPException(status_code=503, detail="Modelo ou dados não disponíveis")
    
    if dias < 1 or dias > 28:
        raise HTTPException(status_code=400, detail="Dias deve ser entre 1 e 28")
    
    # Usar últimos registros como base
    df_recente = df_gold.dropna().tail(60).copy()
    
    # Features do modelo
    feature_cols = modelo.feature_name_
    feature_cols = [c for c in feature_cols if c in df_recente.columns]
    
    # Previsão rolling — cada dia usa previsão anterior como lag
    previsoes = []
    ultima_data = df_recente['data'].max()
    
    for i in range(1, dias + 1):
        data_prev = ultima_data + timedelta(days=i)
        
        # Usar última linha disponível como features
        X_pred = df_recente[feature_cols].iloc[[-1]]
        
        casos_pred = max(float(modelo.predict(X_pred)[0]), 0)
        
        previsoes.append({
            'data': data_prev.strftime('%Y-%m-%d'),
            'casos_previstos': round(casos_pred, 1),
            'nivel_risco': (
                'Muito Alto' if casos_pred > 200 else
                'Alto'       if casos_pred > 100 else
                'Moderado'   if casos_pred > 50  else
                'Baixo'      if casos_pred > 20  else
                'Muito Baixo'
            )
        })
    
    return {
        'modelo': 'LightGBM v4',
        'gerado_em': datetime.now().isoformat(),
        'ultima_data_conhecida': ultima_data.strftime('%Y-%m-%d'),
        'horizonte_dias': dias,
        'previsoes': previsoes,
        'aviso': 'Previsões baseadas em padrões históricos 2018-2024'
    }


@app.get("/score-risco")
def score_risco(municipio: str = None):
    """
    Retorna score de risco por unidade de saúde.
    
    - **municipio**: filtrar por município (opcional)
    """
    if df_score is None:
        raise HTTPException(status_code=503, detail="Score de risco não disponível")
    
    df = df_score.copy()
    
    # Filtrar por município se solicitado
    if municipio:
        df = df[df['bairro_estabelecimento'].str.contains(municipio, case=False, na=False)]
    
    # Serializar resultado
    resultado = df[[
        'nome_fantasia', 'bairro_estabelecimento',
        'casos_historicos', 'score_v2', 'risco_v2', 'baixa_confianca',
        'latitude_estabelecimento_decimo_grau',
        'longitude_estabelecimento_decimo_grau'
    ]].to_dict(orient='records')
    
    return {
        'total_unidades': len(resultado),
        'gerado_em': datetime.now().isoformat(),
        'distribuicao': df['risco_v2'].value_counts().to_dict(),
        'unidades': resultado
    }


@app.get("/historico")
def historico(ano: int = None):
    """Retorna série histórica de casos."""
    if df_gold is None:
        raise HTTPException(status_code=503, detail="Dados não disponíveis")
    
    df = df_gold[['data', 'casos']].copy()
    
    if ano:
        df = df[df['data'].dt.year == ano]
    
    return {
        'total_registros': len(df),
        'periodo': f"{df['data'].min().date()} → {df['data'].max().date()}",
        'serie': df.assign(data=df['data'].dt.strftime('%Y-%m-%d')).to_dict(orient='records')
    }