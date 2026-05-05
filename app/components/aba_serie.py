# ============================================================
# Dengue MT — Componente: Aba Série Temporal v5
# ============================================================
# Município controlado pelo sidebar (parâmetro)
# Filtro de período (ano) é específico desta aba
# ============================================================

import streamlit as st
import plotly.express as px
import pandas as pd
from components.dados import get_historico

MUNICIPIOS_ID = {
    'Cuiabá':        5103403,
    'Várzea Grande': 5108402,
}


def render_aba_serie(municipio_sel: str = 'Todos'):
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

    # ── Filtro de período (específico desta aba) ──────────
    col_f1, col_f2 = st.columns(2)
    anos = sorted(df_hist['ano'].unique())
    with col_f1:
        ano_ini = st.selectbox("Ano início", anos, index=0)
    with col_f2:
        ano_fim = st.selectbox("Ano fim", anos, index=len(anos)-1)

    # ── Filtra período ─────────────────────────────────────
    df_fil = df_hist[
        (df_hist['ano'] >= ano_ini) &
        (df_hist['ano'] <= ano_fim)
    ].copy()

    # ── Filtra município (vem do sidebar) ──────────────────
    if municipio_sel != 'Todos':
        mun_id = MUNICIPIOS_ID.get(municipio_sel)
        if mun_id:
            df_fil = df_fil[df_fil['municipio_id'] == mun_id]

    label_mun = municipio_sel

    # Agrega por semana (soma municípios se "Todos")
    df_sem = df_fil.groupby('data_se')['casos_confirmados'].sum().reset_index()

    # ── Gráfico série temporal ─────────────────────────────
    fig1 = px.area(
        df_sem, x='data_se', y='casos_confirmados',
        title=f"Casos semanais — {label_mun} — {ano_ini} a {ano_fim}",
        labels={'data_se': 'Semana Epidemiológica', 'casos_confirmados': 'Casos'},
        color_discrete_sequence=['#e63946']
    )
    fig1.update_layout(height=400, hovermode='x unified')
    st.plotly_chart(fig1, use_container_width=True)

    # ── Heatmap sazonalidade ───────────────────────────────
    pivot = df_fil.groupby(['ano', 'mes'])['casos_confirmados'].sum().unstack()
    meses_map = {1:'Jan', 2:'Fev', 3:'Mar', 4:'Abr', 5:'Mai', 6:'Jun',
                 7:'Jul', 8:'Ago', 9:'Set', 10:'Out', 11:'Nov', 12:'Dez'}
    pivot.columns = [meses_map.get(c, c) for c in pivot.columns]

    fig2 = px.imshow(
        pivot,
        color_continuous_scale='YlOrRd',
        title=f"Sazonalidade — Casos por Mês/Ano — {label_mun}",
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