"""
dashboard.py — v2
Dashboard interativo — Sistema Preditivo de Dengue MT
Conectado à FastAPI + Mapa Folium

Como rodar:
    streamlit run app/dashboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests
import folium
from streamlit_folium import st_folium
from pathlib import Path
from datetime import datetime, timedelta

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(
    page_title="Dengue MT — Sistema Preditivo",
    page_icon="🦟",
    layout="wide",
    initial_sidebar_state="expanded"
)

API_URL = "http://127.0.0.1:8000"

# ============================================================
# FUNÇÕES DE ACESSO À API
# ============================================================
@st.cache_data(ttl=300)
def get_previsao(dias=14):
    try:
        r = requests.get(f"{API_URL}/previsao", params={"dias": dias}, timeout=10)
        return r.json() if r.status_code == 200 else None
    except:
        return None

@st.cache_data(ttl=300)
def get_score_risco():
    try:
        r = requests.get(f"{API_URL}/score-risco", timeout=10)
        return r.json() if r.status_code == 200 else None
    except:
        return None

@st.cache_data(ttl=300)
def get_saude():
    try:
        r = requests.get(f"{API_URL}/saude", timeout=10)
        return r.json() if r.status_code == 200 else None
    except:
        return None

@st.cache_data(ttl=3600)
def get_historico():
    try:
        r = requests.get(f"{API_URL}/historico", timeout=10)
        if r.status_code == 200:
            data = r.json()
            df = pd.DataFrame(data['serie'])
            df['data'] = pd.to_datetime(df['data'])
            return df
    except:
        pass
    # Fallback local
    try:
        df = pd.read_parquet('data/gold/dataset_features_v4.parquet')
        df['data'] = pd.to_datetime(df['data'])
        return df[['data', 'casos']].sort_values('data')
    except:
        return None

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
        st.metric("R²", f"{metricas.get('R2', 'N/A')}")
        st.metric("MAE", f"{metricas.get('MAE', 'N/A')} casos/dia")
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
st.markdown("---")

# ============================================================
# MÉTRICAS PRINCIPAIS
# ============================================================
df_hist = get_historico()

if df_hist is not None:
    casos_ultimo = int(df_hist['casos'].iloc[-1])
    media_7d = int(df_hist['casos'].tail(7).mean())
    total_2024 = int(df_hist[df_hist['data'].dt.year == 2024]['casos'].sum())
    pico_2024 = int(df_hist[df_hist['data'].dt.year == 2024]['casos'].max())

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📅 Último registro",
                  f"{casos_ultimo} casos",
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
aba1, aba2, aba3, aba4 = st.tabs([
    "🗺️ Mapa de Risco",
    "📈 Série Temporal",
    "🤖 Previsão",
    "ℹ️ Sobre"
])

# ============================================================
# ABA 1 — MAPA DE RISCO (carro-chefe!)
# ============================================================
with aba1:
    st.subheader("🗺️ Mapa de Risco por Unidade de Saúde")
    st.caption("Score baseado na carga histórica SINAN 2007-2024 × CNES | Percentil rank")

    score_data = get_score_risco()

    if score_data:
        df_score = pd.DataFrame(score_data['unidades'])

        # Métricas do mapa
        dist = score_data['distribuicao']
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("🔴 Muito Alto", dist.get('Muito Alto', 0))
        c2.metric("🟠 Alto", dist.get('Alto', 0))
        c3.metric("🟡 Moderado", dist.get('Moderado', 0))
        c4.metric("🔵 Baixo", dist.get('Baixo', 0))
        c5.metric("⚫ Muito Baixo", dist.get('Muito Baixo', 0))

        st.markdown("---")

        # Construir mapa Folium
        mapa = folium.Map(
            location=[-15.62, -56.09],
            zoom_start=12,
            tiles='CartoDB positron'
        )

        cores = {
            'Muito Alto':  '#d73027',
            'Alto':        '#fc8d59',
            'Moderado':    '#fee090',
            'Baixo':       '#91bfdb',
            'Muito Baixo': '#4575b4'
        }

        for _, row in df_score.iterrows():
            lat = row.get('latitude_estabelecimento_decimo_grau')
            lon = row.get('longitude_estabelecimento_decimo_grau')
            if pd.isna(lat) or pd.isna(lon):
                continue

            cor = cores.get(row.get('risco_v2', 'Muito Baixo'), '#4575b4')
            baixa = row.get('baixa_confianca', False)

            folium.CircleMarker(
                location=[lat, lon],
                radius=5 + row.get('score_v2', 0) * 15,
                color='gray' if baixa else cor,
                fill=True,
                fill_color=cor,
                fill_opacity=0.4 if baixa else 0.85,
                popup=folium.Popup(
                    f"<b>{row.get('nome_fantasia','N/A')}</b><br>"
                    f"Bairro: {row.get('bairro_estabelecimento','N/A')}<br>"
                    f"Casos históricos: {row.get('casos_historicos',0):,}<br>"
                    f"Score: {row.get('score_v2',0):.2f}<br>"
                    f"Risco: <b>{row.get('risco_v2','N/A')}</b><br>"
                    f"{'⚠️ Baixa Confiança' if baixa else '✅ Alta Confiança'}",
                    max_width=260
                ),
                tooltip=f"{row.get('nome_fantasia','N/A')} — {row.get('risco_v2','N/A')}"
            ).add_to(mapa)

        # Legenda
        legenda = """
        <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
             background-color: white; padding: 12px; border-radius: 8px;
             border: 2px solid #ccc; font-size: 12px; line-height: 1.8;">
        <b>🦟 Score de Risco — Dengue MT</b><br>
        🔴 Muito Alto (top 20%)<br>
        🟠 Alto (60–80%)<br>
        🟡 Moderado (40–60%)<br>
        🔵 Baixo (20–40%)<br>
        ⚫ Muito Baixo (bottom 20%)<br>
        <b>Borda cinza = Baixa Confiança</b>
        </div>
        """
        mapa.get_root().html.add_child(folium.Element(legenda))

        st_folium(mapa, width=None, height=550, returned_objects=[])

    else:
        st.error("❌ API indisponível — verifique se a FastAPI está rodando na porta 8000")

# ============================================================
# ABA 2 — SÉRIE TEMPORAL
# ============================================================
with aba2:
    st.subheader("Evolução dos Casos Confirmados — MT (2018–2024)")

    if df_hist is not None:
        df_hist['ano'] = df_hist['data'].dt.year
        anos = sorted(df_hist['ano'].unique())

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            ano_ini = st.selectbox("Ano início", anos, index=0)
        with col_f2:
            ano_fim = st.selectbox("Ano fim", anos, index=len(anos)-1)

        df_fil = df_hist[(df_hist['ano'] >= ano_ini) & (df_hist['ano'] <= ano_fim)]
        df_sem = df_fil.set_index('data')['casos'].resample('W').sum().reset_index()

        fig1 = px.area(df_sem, x='data', y='casos',
                       title=f"Casos semanais — {ano_ini} a {ano_fim}",
                       color_discrete_sequence=['#e63946'])
        fig1.update_layout(height=400)
        st.plotly_chart(fig1, use_container_width=True)

        # Heatmap sazonal
        df_hist['mes'] = df_hist['data'].dt.month
        pivot = df_hist.groupby(['ano','mes'])['casos'].sum().unstack()
        pivot.columns = ['Jan','Fev','Mar','Abr','Mai','Jun',
                         'Jul','Ago','Set','Out','Nov','Dez']
        fig2 = px.imshow(pivot, color_continuous_scale='YlOrRd',
                         title="Sazonalidade — Casos por Mês/Ano")
        fig2.update_layout(height=350)
        st.plotly_chart(fig2, use_container_width=True)

# ============================================================
# ABA 3 — PREVISÃO
# ============================================================
with aba3:
    st.subheader("🤖 Previsão de Casos — Próximos dias")

    prev_data = get_previsao(horizonte)

    if prev_data and df_hist is not None:
        df_prev = pd.DataFrame(prev_data['previsoes'])
        df_prev['data'] = pd.to_datetime(df_prev['data'])

        st.info(f"""
        **Modelo:** {prev_data['modelo']} | 
        **Última data conhecida:** {prev_data['ultima_data_conhecida']} | 
        **Horizonte:** {horizonte} dias
        """)

        # Gráfico histórico + previsão
        df_h60 = df_hist.tail(60)

        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=df_h60['data'], y=df_h60['casos'],
            name='Histórico', line=dict(color='#e63946', width=2)
        ))
        fig3.add_trace(go.Scatter(
            x=df_prev['data'], y=df_prev['casos_previstos'],
            name='Previsão', line=dict(color='#2a9d8f', width=2, dash='dash'),
            mode='lines+markers'
        ))
        fig3.add_shape(
            type='line',
            x0=prev_data['ultima_data_conhecida'],
            x1=prev_data['ultima_data_conhecida'],
            y0=0, y1=1,
            yref='paper',
            line=dict(color='gray', dash='dot', width=1)
        )
        fig3.add_annotation(
            x=prev_data['ultima_data_conhecida'],
            y=1, yref='paper',
            text='Hoje', showarrow=False,
            font=dict(color='gray')
        )
        fig3.update_layout(
            title=f"Previsão — próximos {horizonte} dias",
            yaxis_title='Casos/dia', height=420,
            hovermode='x unified'
        )
        st.plotly_chart(fig3, use_container_width=True)

        # Tabela de previsões + alertas
        st.subheader("📋 Previsões detalhadas")
        cores_alerta = {
            'Muito Alto': '🔴',
            'Alto': '🟠',
            'Moderado': '🟡',
            'Baixo': '🔵',
            'Muito Baixo': '⚫'
        }
        df_prev['alerta'] = df_prev['nivel_risco'].map(cores_alerta)
        st.dataframe(
            df_prev[['data', 'casos_previstos', 'nivel_risco', 'alerta']],
            use_container_width=True, hide_index=True
        )

        media_prev = df_prev['casos_previstos'].mean()
        if media_prev > 150:
            st.error(f"🚨 **ALERTA ALTO** — Média prevista: {media_prev:.0f} casos/dia")
        elif media_prev > 50:
            st.warning(f"⚠️ **ALERTA MODERADO** — Média prevista: {media_prev:.0f} casos/dia")
        else:
            st.success(f"✅ **NÍVEL BAIXO** — Média prevista: {media_prev:.0f} casos/dia")
    else:
        st.error("❌ API indisponível")

# ============================================================
# ABA 4 — SOBRE
# ============================================================
with aba4:
    st.subheader("ℹ️ Sobre o Sistema")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("""
        ### 🎯 Objetivo
        Antecipar surtos de dengue em Cuiabá e Várzea Grande/MT
        com **2 a 4 semanas de antecedência**.

        ### 📊 Fontes de dados
        - **SINAN/DATASUS** — 390k registros (2007–2024)
        - **INMET A901** — clima diário Cuiabá
        - **NASA POWER** — radiação solar
        - **GEE Sentinel-2/MODIS** — NDVI, NDWI, NDBI
        - **NOAA** — ONI Index (ENSO)
        - **Google Trends** — Infoveillance (r=0.922)
        """)
    with col_b:
        st.markdown("""
        ### 🤖 Evolução dos modelos

        | Modelo | R² | sMAPE |
        |---|---|---|
        | LightGBM v2 | 0.830 | N/A |
        | LightGBM v3 | 0.829 | 32.4% |
        | LightGBM v4 | 0.820 | 31.5% |

        ### 🏛️ Instituição
        Instituto Federal de Mato Grosso (IFMT)
        Projeto Extensionista — 2026
        **Ediney Magalhães**
        """)

    st.markdown("---")
    st.markdown("""
    ### ⚖️ Ética e Conformidade
    - Dados agregados — sem identificação individual (LGPD)
    - Modelo interpretável via SHAP values
    - Código aberto: [github.com/ediney-magalhaes/dengue-mt](https://github.com/ediney-magalhaes/dengue-mt)
    """)