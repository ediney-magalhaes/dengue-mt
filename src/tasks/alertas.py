# ============================================================
# Dengue MT — Task: Alertas Telegram
# ============================================================
# Envia alertas automáticos via Telegram Bot
# Gatilhos: pipeline falhou, drift alto, modelo piorou,
#           problemas na ingestão, promoção/rollback
# ============================================================

import os
import logging
import requests
from datetime import datetime

logger = logging.getLogger('dengue-mt.pipeline')

TELEGRAM_TOKEN   = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')


def _enviar_mensagem(texto: str) -> bool:
    """Envia mensagem via Telegram Bot API."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram não configurado — TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID ausente")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id':    TELEGRAM_CHAT_ID,
            'text':       texto,
            'parse_mode': 'HTML'
        }
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            logger.info("Alerta Telegram enviado ✅")
            return True
        else:
            logger.error(f"Telegram erro: {r.status_code} — {r.text}")
            return False
    except Exception as e:
        logger.error(f"Telegram falhou: {e}")
        return False


def alerta_pipeline_ok(resumo: dict):
    """Alerta de execução bem-sucedida — enviado sempre."""
    nivel  = resumo.get('nivel_drift', 'desconhecido')
    emoji  = {'normal': '🟢', 'moderado': '🟡', 'critico': '🔴'}.get(nivel, '⚪')
    data   = datetime.now().strftime('%d/%m/%Y %H:%M')

    texto = (
        f"{emoji} <b>DENGUE MT — Pipeline OK</b>\n"
        f"📅 Data: {data}\n"
        f"📉 MAE: {resumo.get('drift_mae', 'N/A')} casos/dia\n"
        f"📈 R²: {resumo.get('drift_r2', 'N/A')}\n"
        f"🎯 Drift: {float(resumo.get('drift_score', 0)):.3f} ({nivel})\n"
        f"🔁 Retreino: {resumo.get('retreino', 'N/A')}\n"
        f"📦 Snapshot: {resumo.get('gold_snapshot', 'N/A')}"
    )
    return _enviar_mensagem(texto)


def alerta_pipeline_falhou(etapa: str, erro: str, resumo: dict = None):
    """Alerta crítico — pipeline falhou em alguma etapa."""
    data = datetime.now().strftime('%d/%m/%Y %H:%M')

    texto = (
        f"🔴 <b>DENGUE MT — PIPELINE FALHOU</b>\n"
        f"📅 Data: {data}\n"
        f"⚠️ Etapa: <code>{etapa}</code>\n"
        f"❌ Erro: <code>{erro[:200]}</code>\n"
        f"🔁 Ação: verificar logs em reports/pipeline.log"
    )
    return _enviar_mensagem(texto)


def alerta_drift(resumo: dict):
    """Alerta de drift moderado ou crítico."""
    nivel       = resumo.get('nivel_drift', 'desconhecido')
    drift_score = resumo.get('drift_score', 0)
    data        = datetime.now().strftime('%d/%m/%Y %H:%M')

    if nivel == 'moderado':
        emoji = '🟡'
        acao  = 'Retreino com parâmetros padrão agendado'
    elif nivel == 'critico':
        emoji = '🔴'
        acao  = 'Retreino CONSERVADOR obrigatório ativado'
    else:
        return False  # Normal — não envia alerta

    texto = (
        f"{emoji} <b>DENGUE MT — DRIFT {nivel.upper()}</b>\n"
        f"📅 Data: {data}\n"
        f"🎯 Drift score: {float(drift_score):.3f}\n"
        f"📉 MAE: {resumo.get('drift_mae', 'N/A')} casos/dia\n"
        f"📈 R²: {resumo.get('drift_r2', 'N/A')}\n"
        f"⚙️ Ação: {acao}"
    )
    return _enviar_mensagem(texto)


def alerta_retreino(resultado: dict, resumo: dict):
    """Alerta sobre resultado do retreino — promovido ou mantido."""
    status = resultado.get('status', 'desconhecido')
    data   = datetime.now().strftime('%d/%m/%Y %H:%M')

    if status == 'promovido':
        emoji = '🚀'
        titulo = 'MODELO PROMOVIDO'
        detalhe = (
            f"📈 R² novo: {resultado.get('r2_novo', 'N/A')}\n"
            f"📈 R² anterior: {resultado.get('r2_anterior', 'N/A')}\n"
            f"📉 MAE novo: {resultado.get('mae', 'N/A')} casos/dia"
        )
    elif status == 'mantido':
        emoji = '⚠️'
        titulo = 'MODELO MANTIDO (rollback)'
        detalhe = (
            f"📈 R² novo: {resultado.get('r2_novo', 'N/A')} "
            f"< R² atual: {resultado.get('r2_anterior', 'N/A')}\n"
            f"🔁 Motivo: {resultado.get('motivo', 'queda de performance')}"
        )
    elif status == 'erro':
        emoji = '❌'
        titulo = 'RETREINO FALHOU'
        detalhe = f"❌ Motivo: {resultado.get('motivo', 'erro desconhecido')}"
    else:
        return False

    texto = (
        f"{emoji} <b>DENGUE MT — {titulo}</b>\n"
        f"📅 Data: {data}\n"
        f"{detalhe}\n"
        f"📦 Snapshot: {resumo.get('gold_snapshot', 'N/A')}"
    )
    return _enviar_mensagem(texto)


def alerta_ingestao(fonte: str, status: str, fallback: bool, detalhes: str = ''):
    """Alerta de problema na ingestão de uma fonte."""
    if status == 'ok' and not fallback:
        return False  # Tudo ok — não envia

    data  = datetime.now().strftime('%d/%m/%Y %H:%M')
    emoji = '🟡' if fallback else '🔴'
    acao  = 'Cache/fallback ativado' if fallback else 'Sem fallback disponível'

    texto = (
        f"{emoji} <b>DENGUE MT — INGESTÃO {fonte.upper()}</b>\n"
        f"📅 Data: {data}\n"
        f"⚠️ Status: {status}\n"
        f"🔄 Fallback: {'sim' if fallback else 'não'}\n"
        f"⚙️ Ação: {acao}\n"
        f"📋 Detalhes: {detalhes[:150]}"
    )
    return _enviar_mensagem(texto)


def alerta_pytest_falhou(output: str):
    """Alerta quando pytest bloqueia promoção do modelo."""
    data = datetime.now().strftime('%d/%m/%Y %H:%M')

    texto = (
        f"🔴 <b>DENGUE MT — PYTEST BLOQUEOU PROMOÇÃO</b>\n"
        f"📅 Data: {data}\n"
        f"❌ Testes falharam — modelo NÃO promovido\n"
        f"📋 Output:\n<code>{output[-300:]}</code>"
    )
    return _enviar_mensagem(texto)