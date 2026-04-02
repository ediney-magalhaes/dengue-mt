# ============================================================
# Dengue MT — Componente: Aba Série Temporal
# ============================================================

import streamlit as st
import plotly.express as px
import pandas as pd
from components.dados import get_historico


def render_aba_serie():
    st.subheader("Evolução dos Casos Confirmados — MT (2018–2024)")

    df_hist = get_historico()

    if df_hist is None:
        st.error("❌ Dados históricos indisponíveis")
        return

    df_hist['data'] = pd.to_datetime(df_hist['data'])
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

    df_hist['mes'] = df_hist['data'].dt.month
    pivot = df_hist.groupby(['ano', 'mes'])['casos'].sum().unstack()
    pivot.columns = ['Jan','Fev','Mar','Abr','Mai','Jun',
                     'Jul','Ago','Set','Out','Nov','Dez']
    fig2 = px.imshow(pivot, color_continuous_scale='YlOrRd',
                     title="Sazonalidade — Casos por Mês/Ano")
    fig2.update_layout(height=350)
    st.plotly_chart(fig2, use_container_width=True)