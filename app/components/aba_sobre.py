# ============================================================
# Dengue MT — Componente: Aba Sobre v2.0
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
        - **InfoDengue API** — casos + nowcast + Rt + clima ERA5 (Fiocruz)
        - **NASA POWER** — temperatura, precipitação, radiação, umidade
        - **MODIS MOD13A3** — NDVI e EVI via AppEEARS NASA
        - **NOAA ONI** — El Niño/La Niña (índice climático global)
        - **Google Trends** — infoveillância digital (BR-MT)

        ### 🏗️ Arquitetura
        - Pipeline: dbt-core + DuckDB (medallion)
        - Orquestração: Prefect 3.x
        - CI/CD: GitHub Actions (domingo 06h)
        - Armazenamento: Hugging Face Hub
        """)
    with col_b:
        st.markdown("""
        ### 🤖 Modelo em produção

        | Métrica | Valor |
        |---|---|
        | **Modelo** | LightGBM v5 |
        | **R²** | 0.741 ± 0.081 |
        | **MAE** | 9.7 ± 6.2 casos/semana |
        | **Validação** | TimeSeriesSplit 5 folds |
        | **Features** | 54 → 12 (SHAP) |
        | **Período** | 2018–2025 |

        > Métrica oficial: TimeSeriesSplit 5-fold —
        > academicamente defensável para publicação.
        > Ver [ADR-006](https://github.com/ediney-magalhaes/dengue-mt/blob/main/reports/adr/006-metrica-oficial-timeseriessplit.md).

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
    - Custo total de infraestrutura: R$ 0,00
    - Código aberto: [github.com/ediney-magalhaes/dengue-mt](https://github.com/ediney-magalhaes/dengue-mt)
    - Dataset público: [HF Hub](https://huggingface.co/datasets/edyestatistica/dengue-mt-medallion)
    """)