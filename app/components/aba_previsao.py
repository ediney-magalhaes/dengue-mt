# ============================================================
# Dengue MT — Componente: Aba Previsão
# ============================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from components.dados import (
    get_previsao, get_historico,
    carregar_modelo_hf, carregar_do_hf, fazer_previsao_local
)


def render_aba_previsao(horizonte: int):
    st.subheader("🤖 Previsão de Casos — Próximos dias")

    prev_data = get_previsao(horizonte)

    if not prev_data:
        modelo_hf    = carregar_modelo_hf()
        df_gold_full = carregar_do_hf('gold/dataset_features_v4.parquet')
        if modelo_hf is not None and df_gold_full is not None:
            prev_data = fazer_previsao_local(modelo_hf, df_gold_full, horizonte)

    df_hist = get_historico()

    if prev_data and df_hist is not None:
        df_prev = pd.DataFrame(prev_data['previsoes'])
        df_prev['data'] = pd.to_datetime(df_prev['data'])

        st.info(f"""
        **Modelo:** {prev_data['modelo']} |
        **Última data conhecida:** {prev_data['ultima_data_conhecida']} |
        **Horizonte:** {horizonte} dias
        """)

        df_h60 = df_hist.tail(60)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_h60['data'], y=df_h60['casos'],
            name='Histórico', line=dict(color='#e63946', width=2)
        ))
        fig.add_trace(go.Scatter(
            x=df_prev['data'], y=df_prev['casos_previstos'],
            name='Previsão',
            line=dict(color='#2a9d8f', width=2, dash='dash'),
            mode='lines+markers'
        ))
        fig.add_shape(
            type='line',
            x0=prev_data['ultima_data_conhecida'],
            x1=prev_data['ultima_data_conhecida'],
            y0=0, y1=1, yref='paper',
            line=dict(color='gray', dash='dot', width=1)
        )
        fig.add_annotation(
            x=prev_data['ultima_data_conhecida'],
            y=1, yref='paper',
            text='Hoje', showarrow=False,
            font=dict(color='gray')
        )
        fig.update_layout(
            title=f"Previsão — próximos {horizonte} dias",
            yaxis_title='Casos/dia', height=420,
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📋 Previsões detalhadas")
        cores_alerta = {
            'Muito Alto': '🔴', 'Alto': '🟠',
            'Moderado': '🟡', 'Baixo': '🔵', 'Muito Baixo': '⚫'
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
        st.error("❌ Dados de previsão indisponíveis")