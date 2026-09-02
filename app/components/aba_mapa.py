# ============================================================
# Dengue MT — Componente: Aba Mapa v5.0
# ============================================================
# Distribuição espacial de casos previstos por bairro (IDW)
# Fonte: previsao_bairros_latest.geojson (HF Hub)
# Horizonte e município controlados pelo sidebar (parâmetros)
# Limiares adaptativos lidos do GeoJSON — zero hardcode
# ============================================================

import streamlit as st
import folium
import os
from streamlit_folium import st_folium
from components.dados import get_previsao_bairros
from components.dados import get_previsao_bairros, get_previsao_bairros_snapshot


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

def _get_carto_key() -> str:
    """
    Busca a chave CARTO API — variável de ambiente (.env local)
    ou secrets do Streamlit Cloud (produção).
    """
    chave = os.getenv('CARTO_API_KEY')
    if chave:
        return chave
    try:
        return st.secrets.get('CARTO_API_KEY', '')
    except Exception:
        return ''


CARTO_API_KEY = _get_carto_key()
CARTO_TILES_URL = (
    'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png?key=' + CARTO_API_KEY
)

def _gerar_legenda_html(limiares: dict, mun_sel: str) -> str:
    """
    Gera legenda HTML dinâmica a partir dos limiares adaptativos.
    Quando 'Todos', usa limiares do primeiro município como referência.
    Quando um município específico, usa os limiares dele.
    """
    lim_exibir = None

    if mun_sel != 'Todos':
        cd_sel = [k for k, v in MUNICIPIOS.items() if v == mun_sel]
        if cd_sel and cd_sel[0] in limiares:
            lim_exibir = limiares[cd_sel[0]]

    if lim_exibir is None and limiares:
        # "Todos" — mostra limiares de cada município separadamente
        blocos = []
        for cd_mun, lim in limiares.items():
            nome = MUNICIPIOS.get(cd_mun, cd_mun)
            blocos.append(
                f"<b>{nome}:</b><br>"
                f"&nbsp; 🔴 Muito Alto (&gt;{lim['P95']:.2f})<br>"
                f"&nbsp; 🟠 Alto ({lim['P85']:.2f}–{lim['P95']:.2f})<br>"
                f"&nbsp; 🟡 Moderado ({lim['P75']:.2f}–{lim['P85']:.2f})<br>"
                f"&nbsp; 🔵 Baixo ({lim['P60']:.2f}–{lim['P75']:.2f})<br>"
                f"&nbsp; ⚫ Muito Baixo (&lt;{lim['P60']:.2f})<br>"
            )
        linhas = "<br>".join(blocos)
    elif lim_exibir:
        linhas = (
            f"🔴 Muito Alto (&gt;{lim_exibir['P95']:.2f} casos)<br>"
            f"🟠 Alto ({lim_exibir['P85']:.2f}–{lim_exibir['P95']:.2f})<br>"
            f"🟡 Moderado ({lim_exibir['P75']:.2f}–{lim_exibir['P85']:.2f})<br>"
            f"🔵 Baixo ({lim_exibir['P60']:.2f}–{lim_exibir['P75']:.2f})<br>"
            f"⚫ Muito Baixo (&lt;{lim_exibir['P60']:.2f})<br>"
        )
    else:
        linhas = (
            "🔴 Muito Alto<br>🟠 Alto<br>"
            "🟡 Moderado<br>🔵 Baixo<br>⚫ Muito Baixo<br>"
        )

    return f"""
    <div style="font-size: 13px; line-height: 1.8;">
    {linhas}
    <hr style="margin:8px 0">
    <i>Previsão LightGBM Direct CQR × IDW</i><br>
    <i>Limiares adaptativos (percentis)</i>
    </div>
    """


def render_aba_mapa(horizonte: int = 2, mun_sel: str = 'Todos', semana_hist: str = 'Semana atual'):
    """
    Renderiza mapa choropleth de distribuição espacial de casos previstos.

    Parâmetros:
        horizonte: semana epidemiológica futura (1-4)
        mun_sel: 'Todos', 'Cuiabá' ou 'Várzea Grande'
    """
    st.subheader("🗺️ Distribuição Espacial de Casos Previstos")
    st.caption(
        "Previsão de casos distribuída por bairro via IDW (Inverse Distance Weighting). "
        "Modelo LightGBM Direct Multi-Step (CQR 90%) atualizado automaticamente toda semana. "
        "Os indicadores abaixo mostram a quantidade de bairros em cada faixa de classificação."
    )

    # ── Carrega GeoDataFrame + limiares (fonte única: GeoJSON) ──
    if semana_hist == 'Semana atual':
        resultado = get_previsao_bairros()
    else:
        resultado = get_previsao_bairros_snapshot(semana_hist)

    if resultado is None or resultado[0] is None:
        st.error("❌ Dados não disponíveis para a semana selecionada.")
        return

    gdf, limiares = resultado

    # Colunas dinâmicas baseadas no horizonte
    col_casos = f'casos_se{horizonte}'
    col_nivel = f'nivel_risco_se{horizonte}'
    col_cor   = f'cor_se{horizonte}'

    # Verifica se as colunas do horizonte existem
    if col_casos not in gdf.columns:
        st.error(f"❌ Horizonte SE+{horizonte} não disponível nos dados.")
        return

    # Filtra município
    gdf_fil = gdf.copy()
    if mun_sel != 'Todos':
        cd_mun = [k for k, v in MUNICIPIOS.items() if v == mun_sel]
        if cd_mun:
            gdf_fil = gdf_fil[gdf_fil['CD_MUN'] == cd_mun[0]]

    if gdf_fil.empty:
        st.warning("⚠️ Nenhum bairro encontrado para o filtro selecionado.")
        return

    # ── Métricas resumo ───────────────────────────────────────
    dist = gdf_fil[col_nivel].value_counts().to_dict()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🔴 Muito Alto",  f"{dist.get('Muito Alto', 0)} bairros")
    c2.metric("🟠 Alto",        f"{dist.get('Alto', 0)} bairros")
    c3.metric("🟡 Moderado",    f"{dist.get('Moderado', 0)} bairros")
    c4.metric("🔵 Baixo",       f"{dist.get('Baixo', 0)} bairros")
    c5.metric("⚫ Muito Baixo", f"{dist.get('Muito Baixo', 0)} bairros")

    st.markdown("---")

    # ── Mapa choropleth ───────────────────────────────────────
    centro = [-15.62, -56.09] if mun_sel == 'Todos' else (
        [-15.5989, -56.0949] if mun_sel == 'Cuiabá' else [-15.6461, -56.1324]
    )
    zoom = 11 if mun_sel == 'Todos' else 12

    if not CARTO_API_KEY:
        st.warning(
            "⚠️ CARTO_API_KEY não configurada — o mapa pode exibir "
            "marca d'água 'API KEY REQUIRED'. Configure a chave no .env."
        )

    mapa = folium.Map(
        location=centro,
        zoom_start=zoom,
        tiles=None,
    )
    folium.TileLayer(
        tiles=CARTO_TILES_URL,
        attr=(
            '&copy; <a href="https://www.openstreetmap.org/copyright">'
            'OpenStreetMap</a> contributors &copy; '
            '<a href="https://carto.com/attributions">CARTO</a>'
        ),
        name='CartoDB Positron',
        subdomains='abcd',
        max_zoom=20,
    ).add_to(mapa)

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
                "<b>{}</b><br>"
                "Município: {}<br>"
                "Casos previstos SE+{}: <b>{:.2f}</b><br>"
                "Classificação: <b style='color:{}'>{}</b>".format(
                    row['NM_BAIRRO'], row['NM_MUN'],
                    horizonte, casos, cor, nivel
                ),
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
    st_folium(mapa, use_container_width=True, height=560, returned_objects=[])

    with st.expander("🔍 Ver legenda de classificação de risco"):
        legenda_html = _gerar_legenda_html(limiares, mun_sel)
        st.markdown(legenda_html, unsafe_allow_html=True)

    # ── Tabela top bairros ────────────────────────────────────
    st.markdown(
        f"### 📋 Top 10 Bairros — Maior Concentração Prevista (SE+{horizonte})"
    )
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

    # ── Nota metodológica ─────────────────────────────────────
    st.markdown("---")
    st.info(
        "**Metodologia:** Previsão de casos municipais via LightGBM Direct Multi-Step "
        "(4 horizontes: SE+1, +2, +4, +8 — bandas CQR 90% calibradas) distribuída "
        "espacialmente por bairro usando Inverse Distance Weighting (IDW) com pesos "
        "calibrados pelo histórico de notificações por UBS (SINAN + CNES). "
        "Propriedade pycnophylactic preservada — Σ casos bairros = previsão municipal. "
        "Classificação por limiares adaptativos (percentis P60/P75/P85/P95) "
        "recalculados automaticamente a cada execução semanal."
    )