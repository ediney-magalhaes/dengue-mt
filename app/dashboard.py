"""
dashboard.py — v5
Dashboard interativo — Sistema Preditivo de Dengue MT
Modularizado em app/components/
Como rodar:
    streamlit run app/dashboard.py
"""
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
load_dotenv()
from components.dados import get_saude, get_historico
from components.banner_drift import render_banner_drift
from components.aba_mapa import render_aba_mapa
from components.dados import get_lista_snapshots_bairros
from components.aba_serie import render_aba_serie
from components.aba_previsao import render_aba_previsao
from components.aba_sobre import render_aba_sobre
from components.aba_monitoramento import render_aba_monitoramento
from components.aba_shap import render_aba_shap
from components.relatorio_pdf import gerar_pdf_boletim

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
    st.markdown("*Cuiabá e Várzea Grande — IFMT*")
    st.markdown("---")

    horizonte = st.select_slider(
        "Horizonte de previsão (semanas)",
        options=[1, 2, 4, 8],
        value=2
    )
    st.caption("Aplica-se ao Mapa e Previsão")

    municipio_sel = st.selectbox(
        "Município",
        options=["Todos", "Cuiabá", "Várzea Grande"],
        index=0
    )

    # Histórico de mapas — só visível na aba Mapa
    st.markdown("---")
    snapshots      = get_lista_snapshots_bairros()
    opcoes_hist    = ['Semana atual'] + snapshots
    semana_hist    = st.selectbox(
        "🗓️ Semana do mapa",
        options=opcoes_hist,
        index=0,
        help="Semana atual = previsão mais recente. "
             "Selecione uma data anterior para comparar a evolução espacial.",
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
        st.warning("⚠️ Metadados do modelo indisponíveis")

    st.markdown("---")
    render_banner_drift()

# ============================================================
# TÍTULO E CABEÇALHO
# ============================================================
st.title("🦟 Sistema Preditivo de Dengue — MT")
st.caption(
    "Cuiabá e Várzea Grande | Instituto Federal de Mato Grosso (IFMT)"
)

# ── Métricas resumo ─────────────────────────────────────────
df_hist = get_historico()

if df_hist is not None and not df_hist.empty:
    df_hist['data_se'] = pd.to_datetime(df_hist['data_se'])
    ano_atual = df_hist['data_se'].dt.year.max()

    ultima_se = int(df_hist['casos_confirmados'].iloc[-1])
    media_4se = int(df_hist['casos_confirmados'].tail(4).mean())
    total_ano = int(
        df_hist[df_hist['data_se'].dt.year == ano_atual]['casos_confirmados'].sum()
    )
    pico_ano = int(
        df_hist[df_hist['data_se'].dt.year == ano_atual]['casos_confirmados'].max()
    )

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
aba1, aba2, aba3, aba4, aba5, aba6 = st.tabs([
    "🗺️ Mapa de Risco",
    "📈 Série Temporal",
    "🤖 Previsão",
    "📊 Monitoramento",
    "🔍 Explicabilidade",
    "ℹ️ Sobre"
])

with aba1:
    render_aba_mapa(horizonte, municipio_sel, semana_hist)

    st.markdown("---")
    st.markdown("#### 📄 Exportar Boletim")
    if st.button("Gerar PDF desta semana", type="primary"):
        with st.spinner("Gerando boletim... aguarde (consulta IA)"):
            from components.dados import get_previsao_bairros, get_previsao_bairros_snapshot
            if semana_hist == 'Semana atual':
                gdf_pdf, limiares_pdf = get_previsao_bairros()
            else:
                gdf_pdf, limiares_pdf = get_previsao_bairros_snapshot(semana_hist)

            if gdf_pdf is not None:
                pdf_bytes = gerar_pdf_boletim(
                    gdf_pdf, limiares_pdf,
                    horizonte, municipio_sel, semana_hist
                )
                nome_arquivo = (
                    f"boletim_dengue_mt_SE{horizonte}_"
                    f"{semana_hist.replace(' ', '_')}_{municipio_sel}.pdf"
                )
                st.download_button(
                    label="⬇️ Baixar PDF",
                    data=pdf_bytes,
                    file_name=nome_arquivo,
                    mime="application/pdf",
                )
            else:
                st.error("Não foi possível carregar os dados para gerar o PDF.")

with aba2:
    render_aba_serie(municipio_sel)

with aba3:
    render_aba_previsao(horizonte, municipio_sel)

with aba4:
    render_aba_monitoramento()

with aba5:
    render_aba_shap(horizonte, municipio_sel)

with aba6:
    render_aba_sobre()