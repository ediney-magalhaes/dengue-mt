"""
dashboard.py — v3
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
        "Horizonte de previsão (dias)",
        min_value=7, max_value=28, value=14, step=7
    )

    st.markdown("---")
    st.markdown("### 📊 Status do Modelo")
    saude = get_saude()
    if saude:
        st.success(f"✅ {saude['modelo']}")
        metricas = saude.get('metricas', {})
        st.metric("R²",    f"{metricas.get('R2', 'N/A')}")
        st.metric("MAE",   f"{metricas.get('MAE', 'N/A')} casos/dia")
        st.metric("sMAPE", f"{metricas.get('sMAPE', 'N/A')}%")
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
df_hist = get_historico()

if df_hist is not None:
    casos_ultimo = int(df_hist['casos'].iloc[-1])
    media_7d     = int(df_hist['casos'].tail(7).mean())
    total_2024   = int(df_hist[df_hist['data'].dt.year == 2024]['casos'].sum())
    pico_2024    = int(df_hist[df_hist['data'].dt.year == 2024]['casos'].max())

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📅 Último registro", f"{casos_ultimo} casos",
                  delta=f"{casos_ultimo - media_7d:+.0f} vs média 7d")
    with col2:
        st.metric("📊 Média 7 dias", f"{media_7d} casos/dia")
    with col3:
        st.metric("📈 Total 2024", f"{total_2024:,} casos")
    with col4:
        st.metric("⚠️ Pico 2024", f"{pico_2024} casos/dia")

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