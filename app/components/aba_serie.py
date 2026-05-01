# ============================================================
# Dengue MT — Componente: Aba Série Temporal
# ============================================================

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from components.dados import get_historico


def render_aba_serie():
    df_hist = get_historico()

    if df_hist is None:
        st.error("❌ Dados históricos indisponíveis")
        return

    df_hist['data_se'] = pd.to_datetime(df_hist['data_se'])
    df_hist['ano']     = df_hist['data_se'].dt.year
    df_hist['mes']     = df_hist['data_se'].dt.month

    ano_min = int(df_hist['ano'].min())
    ano_max = int(df_hist['ano'].max())

    st.subheader(f"Evolução dos Casos Confirmados — MT ({ano_min}–{ano_max})")

    # ── Filtros ───────────────────────────────────────────
    col_f1, col_f2, col_f3 = st.columns(3)
    anos = sorted(df_hist['ano'].unique())
    with col_f1:
        ano_ini = st.selectbox("Ano início", anos, index=0)
    with col_f2:
        ano_fim = st.selectbox("Ano fim", anos, index=len(anos)-1)
    with col_f3:
        municipios = {5103403: 'Cuiabá', 5108402: 'Várzea Grande', 0: 'Ambos'}
        mun_opcao  = st.selectbox("Município", list(municipios.values()), index=2)
        mun_id     = [k for k, v in municipios.items() if v == mun_opcao][0]

    # ── Filtra período e município ─────────────────────────
    df_fil = df_hist[
        (df_hist['ano'] >= ano_ini) &
        (df_hist['ano'] <= ano_fim)
    ].copy()

    if mun_id != 0:
        df_fil = df_fil[df_fil['municipio_id'] == mun_id]

    # Agrega por semana (soma municípios se "Ambos")
    df_sem = df_fil.groupby('data_se')['casos_confirmados'].sum().reset_index()

    # ── Gráfico série temporal ─────────────────────────────
    fig1 = px.area(
        df_sem, x='data_se', y='casos_confirmados',
        title=f"Casos semanais — {mun_opcao} — {ano_ini} a {ano_fim}",
        labels={'data_se': 'Semana Epidemiológica', 'casos_confirmados': 'Casos'},
        color_discrete_sequence=['#e63946']
    )
    fig1.update_layout(height=400, hovermode='x unified')
    st.plotly_chart(fig1, use_container_width=True)

    # ── Heatmap sazonalidade ───────────────────────────────
    pivot = df_fil.groupby(['ano', 'mes'])['casos_confirmados'].sum().unstack()
    pivot.columns = ['Jan','Fev','Mar','Abr','Mai','Jun',
                     'Jul','Ago','Set','Out','Nov','Dez']

    fig2 = px.imshow(
        pivot,
        color_continuous_scale='YlOrRd',
        title=f"Sazonalidade — Casos por Mês/Ano — {mun_opcao}",
        labels={'x': 'Mês', 'y': 'Ano', 'color': 'Casos'}
    )
    fig2.update_layout(height=350)
    st.plotly_chart(fig2, use_container_width=True)

    # ── Métricas rápidas ───────────────────────────────────
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total no período",  f"{int(df_sem['casos_confirmados'].sum()):,}")
    c2.metric("Pico semanal",      f"{int(df_sem['casos_confirmados'].max()):,} casos")
    c3.metric("Média semanal",     f"{df_sem['casos_confirmados'].mean():.0f} casos")