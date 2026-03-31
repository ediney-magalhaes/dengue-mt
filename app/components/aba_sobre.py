# ============================================================
# Dengue MT — Componente: Aba Sobre
# ============================================================

import streamlit as st


def render_aba_sobre():
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

        | Modelo | R² | sMAPE | Validação |
        |---|---|---|---|
        | LightGBM v2 | 0.830 | N/A | Rolling Window |
        | LightGBM v3 | 0.829 | 32.4% | Rolling Window |
        | **LightGBM v4** | **0.820** | **31.5%** | **TimeSeriesSplit** |

        > Métrica oficial: TimeSeriesSplit 5-fold — academicamente defensável.

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