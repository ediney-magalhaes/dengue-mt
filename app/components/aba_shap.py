# ============================================================
# Dengue MT — Componente: Aba Explicabilidade (SHAP) v1.0
# ============================================================
# Exibe análise SHAP dos modelos Direct CQR (q50)
# Figuras geradas por: notebooks/backtesting/04_shap_direct_cqr.py
# Atualizar figuras após cada retreino do pipeline semanal
#
# Referências:
#   - Lundberg & Lee (NeurIPS 2017) — SHAP
#   - Lundberg et al. (Nature MI 2020) — TreeSHAP
#   - Taieb & Hyndman (2014) — Direct multi-step forecasting
# ============================================================

import streamlit as st
from pathlib import Path

# ── Paths das figuras ─────────────────────────────────────────────────────────
# Relativo ao dashboard.py em app/
ASSETS_DIR = Path(__file__).parent.parent / 'assets' / 'shap'
DIR_GLOBAL = ASSETS_DIR / 'global'
DIR_MUN    = ASSETS_DIR / 'municipios'

MUNICIPIOS_SLUG = {
    'Todos':         None,
    'Cuiabá':        'cuiaba',
    'Várzea Grande': 'varzea_grande',
}

HORIZONTES = [1, 2, 4, 8]

# Nomes legíveis para features que aparecem nos títulos
FEATURE_LABELS = {
    'casos_mm4':             'Casos MM4 (média móvel 4 semanas)',
    'notif_acum_ano_lag1':   'Notificações acumuladas no ano (lag 1)',
    'casos_lag1':            'Casos confirmados (lag 1 semana)',
    'precip_acum8':          'Precipitação acumulada 8 semanas',
    'populacao':             'População do município',
}


def _img(path: Path) -> bool:
    """Verifica se imagem existe antes de exibir."""
    return path.exists()


def _titulo_horizonte(h: int) -> str:
    return {
        1: 'SE+1 — Próxima semana',
        2: 'SE+2 — 2 semanas à frente',
        4: 'SE+4 — 1 mês à frente',
        8: 'SE+8 — 2 meses à frente',
    }[h]


def render_aba_shap(horizonte: int, municipio_sel: str = 'Todos'):
    st.subheader("🔍 Explicabilidade do Modelo — Análise SHAP")

    st.markdown(
        """
        **O que é SHAP?** É uma técnica que explica *por que* o modelo fez
        cada previsão — mostrando quais informações mais influenciaram o
        resultado. Cada barra ou ponto representa a contribuição de uma
        variável para a previsão daquela semana.

        > Referência: Lundberg & Lee (NeurIPS 2017) — *A Unified Approach
        > to Interpreting Model Predictions*
        """
    )

    st.info(
        f"🎯 Exibindo análise para: **Horizonte SE+{horizonte}** | "
        f"**{municipio_sel}** — "
        "Use o seletor na barra lateral para alterar."
    )

    # ── Seção 1: Importância das features (Bar chart) ─────────────────────────
    st.markdown("---")
    st.markdown("### 📊 Quais variáveis mais influenciam a previsão?")
    st.markdown(
        "O gráfico abaixo mostra as 20 variáveis com maior impacto médio "
        "na previsão. Quanto maior a barra, mais aquela variável contribui "
        "para o resultado do modelo."
    )

    slug = MUNICIPIOS_SLUG.get(municipio_sel)

    if slug is None:
        # Global — ambos municípios
        path_bar = DIR_GLOBAL / f'fig02_h{horizonte}_bar_top20.png'
        legenda_bar = f"Top 20 features — Horizonte {_titulo_horizonte(horizonte)} (ambos municípios)"
    else:
        path_bar = DIR_MUN / f'fig02_h{horizonte}_{slug}_bar_top20.png'
        legenda_bar = f"Top 20 features — Horizonte {_titulo_horizonte(horizonte)} | {municipio_sel}"

    if _img(path_bar):
        st.image(str(path_bar), caption=legenda_bar, use_container_width=True)
    else:
        st.warning(
            "⚠️ Figura não encontrada. Execute o script de análise SHAP: "
            "`python notebooks/backtesting/04_shap_direct_cqr.py`"
        )

    # Legenda de cores
    with st.expander("🎨 O que significam as cores das barras?"):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("🔴 **Epidemiológico** — Casos anteriores, Rt, alertas")
            st.markdown("🔵 **Climático** — Temperatura, umidade, precipitação")
        with col2:
            st.markdown("🟢 **Vegetação** — NDVI, NDWI (cobertura vegetal)")
            st.markdown("🟠 **ENSO** — Índice ONI (El Niño/La Niña)")
        with col3:
            st.markdown("🟣 **Infoveillance** — Google Trends")
            st.markdown("⚫ **Outros** — Sazonalidade, população")

    # ── Seção 2: Beeswarm ─────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🐝 Direção do efeito de cada variável")
    st.markdown(
        "Cada ponto representa uma semana epidemiológica. "
        "**Pontos à direita** aumentam a previsão de casos; "
        "**pontos à esquerda** a reduzem. "
        "A cor indica o valor da variável: "
        "**vermelho = valor alto**, **azul = valor baixo**."
    )

    if slug is None:
        path_bee = DIR_GLOBAL / f'fig01_h{horizonte}_beeswarm.png'
        legenda_bee = f"Beeswarm SHAP — Horizonte {_titulo_horizonte(horizonte)} (global)"
    else:
        path_bee = DIR_MUN / f'fig01_h{horizonte}_{slug}_beeswarm.png'
        legenda_bee = f"Beeswarm SHAP — Horizonte {_titulo_horizonte(horizonte)} | {municipio_sel}"

    if _img(path_bee):
        st.image(str(path_bee), caption=legenda_bee, use_container_width=True)
    else:
        st.warning("⚠️ Figura não encontrada.")

    with st.expander("📖 Como ler este gráfico?"):
        st.markdown(
            """
            - **Eixo horizontal (SHAP value):** impacto na previsão.
              Valores positivos aumentam a previsão; negativos reduzem.
            - **Cor do ponto:** valor da variável naquela semana.
              Vermelho = valor alto; azul = valor baixo.
            - **Exemplo:** se *Casos MM4* tem pontos vermelhos à direita,
              significa que semanas com muitos casos recentes tendem a
              gerar previsões mais altas — o modelo "reconhece" o momentum
              epidêmico.
            """
        )

    # ── Seção 3: Importância por fase epidêmica ───────────────────────────────
    st.markdown("---")
    st.markdown("### 📅 Como as variáveis mudam ao longo do ano?")
    st.markdown(
        "O modelo usa variáveis diferentes dependendo da fase do ciclo "
        "epidêmico. Durante o surto (jan-mai), o momentum de casos recentes "
        "domina. Na entressafra (jun-set), fatores climáticos e sazonais "
        "ganham mais peso."
    )

    path_temp = DIR_GLOBAL / f'fig04_h{horizonte}_temporal.png'
    if _img(path_temp):
        st.image(
            str(path_temp),
            caption=f"Importância SHAP por fase epidêmica — Horizonte {_titulo_horizonte(horizonte)}",
            use_container_width=True,
        )
    else:
        st.warning("⚠️ Figura não encontrada.")

    # ── Seção 4: Comparativo entre horizontes ─────────────────────────────────
    st.markdown("---")
    st.markdown("### 🔭 Como a estratégia do modelo muda com o horizonte?")
    st.markdown(
        """
        À medida que o horizonte aumenta de **SE+1** (próxima semana) para
        **SE+8** (2 meses à frente), o modelo muda de estratégia:

        - **Horizontes curtos (SE+1, SE+2):** predomina o *momentum* —
          quantos casos houve nas últimas semanas.
        - **Horizontes longos (SE+4, SE+8):** ganham peso a sazonalidade
          histórica e a precipitação acumulada — o modelo "olha mais para
          o ambiente" quando não pode mais confiar nos dados mais recentes.

        Este padrão é consistente com a literatura de previsão multi-step
        (Taieb & Hyndman, 2014).
        """
    )

    path_comp = DIR_GLOBAL / 'fig05_comparativo_horizontes.png'
    if _img(path_comp):
        st.image(
            str(path_comp),
            caption="Comparativo de importância SHAP entre horizontes (h=1, 2, 4, 8)",
            use_container_width=True,
        )
    else:
        st.warning("⚠️ Figura não encontrada.")

    # ── Rodapé técnico ────────────────────────────────────────────────────────
    st.markdown("---")
    with st.expander("🔬 Detalhes técnicos"):
        st.markdown(
            f"""
            **Método:** SHAP TreeExplainer (exato para modelos baseados em árvores)

            **Modelos analisados:** LightGBM Direct Multi-Step — quantil 0.50
            (mediana) para cada horizonte

            **Horizontes:** SE+1, SE+2, SE+4, SE+8 semanas epidemiológicas

            **Features:** {46} variáveis preditoras (epidemiológicas,
            climáticas, ENSO, Google Trends, sazonalidade)

            **Dados:** Gold dataset — Cuiabá e Várzea Grande, 2018–2026

            **Escala dos valores SHAP:** espaço log1p — o ranking de
            importância é preservado pela transformação monotônica

            **Quando atualizar:** após cada retreino do pipeline semanal,
            execute `python notebooks/backtesting/04_shap_direct_cqr.py`

            **Referências:**
            - Lundberg & Lee (NeurIPS 2017) — SHAP
            - Lundberg et al. (Nature MI 2020) — TreeSHAP
            - Taieb & Hyndman (2014) — Direct multi-step forecasting
            - Romano et al. (2019) — Conformalized Quantile Regression
            """
        )