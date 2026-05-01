# ============================================================
# Dengue MT — Componente: Aba Mapa de Risco v3.0
# ============================================================
# Mapa choropleth IDW dinâmico — previsão semanal por bairro
# Fonte: previsao_bairros_latest.geojson (HF Hub)
# Slider SE+1 → SE+4
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

MUNICIPIOS = {
    '5103403': 'Cuiabá',
    '5108402': 'Várzea Grande',
}


def render_aba_mapa():
    st.subheader("🗺️ Mapa de Risco por Bairro — Previsão Semanal")
    st.caption(
        "Previsão de casos distribuída por bairro via IDW (Inverse Distance Weighting). "
        "Modelo LightGBM v5 atualizado automaticamente toda semana."
    )

    # Carrega GeoDataFrame
    gdf = get_previsao_bairros()

    if gdf is None or gdf.empty:
        st.error("❌ Dados de previsão por bairro indisponíveis")
        return

    # ── Controles ─────────────────────────────────────────
    col1, col2 = st.columns([1, 2])
    with col1:
        horizonte = st.radio(
            "Horizonte de previsão",
            options=[1, 2, 3, 4],
            format_func=lambda x: f"SE+{x} ({x} semana{'s' if x > 1 else ''})",
            horizontal=False,
            index=0,
        )
    with col2:
        mun_opcoes = ['Todos'] + list(MUNICIPIOS.values())
        mun_sel    = st.selectbox("Município", mun_opcoes, index=0)

    # Colunas do horizonte selecionado
    col_casos  = f'casos_se{horizonte}'
    col_nivel  = f'nivel_risco_se{horizonte}'
    col_cor    = f'cor_se{horizonte}'

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

    # Choropleth por bairro
    for _, row in gdf_fil.iterrows():
        cor    = CORES_RISCO.get(row[col_nivel], '#4575b4')
        casos  = row[col_casos]
        nivel  = row[col_nivel]

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
                f"Casos previstos SE+{horizonte}: <b>{casos:.1f}</b><br>"
                f"Risco: <b style='color:{cor}'>{nivel}</b>",
                sticky=True
            ),
            popup=folium.Popup(
                "<b>{}</b> — {}<br><br>{}".format(
                    row['NM_BAIRRO'],
                    row['NM_MUN'],
                    '<br>'.join([
                        'SE+{}: {:.1f} casos ({})'.format(
                            h, row[f'casos_se{h}'], row[f'nivel_risco_se{h}']
                        )
                        for h in range(1, 5)
                    ])
                ),
                max_width=250
            )
        ).add_to(mapa)

    # Legenda
    legenda_html = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
         background-color: white; padding: 12px; border-radius: 8px;
         border: 2px solid #ccc; font-size: 12px; line-height: 1.8;">
    <b>🦟 Risco Previsto — Dengue MT</b><br>
    🔴 Muito Alto (&gt;200 casos)<br>
    🟠 Alto (100–200 casos)<br>
    🟡 Moderado (50–100 casos)<br>
    🔵 Baixo (20–50 casos)<br>
    ⚫ Muito Baixo (&lt;20 casos)<br>
    <hr style="margin:4px 0">
    <i>Previsão LightGBM v5 × IDW</i>
    </div>
    """
    mapa.get_root().html.add_child(folium.Element(legenda_html))

    st_folium(mapa, width=None, height=560, returned_objects=[])

    # ── Tabela top bairros ─────────────────────────────────
    st.markdown(f"### 📋 Top 10 Bairros — Maior Risco Previsto (SE+{horizonte})")
    df_top = (
        gdf_fil[['NM_BAIRRO', 'NM_MUN', col_casos, col_nivel]]
        .sort_values(col_casos, ascending=False)
        .head(10)
        .rename(columns={
            'NM_BAIRRO': 'Bairro',
            'NM_MUN':    'Município',
            col_casos:   'Casos previstos',
            col_nivel:   'Nível de risco',
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
        "Atualização automática toda semana."
    )