# ============================================================
# Dengue MT — Task: Alertas
# ============================================================

from prefect import task, get_run_logger
from datetime import datetime
from src.config import REPORTS_DIR
import json


@task(name="enviar_alerta")
def enviar_alerta_email(assunto: str, mensagem: str):
    """Envia alerta por email (requer configuração SMTP)."""
    logger = get_run_logger()
    logger.info(f"Alerta: {assunto}")

    alerta = {
        'timestamp': datetime.now().isoformat(),
        'assunto':   assunto,
        'mensagem':  mensagem
    }

    alertas_path = REPORTS_DIR / 'alertas.jsonl'
    with open(alertas_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(alerta, ensure_ascii=False) + '\n')

    logger.info("Alerta salvo em reports/alertas.jsonl")
    return alerta