# ============================================================
# Dengue MT — Componente: Banner de Drift do Modelo
# ============================================================
# Exibe status do modelo em tempo real com nível de drift
# Baseado em Wasserstein distance — níveis Normal/Moderado/Crítico
# ============================================================

import streamlit as st
from components.dados import get_run_metadata


def render_banner_drift():
    """Renderiza banner visual de status do modelo."""
    meta = get_run_metadata()

    if meta is None:
        st.info("ℹ️ Metadata do pipeline não disponível localmente.")
        return

    nivel     = meta.get('nivel_drift', 'desconhecido')
    score     = meta.get('drift_score')
    mae       = meta.get('drift_mae')
    r2        = meta.get('drift_r2')
    retreino  = meta.get('retreino', 'desconhecido')
    timestamp = meta.get('timestamp', '')[:10]
    fallbacks = meta.get('fallbacks', {})
    fallback_ativo = any(fallbacks.values())

    # Configuração visual por nível
    config = {
        'normal': {
            'emoji': '🟢',
            'label': 'Modelo Estável',
            'cor':   '#28a745',
            'bg':    '#d4edda',
            'borda': '#28a745',
            'msg':   'O modelo está operando dentro dos parâmetros esperados.'
        },
        'moderado': {
            'emoji': '🟡',
            'label': 'Drift Moderado Detectado',
            'cor':   '#856404',
            'bg':    '#fff3cd',
            'borda': '#ffc107',
            'msg':   'Variação moderada nos dados detectada. Retreino programado.'
        },
        'critico': {
            'emoji': '🔴',
            'label': 'Drift Crítico — Retreino em Andamento',
            'cor':   '#721c24',
            'bg':    '#f8d7da',
            'borda': '#dc3545',
            'msg':   'Variação crítica detectada. Retreino com parâmetros conservadores ativado.'
        },
    }.get(nivel, {
        'emoji': '⚪',
        'label': 'Status Desconhecido',
        'cor':   '#6c757d',
        'bg':    '#f8f9fa',
        'borda': '#6c757d',
        'msg':   'Não foi possível determinar o status do modelo.'
    })

    # Banner principal
    st.markdown(f"""
    <div style="
        background-color: {config['bg']};
        border-left: 6px solid {config['borda']};
        border-radius: 6px;
        padding: 14px 20px;
        margin-bottom: 16px;
    ">
        <div style="font-size: 1.1rem; font-weight: 700; color: {config['cor']};">
            {config['emoji']} {config['label']}
        </div>
        <div style="font-size: 0.9rem; color: {config['cor']}; margin-top: 4px;">
            {config['msg']}
        </div>
        <div style="font-size: 0.8rem; color: #555; margin-top: 8px;">
            📅 Última execução: <b>{timestamp}</b> &nbsp;|&nbsp;
            📉 Drift score: <b>{f'{score:.3f}' if score is not None else 'N/A'}</b> &nbsp;|&nbsp;
            📊 MAE: <b>{mae if mae is not None else 'N/A'}</b> casos/dia &nbsp;|&nbsp;
            📈 R²: <b>{r2 if r2 is not None else 'N/A'}</b> &nbsp;|&nbsp;
            🔁 Retreino: <b>{retreino}</b>
        </div>
        {
            '<div style="font-size:0.8rem; color:#856404; margin-top:6px;">⚠️ <b>Fallback ativo</b> em pelo menos uma fonte de dados.</div>'
            if fallback_ativo else ''
        }
    </div>
    """, unsafe_allow_html=True)