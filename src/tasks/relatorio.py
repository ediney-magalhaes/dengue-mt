# ============================================================
# Dengue MT — Task: Relatório de Execução Automático
# ============================================================

from prefect import task, get_run_logger
from datetime import datetime
from pathlib import Path
from src.config import REPORTS_DIR, PIPELINE_VERSION, DATASET_VERSION, MODEL_VERSION


@task(name="gerar_relatorio")
def gerar_relatorio_execucao(resumo: dict) -> str:
    """Gera relatório markdown automático de cada execução do pipeline."""
    logger = get_run_logger()
    logger.info("Gerando relatório de execução...")

    hoje = datetime.now().strftime('%Y-%m-%d')
    hora = datetime.now().strftime('%H:%M UTC')

    # Status emoji helper
    def status_emoji(s):
        if s in ('ok', 'promovido', 'nao_executado'):
            return '✅'
        elif s in ('pendente', 'mantido'):
            return '⚠️'
        return '❌'

    # Decisão final
    retreino_status = resumo.get('retreino', 'nao_executado')
    if retreino_status == 'promovido':
        decisao = '🚀 **Novo modelo promovido para produção**'
    elif retreino_status == 'mantido':
        decisao = '⚠️ **Retreino executado — modelo anterior mantido (rollback)**'
    elif retreino_status == 'nao_executado':
        decisao = '✅ **Modelo estável — retreino não necessário**'
    else:
        decisao = '❌ **Erro no retreino — modelo anterior mantido**'

    # Fallbacks
    fallbacks = resumo.get('fallbacks', {})
    fallback_lines = '\n'.join([
        f"| {fonte} | {'⚠️ FALLBACK' if ativo else '✅ API ok'} |"
        for fonte, ativo in fallbacks.items()
    ])

    # Cache status
    cache = resumo.get('cache_status', {})
    cache_lines = '\n'.join([
        f"| {fonte} | {'✅' if info.get('valido') else '⚠️'} | {info.get('n_registros', '?')} | {info.get('atualizado_em', '?')[:10]} |"
        for fonte, info in cache.items()
    ])

    # Gold snapshot
    snapshot = resumo.get('gold_snapshot', 'não gerado')
    hf_url = f"https://huggingface.co/datasets/edyestatistica/dengue-mt-medallion/blob/main/{snapshot}" if snapshot else 'N/A'

    relatorio = f"""# Relatório de Execução — Dengue MT
**Data:** {hoje} às {hora}  
**Pipeline version:** {PIPELINE_VERSION}  
**Dataset version:** {DATASET_VERSION}  
**Model version:** {MODEL_VERSION}  
**Commit SHA:** `{resumo.get('commit_sha', 'local')}`  
**Ambiente:** `{resumo.get('run_env', 'local')}`  
**Data corte:** `{resumo.get('data_corte', 'N/A')}`  

---

## 1. Status das Etapas de Ingestão

| Fonte | Status |
|---|---|
| INMET | {status_emoji(resumo.get('inmet', 'erro'))} {resumo.get('inmet', 'erro')} |
| NASA POWER | {status_emoji(resumo.get('nasa_power', 'erro'))} {resumo.get('nasa_power', 'erro')} |
| ONI Index | {status_emoji(resumo.get('oni', 'erro'))} {resumo.get('oni', 'erro')} |
| Google Trends | {status_emoji(resumo.get('trends', 'erro'))} {resumo.get('trends', 'erro')} |
| Contratos de dados | {status_emoji(resumo.get('contratos', 'erro'))} {resumo.get('contratos', 'erro')} |

## 2. Fallbacks Ativados

| Fonte | Status |
|---|---|
{fallback_lines}

## 3. Cache das Fontes

| Fonte | Válido | Registros | Última atualização |
|---|---|---|---|
{cache_lines}

## 4. Métricas do Modelo

| Métrica | Valor |
|---|---|
| MAE recente (90d) | {resumo.get('drift_mae', 'N/A')} casos/dia |
| R² recente (90d) | {resumo.get('drift_r2', 'N/A')} |
| Retreino necessário | {'Sim' if resumo.get('retreinar') else 'Não'} |

## 5. Gold Dataset

| Item | Valor |
|---|---|
| Snapshot | `{snapshot}` |
| HF Hub | [Acessar]({hf_url}) |

## 6. Decisão Final

{decisao}

---
*Gerado automaticamente pelo pipeline Dengue MT — IFMT 2026*
"""

    # Salvar relatório
    REPORTS_DIR.mkdir(exist_ok=True)
    relatorio_path = REPORTS_DIR / f'execucao_{hoje}.md'
    with open(relatorio_path, 'w', encoding='utf-8') as f:
        f.write(relatorio)

    logger.info(f"Relatório salvo: {relatorio_path}")
    return str(relatorio_path)

def publicar_relatorio_hf(relatorio_path: str, resumo: dict):
    """
    Publica relatório de execução no HF Hub.
    - Snapshot datado: reports/execucao_YYYY-MM-DD.md
    - Ponteiro fixo:   reports/execucao_latest.md
    """
    import logging
    logger = logging.getLogger('dengue-mt.pipeline')

    try:
        from huggingface_hub import HfApi
        import os

        token = os.environ.get('HF_TOKEN')
        if not token:
            logger.warning("HF_TOKEN não encontrado — relatório não publicado no HF Hub")
            return {'status': 'skip', 'motivo': 'sem HF_TOKEN'}

        api      = HfApi(token=token)
        repo_id  = 'edyestatistica/dengue-mt-medallion'
        hoje     = datetime.now().strftime('%Y-%m-%d')

        # 1. Snapshot datado
        snapshot_path = f'reports/execucao_{hoje}.md'
        api.upload_file(
            path_or_fileobj=relatorio_path,
            path_in_repo=snapshot_path,
            repo_id=repo_id,
            repo_type='dataset',
            commit_message=f'report: execução {hoje} — drift={resumo.get("nivel_drift")} retreino={resumo.get("retreino")}'
        )
        logger.info(f"Relatório snapshot publicado: {snapshot_path}")

        # 2. Ponteiro latest
        api.upload_file(
            path_or_fileobj=relatorio_path,
            path_in_repo='reports/execucao_latest.md',
            repo_id=repo_id,
            repo_type='dataset',
            commit_message=f'report: latest atualizado — {hoje}'
        )
        logger.info("Relatório latest atualizado no HF Hub")

        url_latest   = f"https://huggingface.co/datasets/{repo_id}/blob/main/reports/execucao_latest.md"
        url_snapshot = f"https://huggingface.co/datasets/{repo_id}/blob/main/{snapshot_path}"

        return {
            'status':       'ok',
            'url_latest':   url_latest,
            'url_snapshot': url_snapshot,
            'snapshot':     snapshot_path
        }

    except Exception as e:
        logger.error(f"Erro ao publicar relatório no HF Hub: {e}")
        return {'status': 'erro', 'motivo': str(e)}