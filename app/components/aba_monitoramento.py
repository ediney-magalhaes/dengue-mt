# ============================================================
# Dengue MT — Componente: Aba Monitoramento
# ============================================================
# Para gestores de saúde — gráficos interativos de monitoramento
# Lê histórico de execuções do HF Hub e run_metadata.json local
# ============================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from components.dados import get_run_metadata, carregar_do_hf


@st.cache_data(ttl=1800)
def carregar_historico_runs():
    """
    Carrega histórico de execuções do HF Hub.
    Tenta carregar reports/historico_runs.parquet — gerado pelo pipeline.
    Fallback: usa apenas o run_metadata.json local.
    """
    # Tenta HF Hub primeiro
    df = carregar_do_hf('reports/historico_runs.parquet')
    if df is not None:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df.sort_values('timestamp')

    # Fallback — apenas run atual
    meta = get_run_metadata()
    if meta is None:
        return None

    row = {
        'timestamp':    pd.to_datetime(meta.get('timestamp', datetime.now().isoformat())),
        'drift_score':  meta.get('drift_score'),
        'nivel_drift':  meta.get('nivel_drift', 'desconhecido'),
        'drift_mae':    meta.get('drift_mae'),
        'drift_r2':     meta.get('drift_r2'),
        'retreino':     meta.get('retreino', 'nao_executado'),
        'inmet':        meta.get('fallbacks', {}).get('inmet', False),
        'nasa':         meta.get('fallbacks', {}).get('nasa', False),
        'oni':          meta.get('fallbacks', {}).get('oni', False),
        'trends':       meta.get('fallbacks', {}).get('trends', False),
    }
    return pd.DataFrame([row])


def _cor_nivel(nivel):
    return {'normal': '#28a745', 'moderado': '#ffc107', 'critico': '#dc3545'}.get(nivel, '#6c757d')


def render_aba_monitoramento():
    st.subheader("📊 Monitoramento do Pipeline")
    st.caption("Histórico de execuções, drift e saúde do modelo")

    df = carregar_historico_runs()

    if df is None or df.empty:
        st.warning("⚠️ Sem histórico de execuções disponível.")
        return

    # ── Cards de status atual ──────────────────────────────
    ultimo = df.iloc[-1]
    st.markdown("### Status da Última Execução")

    c1, c2, c3, c4 = st.columns(4)
    nivel = ultimo.get('nivel_drift', 'desconhecido')
    emoji = {'normal': '🟢', 'moderado': '🟡', 'critico': '🔴'}.get(nivel, '⚪')

    c1.metric("🎯 Drift Score",
              f"{float(ultimo['drift_score']):.3f}" if ultimo.get('drift_score') else 'N/A',
              delta=None)
    c2.metric("📉 MAE (90d)",
              f"{ultimo.get('drift_mae', 'N/A')} casos/dia")
    c3.metric("📈 R² (90d)",
              f"{ultimo.get('drift_r2', 'N/A')}")
    c4.metric(f"{emoji} Nível Drift",
              nivel.capitalize())

    st.markdown("---")

    # ── Gráfico drift score ao longo do tempo ─────────────
    if len(df) > 1:
        st.markdown("### 📉 Drift Score — Histórico")

        fig = go.Figure()

        # Linha do drift score
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['drift_score'],
            mode='lines+markers',
            name='Drift Score',
            line=dict(color='#2a9d8f', width=2),
            marker=dict(size=8)
        ))

        # Limiares
        fig.add_hline(y=0.3, line_dash='dash', line_color='#ffc107',
                      annotation_text='Limiar Moderado (0.3)')
        fig.add_hline(y=0.6, line_dash='dash', line_color='#dc3545',
                      annotation_text='Limiar Crítico (0.6)')

        fig.update_layout(
            height=300,
            yaxis_title='Wasserstein Distance (normalizada)',
            xaxis_title='Data de Execução',
            hovermode='x unified',
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Gráfico MAE e R² ao longo do tempo ────────────────
    if len(df) > 1 and 'drift_mae' in df.columns:
        st.markdown("### 📊 Métricas do Modelo — Histórico")

        col1, col2 = st.columns(2)

        with col1:
            fig_mae = px.line(df, x='timestamp', y='drift_mae',
                              title='MAE recente (90d)',
                              markers=True,
                              color_discrete_sequence=['#e63946'])
            fig_mae.add_hline(y=25, line_dash='dash', line_color='gray',
                              annotation_text='Limiar retreino (25)')
            fig_mae.update_layout(height=280, showlegend=False,
                                  yaxis_title='casos/dia')
            st.plotly_chart(fig_mae, use_container_width=True)

        with col2:
            fig_r2 = px.line(df, x='timestamp', y='drift_r2',
                             title='R² recente (90d)',
                             markers=True,
                             color_discrete_sequence=['#2a9d8f'])
            fig_r2.add_hline(y=0.75, line_dash='dash', line_color='gray',
                             annotation_text='Limiar mínimo (0.75)')
            fig_r2.update_layout(height=280, showlegend=False,
                                 yaxis_title='R²', yaxis_range=[0, 1])
            st.plotly_chart(fig_r2, use_container_width=True)

    # ── Histórico de retreinos ─────────────────────────────
    st.markdown("### 🔁 Histórico de Decisões")
    cores_retreino = {
        'promovido':     '🚀',
        'mantido':       '⚠️',
        'nao_executado': '✅',
        'erro':          '❌'
    }
    df_display = df[['timestamp', 'nivel_drift', 'drift_score',
                     'drift_mae', 'drift_r2', 'retreino']].copy()
    df_display['timestamp'] = pd.to_datetime(df_display['timestamp']).dt.strftime('%Y-%m-%d %H:%M')
    df_display['nivel_drift'] = df_display['nivel_drift'].apply(
        lambda x: f"{'🟢' if x=='normal' else '🟡' if x=='moderado' else '🔴'} {x}"
    )
    df_display['retreino'] = df_display['retreino'].apply(
        lambda x: f"{cores_retreino.get(x, '?')} {x}"
    )
    df_display.columns = ['Data', 'Drift', 'Score', 'MAE', 'R²', 'Decisão']
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    # ── Link relatório técnico ─────────────────────────────
    st.markdown("---")
    st.markdown("### 📄 Relatório Técnico Completo")
    url = "https://huggingface.co/datasets/edyestatistica/dengue-mt-medallion/blob/main/reports/execucao_latest.md"
    st.markdown(f"[📋 Ver último relatório no HF Hub]({url})")
    st.caption("Relatório detalhado com status de todas as etapas, fallbacks e cache.")