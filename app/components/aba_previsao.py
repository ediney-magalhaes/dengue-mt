# ============================================================
# Dengue MT — Componente: Aba Previsão v2.0
# ============================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from components.dados import (
    get_previsao, get_historico,
    carregar_modelo_hf, carregar_do_hf, fazer_previsao_local
)

HF_GOLD_LATEST = 'gold/dataset_features_latest.parquet'


def render_aba_previsao(horizonte: int):
    st.subheader("🤖 Previsão de Casos — Próximas semanas")

    # horizonte já vem em semanas (1-4) — dashboard.py v4
    semanas = max(horizonte, 1)

    prev_data = get_previsao(semanas)

    if not prev_data:
        modelo_hf    = carregar_modelo_hf()
        df_gold_full = carregar_do_hf(HF_GOLD_LATEST)
        if modelo_hf is not None and df_gold_full is not None:
            prev_data = fazer_previsao_local(modelo_hf, df_gold_full, semanas)

    df_hist = get_historico()

    if prev_data and df_hist is not None:
        df_prev = pd.DataFrame(prev_data['previsoes'])
        df_prev['data_se'] = pd.to_datetime(df_prev['data_se'])

        st.info(f"""
        **Modelo:** {prev_data['modelo']} |
        **Última data conhecida:** {prev_data['ultima_data_conhecida']} |
        **Horizonte:** {semanas} semanas
        """)

        # Filtro por município
        municipios = {5103403: 'Cuiabá', 5108402: 'Várzea Grande'}
        mun_opcoes = list(municipios.values())
        mun_selecionado = st.selectbox("Município", mun_opcoes, index=0)
        mun_id = [k for k, v in municipios.items() if v == mun_selecionado][0]

        # Filtrar dados
        df_hist_mun = df_hist[df_hist['municipio_id'] == mun_id].copy()
        df_prev_mun = df_prev[df_prev['municipio_id'] == mun_id].copy()

        df_h60 = df_hist_mun.tail(60)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_h60['data_se'], y=df_h60['casos_confirmados'],
            name='Histórico', line=dict(color='#e63946', width=2)
        ))
        fig.add_trace(go.Scatter(
            x=df_prev_mun['data_se'], y=df_prev_mun['casos_previstos'],
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
            text='Último dado', showarrow=False,
            font=dict(color='gray')
        )
        fig.update_layout(
            title=f"Previsão — {mun_selecionado} — próximas {semanas} semanas",
            yaxis_title='Casos/semana', height=420,
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📋 Previsões detalhadas")
        cores_alerta = {
            'Muito Alto': '🔴', 'Alto': '🟠',
            'Moderado': '🟡', 'Baixo': '🔵', 'Muito Baixo': '⚫'
        }
        df_prev_mun['alerta'] = df_prev_mun['nivel_risco'].map(cores_alerta)
        st.dataframe(
            df_prev_mun[['data_se', 'casos_previstos', 'nivel_risco', 'alerta']],
            use_container_width=True, hide_index=True
        )

        media_prev = df_prev_mun['casos_previstos'].mean()
        if media_prev > 150:
            st.error(f"🚨 **ALERTA ALTO** — Média prevista: {media_prev:.0f} casos/semana")
        elif media_prev > 50:
            st.warning(f"⚠️ **ALERTA MODERADO** — Média prevista: {media_prev:.0f} casos/semana")
        else:
            st.success(f"✅ **NÍVEL BAIXO** — Média prevista: {media_prev:.0f} casos/semana")
    else:
        st.error("❌ Dados de previsão indisponíveis")