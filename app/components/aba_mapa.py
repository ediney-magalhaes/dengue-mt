# ============================================================
# Dengue MT — Componente: Aba Mapa v4.0
# ============================================================
# Distribuição espacial de casos previstos por bairro (IDW)
# Fonte: previsao_bairros_latest.geojson (HF Hub)
# Horizonte controlado pelo sidebar (unificado)
# Limiares adaptativos lidos do GeoJSON — zero hardcode
# ============================================================

import streamlit as st
import folium
import pandas as pd
from streamlit_folium import st_folium
from components.dados import get_previsao_bairros


CORES_RISCO = {
    'Muito Alto':  '#d73027',
    'Alto':        '#fc8d59',
    'Moderado':    '#fee090',
    'Baixo':       '#91bfdb',
    'Muito Baixo': '#4575b4',
}

EMOJI_RISCO = {
    'Muito Alto':  '🔴',
    'Alto':        '🟠',
    'Moderado':    '🟡',
    'Baixo':       '🔵',
    'Muito Baixo': '⚫',
}

MUNICIPIOS = {
    '5103403': 'Cuiabá',
    '5108402': 'Várzea Grande',
}


def _gerar_legenda_html(limiares: dict) -> str:
    """
    Gera legenda HTML dinâmica a partir dos limiares adaptativos.
    Se não há limiares, mostra legenda genérica por nível.
    """
    # Pega os limiares do primeiro município como referência visual
    # (a classificação real usa os limiares de cada município)
    if limiares:
        lim = list(limiares.values())[0]
        p60 = lim['P60']
        p75 = lim['P75']
        p85 = lim['P85']
        p95 = lim['P95']
        linhas = (
            f"🔴 Muito Alto (&gt;{p95:.2f} casos)<br>"
            f"🟠 Alto ({p85:.2f}–{p95:.2f} casos)<br>"
            f"🟡 Moderado ({p75:.2f}–{p85:.2f} casos)<br>"
            f"🔵 Baixo ({p60:.2f}–{p75:.2f} casos)<br>"
            f"⚫ Muito Baixo (&lt;{p60:.2f} casos)<br>"
        )
    else:
        linhas = (
            "🔴 Muito Alto<br>"
            "🟠 Alto<br>"
            "🟡 Moderado<br>"
            "🔵 Baixo<br>"
            "⚫ Muito Baixo<br>"
        )

    return f"""
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
         background-color: white; padding: 12px; border-radius: 8px;
         border: 2px solid #ccc; font-size: 12px; line-height: 1.8;">
    <b>🦟 Casos Previstos — Dengue MT</b><br>
    {linhas}
    <hr style="margin:4px 0">
    <i>Previsão LightGBM v5 × IDW</i><br>
    <i>Limiares adaptativos (percentis)</i>
    </div>
    """


def render_aba_mapa():
    st.subheader("🗺️ Distribuição Espacial de Casos Previstos")
    st.caption(
        "Previsão de casos distribuída por bairro via IDW (Inverse Distance Weighting). "
        "Modelo LightGBM v5 atualizado automaticamente toda semana."
    )

    # Carrega GeoDataFrame + limiares (fonte única: GeoJSON)
    resultado = get_previsao_bairros()

    if resultado is None or resultado[0] is None:
        st.error("❌ Dados de previsão por bairro indisponíveis")
        return

    gdf, limiares = resultado

    if gdf.empty:
        st.error("❌ Dados de previsão por bairro indisponíveis")
        return

    # ── Horizonte vem do sidebar (controle unificado) ─────
    horizonte = st.session_state.get('horizonte_semanas', 2)

    # ── Filtro de município ───────────────────────────────
    mun_opcoes = ['Todos'] + list(MUNICIPIOS.values())
    mun_sel    = st.selectbox("Município", mun_opcoes, index=0)

    # Colunas do horizonte selecionado
    col_casos = f'casos_se{horizonte}'
    col_nivel = f'nivel_risco_se{horizonte}'
    col_cor   = f'cor_se{horizonte}'

    # Verifica se as colunas existem
    if col_casos not in gdf.columns:
        st.warning(f"⚠️ Horizonte SE+{horizonte} não disponível nos dados.")
        return

    # Filtra município
    gdf_fil = gdf.copy()
    if mun_sel != 'Todos':
        cd_mun = [k for k, v in MUNICIPIOS.items() if v == mun_sel][0]
        gdf_fil = gdf_fil[gdf_fil['CD_MUN'] == cd_mun]

    # ── Métricas resumo ───────────────────────────────────
    dist = gdf_fil[col_nivel].value_counts().to_dict()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🔴 Muito Alto",  dist.get('Muito Alto', 0))
    c2.metric("🟠 Alto",        dist.get('Alto', 0))
    c3.metric("🟡 Moderado",    dist.get('Moderado', 0))
    c4.metric("🔵 Baixo",       dist.get('Baixo', 0))
    c5.metric("⚫ Muito Baixo", dist.get('Muito Baixo', 0))

    st.markdown("---")

    # ── Mapa choropleth ───────────────────────────────────
    centro = [-15.62, -56.09] if mun_sel == 'Todos' else (
        [-15.5989, -56.0949] if mun_sel == 'Cuiabá' else [-15.6461, -56.1324]
    )
    zoom = 11 if mun_sel == 'Todos' else 12

    mapa = folium.Map(
        location=centro,
        zoom_start=zoom,
        tiles='CartoDB positron'
    )

    for _, row in gdf_fil.iterrows():
        cor   = CORES_RISCO.get(row[col_nivel], '#4575b4')
        casos = row[col_casos]
        nivel = row[col_nivel]

        folium.GeoJson(
            data=row['geometry'].__geo_interface__,
            style_function=lambda x, c=cor: {
                'fillColor':   c,
                'color':       '#555555',
                'weight':      0.5,
                'fillOpacity': 0.75,
            },
            tooltip=folium.Tooltip(
                f"<b>{row['NM_BAIRRO']}</b><br>"
                f"Município: {row['NM_MUN']}<br>"
                f"Casos previstos SE+{horizonte}: <b>{casos:.2f}</b><br>"
                f"Classificação: <b style='color:{cor}'>{nivel}</b>",
                sticky=True
            ),
            popup=folium.Popup(
                "<b>{}</b> — {}<br><br>{}".format(
                    row['NM_BAIRRO'],
                    row['NM_MUN'],
                    '<br>'.join([
                        'SE+{}: {:.2f} casos ({})'.format(
                            h, row[f'casos_se{h}'], row[f'nivel_risco_se{h}']
                        )
                        for h in range(1, 5)
                        if f'casos_se{h}' in row.index
                    ])
                ),
                max_width=250
            )
        ).add_to(mapa)

    # Legenda dinâmica
    # Usa limiares do município filtrado, ou do primeiro se "Todos"
    if mun_sel != 'Todos':
        cd_sel = [k for k, v in MUNICIPIOS.items() if v == mun_sel][0]
        lim_legenda = {cd_sel: limiares.get(cd_sel, {})}
    else:
        lim_legenda = limiares

    legenda_html = _gerar_legenda_html(lim_legenda)
    mapa.get_root().html.add_child(folium.Element(legenda_html))

    st_folium(mapa, width=None, height=560, returned_objects=[])

    # ── Tabela top bairros ─────────────────────────────────
    st.markdown(f"### 📋 Top 10 Bairros — Maior Concentração Prevista (SE+{horizonte})")
    df_top = (
        gdf_fil[['NM_BAIRRO', 'NM_MUN', col_casos, col_nivel]]
        .sort_values(col_casos, ascending=False)
        .head(10)
        .rename(columns={
            'NM_BAIRRO': 'Bairro',
            'NM_MUN':    'Município',
            col_casos:   'Casos previstos',
            col_nivel:   'Classificação',
        })
    )
    st.dataframe(df_top, use_container_width=True, hide_index=True)

    # ── Nota metodológica ─────────────────────────────────
    st.markdown("---")
    st.info(
        "**Metodologia:** Previsão de casos municipais via LightGBM v5 distribuída "
        "espacialmente por bairro usando Inverse Distance Weighting (IDW) com pesos "
        "calibrados pelo histórico de notificações por UBS (SINAN + CNES). "
        "Propriedade pycnophylactic preservada — Σ casos bairros = previsão municipal. "
        "Classificação por limiares adaptativos (percentis P60/P75/P85/P95) "
        "recalculados automaticamente a cada execução semanal."
    )