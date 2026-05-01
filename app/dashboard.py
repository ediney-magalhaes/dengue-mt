"""
dashboard.py — v4
Dashboard interativo — Sistema Preditivo de Dengue MT
Modularizado em app/components/

Como rodar:
    streamlit run app/dashboard.py
"""

import streamlit as st
from datetime import datetime

from components.dados import get_saude, get_historico
from components.banner_drift import render_banner_drift
from components.aba_mapa import render_aba_mapa
from components.aba_serie import render_aba_serie
from components.aba_previsao import render_aba_previsao
from components.aba_sobre import render_aba_sobre
from components.aba_monitoramento import render_aba_monitoramento

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(
    page_title="Dengue MT — Sistema Preditivo",
    page_icon="🦟",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("## 🦟 Dengue MT")
    st.markdown("**Sistema Preditivo de Surtos**")
    st.markdown("---")

    horizonte = st.slider(
        "Horizonte de previsão (semanas)",
        min_value=1, max_value=4, value=2, step=1
    )

    st.markdown("---")
    st.markdown("### 📊 Status do Modelo")
    saude = get_saude()
    if saude:
        st.success(f"✅ {saude['modelo']}")
        metricas = saude.get('metricas', {})
        st.metric("R²",  f"{metricas.get('R2', 'N/A')}")
        st.metric("MAE", f"{metricas.get('MAE', 'N/A')} casos/semana")
    else:
        st.error("❌ API indisponível")

    st.markdown("---")
    st.caption(f"Atualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    st.caption("IFMT — Projeto Extensionista 2026")
    st.caption("Ediney Magalhães")

# ============================================================
# CABEÇALHO
# ============================================================
st.markdown("# 🦟 Sistema Preditivo de Dengue — MT")
st.markdown("**Cuiabá e Várzea Grande | Instituto Federal de Mato Grosso (IFMT)**")

# ============================================================
# BANNER DE DRIFT — status do modelo em tempo real
# ============================================================
render_banner_drift()

st.markdown("---")

# ============================================================
# MÉTRICAS PRINCIPAIS
# ============================================================
import pandas as pd

df_hist = get_historico()

if df_hist is not None:
    df_hist['data_se'] = pd.to_datetime(df_hist['data_se'])
    df_hist['ano']     = df_hist['data_se'].dt.year

    # Agrega ambos municípios por semana
    df_sem = df_hist.groupby('data_se')['casos_confirmados'].sum().reset_index()
    df_sem = df_sem.sort_values('data_se')

    ano_atual    = df_hist['ano'].max()
    ultima_se    = int(df_sem['casos_confirmados'].iloc[-1])
    media_4se    = int(df_sem['casos_confirmados'].tail(4).mean())
    total_ano    = int(df_hist[df_hist['ano'] == ano_atual]['casos_confirmados'].sum())
    pico_ano     = int(df_hist[df_hist['ano'] == ano_atual]['casos_confirmados'].max())

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📅 Última SE",
                  f"{ultima_se} casos",
                  delta=f"{ultima_se - media_4se:+.0f} vs média 4SE")
    with col2:
        st.metric("📊 Média 4 semanas", f"{media_4se} casos/SE")
    with col3:
        st.metric(f"📈 Total {ano_atual}", f"{total_ano:,} casos")
    with col4:
        st.metric(f"⚠️ Pico {ano_atual}", f"{pico_ano} casos/SE")

st.markdown("---")

# ============================================================
# ABAS
# ============================================================
aba1, aba2, aba3, aba4, aba5 = st.tabs([
    "🗺️ Mapa de Risco",
    "📈 Série Temporal",
    "🤖 Previsão",
    "📊 Monitoramento",
    "ℹ️ Sobre"
])

with aba1:
    render_aba_mapa()

with aba2:
    render_aba_serie()

with aba3:
    render_aba_previsao(horizonte)

with aba4:
    render_aba_monitoramento()

with aba5:
    render_aba_sobre()