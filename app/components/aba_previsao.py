# ============================================================
# Dengue MT — Componente: Aba Previsão v4.0
# ============================================================
# Direct CQR: modelo por horizonte + bandas calibradas 90%
# Fallback: modelo pontual único (sem bandas)
# ============================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from components.dados import (
    get_previsao, get_historico,
    carregar_modelo_hf, carregar_modelos_direct_hf,
    carregar_do_hf, fazer_previsao_local,
    HORIZONTES_DIRECT
)

HF_GOLD_LATEST = 'gold/dataset_features_latest.parquet'

MUNICIPIOS_ID = {
    'Cuiabá':        5103403,
    'Várzea Grande': 5108402,
}


def render_aba_previsao(horizonte: int, municipio_sel: str = 'Todos'):
    st.subheader("🤖 Previsão de Casos — Próximas semanas")

    semanas = max(horizonte, 1)

    # Tenta carregar modelos Direct CQR
    modelos_direct, metadata_direct = carregar_modelos_direct_hf()

    prev_data = None

    # Previsão local com Direct CQR ou fallback
    modelo_hf    = carregar_modelo_hf()
    df_gold_full = carregar_do_hf(HF_GOLD_LATEST)

    if df_gold_full is not None:
        prev_data = fazer_previsao_local(
            modelo_hf, df_gold_full, semanas,
            modelos_direct=modelos_direct,
            metadata_direct=metadata_direct
        )

    # Fallback API
    if not prev_data:
        prev_data = get_previsao(semanas)

    df_hist = get_historico()

    if prev_data and df_hist is not None:
        df_prev = pd.DataFrame(prev_data['previsoes'])
        df_prev['data_se'] = pd.to_datetime(df_prev['data_se'])

        tem_bandas = prev_data.get('tem_bandas', False)

        info_texto = (
            f"**Modelo:** {prev_data['modelo']} | "
            f"**Última data conhecida:** {prev_data['ultima_data_conhecida']} | "
            f"**Horizontes:** SE+{', +'.join(str(h) for h in HORIZONTES_DIRECT)}"
        )
        if tem_bandas:
            info_texto += " | **Bandas:** CQR 90% calibrada"
        st.info(info_texto)

        # ── Filtra município (vem do sidebar) ──────────────
        if municipio_sel == 'Todos':
            mun_ids = list(MUNICIPIOS_ID.values())
        else:
            mun_ids = [MUNICIPIOS_ID[municipio_sel]]

        for mun_id in mun_ids:
            mun_nome = next(k for k, v in MUNICIPIOS_ID.items() if v == mun_id)

            df_hist_mun = df_hist[df_hist['municipio_id'] == mun_id].copy()
            df_prev_mun = df_prev[df_prev['municipio_id'] == mun_id].copy()
            # Filtrar horizontes pelo slider do sidebar
            df_prev_mun = df_prev_mun[df_prev_mun['horizonte_se'] <= semanas].copy()

            if df_hist_mun.empty or df_prev_mun.empty:
                continue

            df_h60 = df_hist_mun.tail(60)

            fig = go.Figure()

            # Histórico
            fig.add_trace(go.Scatter(
                x=df_h60['data_se'], y=df_h60['casos_confirmados'],
                name='Histórico', line=dict(color='#e63946', width=2)
            ))

            # Banda CQR (se disponível) — plotar ANTES da linha de previsão
            if tem_bandas and 'lower' in df_prev_mun.columns:
                # Upper bound (invisível, serve de topo da banda)
                fig.add_trace(go.Scatter(
                    x=df_prev_mun['data_se'],
                    y=df_prev_mun['upper'],
                    mode='lines',
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo='skip'
                ))
                # Lower bound com fill até o upper
                fig.add_trace(go.Scatter(
                    x=df_prev_mun['data_se'],
                    y=df_prev_mun['lower'],
                    mode='lines',
                    line=dict(width=0),
                    fill='tonexty',
                    fillcolor='rgba(42, 157, 143, 0.2)',
                    name='Banda CQR 90%',
                    hovertemplate='Lower: %{y:.0f}<extra></extra>'
                ))

            # Previsão pontual (mediana)
            fig.add_trace(go.Scatter(
                x=df_prev_mun['data_se'], y=df_prev_mun['casos_previstos'],
                name='Previsão (mediana)',
                line=dict(color='#2a9d8f', width=2, dash='dash'),
                mode='lines+markers',
                hovertemplate='Previsão: %{y:.0f}<extra></extra>'
            ))

            # Linha divisória
            fig.add_shape(
                type='line',
                x0=prev_data['ultima_data_conhecida'],
                x1=prev_data['ultima_data_conhecida'],
                y0=0, y1=1, yref='paper',
                line=dict(color='gray', dash='dot', width=1)
            )
            fig.add_annotation(
                x=prev_data['ultima_data_conhecida'],
                y=1, yref='paper',
                text='Último dado', showarrow=False,
                font=dict(color='gray')
            )

            titulo = f"Previsão — {mun_nome}"
            if tem_bandas:
                titulo += " — com intervalo de 90%"

            fig.update_layout(
                title=titulo,
                yaxis_title='Casos/semana',
                height=450,
                hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True)

            # ── Tabela detalhada ───────────────────────────
            cores_alerta = {
                'Muito Alto': '🔴', 'Alto': '🟠',
                'Moderado': '🟡', 'Baixo': '🔵', 'Muito Baixo': '⚫'
            }
            df_show = df_prev_mun.copy()

            if 'nivel_risco' in df_show.columns:
                df_show['alerta'] = df_show['nivel_risco'].map(cores_alerta)

            # Montar colunas dinamicamente
            colunas = ['data_se', 'horizonte_se', 'casos_previstos']
            if tem_bandas and 'lower' in df_show.columns:
                colunas += ['lower', 'upper']
            if 'nivel_risco' in df_show.columns:
                colunas += ['nivel_risco', 'alerta']

            # Renomear para exibição
            rename = {
                'data_se': 'Semana',
                'horizonte_se': 'Horizonte',
                'casos_previstos': 'Previsão',
                'lower': 'Limite Inferior',
                'upper': 'Limite Superior',
                'nivel_risco': 'Nível',
                'alerta': 'Alerta'
            }

            df_display = df_show[[c for c in colunas if c in df_show.columns]].copy()
            df_display = df_display.rename(columns=rename)

            st.dataframe(
                df_display,
                use_container_width=True, hide_index=True
            )

            # ── Alerta ─────────────────────────────────────
            media_prev = df_prev_mun['casos_previstos'].mean()
            if media_prev > 150:
                st.error(
                    f"🚨 **ALERTA ALTO — {mun_nome}** — "
                    f"Média prevista: {media_prev:.0f} casos/semana"
                )
            elif media_prev > 50:
                st.warning(
                    f"⚠️ **ALERTA MODERADO — {mun_nome}** — "
                    f"Média prevista: {media_prev:.0f} casos/semana"
                )
            else:
                st.success(
                    f"✅ **NÍVEL BAIXO — {mun_nome}** — "
                    f"Média prevista: {media_prev:.0f} casos/semana"
                )

            if len(mun_ids) > 1:
                st.markdown("---")
    else:
        st.error("❌ Dados de previsão indisponíveis")