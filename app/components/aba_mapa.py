# ============================================================
# Dengue MT — Componente: Aba Mapa de Risco
# ============================================================

import streamlit as st
import folium
import pandas as pd
from streamlit_folium import st_folium
from components.dados import get_score_risco_hf


def render_aba_mapa():
    st.subheader("🗺️ Mapa de Risco por Unidade de Saúde")
    st.caption("Score baseado na carga histórica SINAN 2007-2024 × CNES | Percentil rank")

    score_data = get_score_risco_hf()

    if not score_data:
        st.error("❌ Dados de risco indisponíveis")
        return

    df_score = pd.DataFrame(score_data['unidades'])
    dist     = score_data['distribuicao']

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🔴 Muito Alto",  dist.get('Muito Alto', 0))
    c2.metric("🟠 Alto",        dist.get('Alto', 0))
    c3.metric("🟡 Moderado",    dist.get('Moderado', 0))
    c4.metric("🔵 Baixo",       dist.get('Baixo', 0))
    c5.metric("⚫ Muito Baixo", dist.get('Muito Baixo', 0))

    st.markdown("---")

    mapa = folium.Map(location=[-15.62, -56.09], zoom_start=12,
                      tiles='CartoDB positron')

    cores = {
        'Muito Alto':  '#d73027',
        'Alto':        '#fc8d59',
        'Moderado':    '#fee090',
        'Baixo':       '#91bfdb',
        'Muito Baixo': '#4575b4'
    }

    for _, row in df_score.iterrows():
        lat = row.get('latitude_estabelecimento_decimo_grau')
        lon = row.get('longitude_estabelecimento_decimo_grau')
        if pd.isna(lat) or pd.isna(lon):
            continue

        cor   = cores.get(row.get('risco_v2', 'Muito Baixo'), '#4575b4')
        baixa = row.get('baixa_confianca', False)

        folium.CircleMarker(
            location=[lat, lon],
            radius=5 + row.get('score_v2', 0) * 15,
            color='gray' if baixa else cor,
            fill=True, fill_color=cor,
            fill_opacity=0.4 if baixa else 0.85,
            popup=folium.Popup(
                f"<b>{row.get('nome_fantasia','N/A')}</b><br>"
                f"Bairro: {row.get('bairro_estabelecimento','N/A')}<br>"
                f"Casos históricos: {row.get('casos_historicos',0):,}<br>"
                f"Score: {row.get('score_v2',0):.2f}<br>"
                f"Risco: <b>{row.get('risco_v2','N/A')}</b><br>"
                f"{'⚠️ Baixa Confiança' if baixa else '✅ Alta Confiança'}",
                max_width=260
            ),
            tooltip=f"{row.get('nome_fantasia','N/A')} — {row.get('risco_v2','N/A')}"
        ).add_to(mapa)

    legenda = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
         background-color: white; padding: 12px; border-radius: 8px;
         border: 2px solid #ccc; font-size: 12px; line-height: 1.8;">
    <b>🦟 Score de Risco — Dengue MT</b><br>
    🔴 Muito Alto (top 20%)<br>
    🟠 Alto (60–80%)<br>
    🟡 Moderado (40–60%)<br>
    🔵 Baixo (20–40%)<br>
    ⚫ Muito Baixo (bottom 20%)<br>
    <b>Borda cinza = Baixa Confiança</b>
    </div>
    """
    mapa.get_root().html.add_child(folium.Element(legenda))
    st_folium(mapa, width=None, height=550, returned_objects=[])