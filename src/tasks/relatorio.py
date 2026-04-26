# ============================================================
# Dengue MT — Task: Relatório de Execução Automático v2.0
# ============================================================

from prefect import task, get_run_logger
from datetime import datetime
from pathlib import Path
from src.config import (
    REPORTS_DIR, PIPELINE_VERSION, DATASET_VERSION, MODEL_VERSION,
    SCHEMA_LATEST_PATH
)


@task(name="gerar_relatorio")
def gerar_relatorio_execucao(resumo: dict) -> str:
    """Gera relatório markdown automático de cada execução do pipeline."""
    logger = get_run_logger()
    logger.info("Gerando relatório de execução...")

    hoje = datetime.now().strftime('%Y-%m-%d')
    hora = datetime.now().strftime('%H:%M UTC')

    def status_emoji(s):
        if s in ('ok', 'promovido', 'nao_executado'):
            return '✅'
        elif s in ('pendente', 'mantido', 'warn'):
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

    # Gold snapshot
    snapshot = resumo.get('gold_snapshot', 'não gerado')
    hf_url = f"https://huggingface.co/datasets/edyestatistica/dengue-mt-medallion/blob/main/{snapshot}" if snapshot else 'N/A'

    # dbt status
    dbt_pass = resumo.get('dbt_test_pass', 'N/A')
    dbt_fail = resumo.get('dbt_test_fail', 'N/A')

    relatorio = f"""# Relatório de Execução — Dengue MT
**Data:** {hoje} às {hora}  
**Pipeline version:** {PIPELINE_VERSION}  
**Dataset version:** {DATASET_VERSION}  
**Model version:** {MODEL_VERSION}  
**Commit SHA:** `{resumo.get('commit_sha', 'local')}`  
**Ambiente:** `{resumo.get('run_env', 'local')}`  
**Data corte:** `{resumo.get('data_corte', 'N/A')}`  

---

## 1. Ingestão Bronze

| Fonte | Status |
|---|---|
| InfoDengue | {status_emoji(resumo.get('infodengue', 'erro'))} {resumo.get('infodengue', 'erro')} |
| NASA POWER | {status_emoji(resumo.get('nasa_power', 'erro'))} {resumo.get('nasa_power', 'erro')} |
| ONI Index | {status_emoji(resumo.get('oni', 'erro'))} {resumo.get('oni', 'erro')} |
| Google Trends | {status_emoji(resumo.get('google_trends', 'erro'))} {resumo.get('google_trends', 'erro')} |
| MODIS AppEEARS | {status_emoji(resumo.get('modis', 'erro'))} {resumo.get('modis', 'erro')} |

## 2. Transformação dbt

| Etapa | Status |
|---|---|
| dbt run | {status_emoji(resumo.get('dbt_run', 'erro'))} {resumo.get('dbt_run', 'erro')} |
| dbt test | PASS={dbt_pass} FAIL={dbt_fail} |

## 3. Métricas do Modelo

| Métrica | Valor |
|---|---|
| MAE recente (26 SE) | {resumo.get('drift_mae', 'N/A')} casos/semana |
| R² recente (26 SE) | {resumo.get('drift_r2', 'N/A')} |
| Drift score | {resumo.get('drift_score', 'N/A')} |
| Nível drift | {resumo.get('nivel_drift', 'N/A')} |
| Retreino necessário | {'Sim' if resumo.get('retreinar') else 'Não'} |

## 4. Gold Dataset

| Item | Valor |
|---|---|
| Snapshot | `{snapshot}` |
| HF Hub | [Acessar]({hf_url}) |

## 5. Rastreabilidade MLflow

| Item | Valor |
|---|---|
| Run ID | `{resumo.get('mlflow_run_id', 'N/A')}` |
| Experimento | `dengue-mt-pipeline` |

## 6. Decisão Final

{decisao}

---
*Gerado automaticamente pelo pipeline Dengue MT v2.0 — IFMT 2026*
"""

    REPORTS_DIR.mkdir(exist_ok=True)
    relatorio_path = REPORTS_DIR / f'execucao_{hoje}.md'
    with open(relatorio_path, 'w', encoding='utf-8') as f:
        f.write(relatorio)

    logger.info(f"Relatório salvo: {relatorio_path}")
    return str(relatorio_path)


def publicar_relatorio_hf(relatorio_path: str, resumo: dict):
    """Publica relatório no HF Hub — snapshot datado + latest."""
    import logging
    logger = logging.getLogger('dengue-mt.pipeline')

    try:
        from huggingface_hub import HfApi
        import os

        token = os.environ.get('HF_TOKEN')
        if not token:
            logger.warning("HF_TOKEN não encontrado — relatório não publicado")
            return {'status': 'skip', 'motivo': 'sem HF_TOKEN'}

        api     = HfApi(token=token)
        repo_id = 'edyestatistica/dengue-mt-medallion'
        hoje    = datetime.now().strftime('%Y-%m-%d')

        snapshot_path = f'reports/execucao_{hoje}.md'
        api.upload_file(
            path_or_fileobj=relatorio_path,
            path_in_repo=snapshot_path,
            repo_id=repo_id,
            repo_type='dataset',
            commit_message=f'report: execução {hoje} — drift={resumo.get("nivel_drift")} retreino={resumo.get("retreino")}'
        )

        api.upload_file(
            path_or_fileobj=relatorio_path,
            path_in_repo='reports/execucao_latest.md',
            repo_id=repo_id,
            repo_type='dataset',
            commit_message=f'report: latest atualizado — {hoje}'
        )

        url_latest  = f"https://huggingface.co/datasets/{repo_id}/blob/main/reports/execucao_latest.md"
        url_snapshot = f"https://huggingface.co/datasets/{repo_id}/blob/main/{snapshot_path}"

        return {'status': 'ok', 'url_latest': url_latest,
                'url_snapshot': url_snapshot, 'snapshot': snapshot_path}

    except Exception as e:
        logger.error(f"Erro ao publicar relatório: {e}")
        return {'status': 'erro', 'motivo': str(e)}


def atualizar_historico_runs(resumo: dict):
    """Mantém histórico de execuções em historico_runs.parquet no HF Hub."""
    import logging
    import os
    import pandas as pd
    import tempfile
    logger = logging.getLogger('dengue-mt.pipeline')

    token = os.environ.get('HF_TOKEN')
    if not token:
        logger.warning("HF_TOKEN não encontrado — histórico não atualizado")
        return

    try:
        from huggingface_hub import HfApi, hf_hub_download
        api     = HfApi(token=token)
        repo_id = 'edyestatistica/dengue-mt-medallion'

        try:
            path = hf_hub_download(
                repo_id=repo_id,
                filename='reports/historico_runs.parquet',
                repo_type='dataset', token=token
            )
            df_hist = pd.read_parquet(path)
        except Exception:
            df_hist = pd.DataFrame()

        novo = {
            'timestamp':    resumo.get('timestamp'),
            'drift_score':  float(resumo.get('drift_score', 0)) if resumo.get('drift_score') else None,
            'nivel_drift':  resumo.get('nivel_drift'),
            'drift_mae':    resumo.get('drift_mae'),
            'drift_r2':     resumo.get('drift_r2'),
            'retreino':     resumo.get('retreino'),
            'commit_sha':   resumo.get('commit_sha'),
            'data_corte':   resumo.get('data_corte'),
            'dbt_run':      resumo.get('dbt_run'),
            'dbt_test_pass': resumo.get('dbt_test_pass'),
            'infodengue':   resumo.get('infodengue'),
            'nasa_power':   resumo.get('nasa_power'),
            'oni':          resumo.get('oni'),
            'google_trends': resumo.get('google_trends'),
            'modis':        resumo.get('modis'),
        }
        df_novo   = pd.DataFrame([novo])
        df_result = pd.concat([df_hist, df_novo], ignore_index=True)

        with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as f:
            df_result.to_parquet(f.name, index=False)
            api.upload_file(
                path_or_fileobj=f.name,
                path_in_repo='reports/historico_runs.parquet',
                repo_id=repo_id,
                repo_type='dataset',
                commit_message=f'history: run {novo["timestamp"][:10]}'
            )
        logger.info(f"Histórico atualizado: {len(df_result)} execuções")

    except Exception as e:
        logger.error(f"Erro ao atualizar histórico: {e}")


def atualizar_changelog(resumo: dict, resultado_retreino: dict):
    """Gera entrada automática no CHANGELOG após retreino promovido."""
    import logging
    logger = logging.getLogger('dengue-mt.pipeline')

    if resultado_retreino.get('status') != 'promovido':
        logger.info("CHANGELOG — retreino não promovido, sem entrada gerada")
        return

    try:
        from src.config import ROOT_DIR, PIPELINE_VERSION, DATASET_VERSION
        import json

        schema = {}
        if SCHEMA_LATEST_PATH.exists():
            with open(SCHEMA_LATEST_PATH) as f:
                schema = json.load(f)

        hoje        = datetime.now().strftime('%Y-%m-%d')
        versao      = resultado_retreino.get('versao', DATASET_VERSION)
        snapshot    = resumo.get('gold_snapshot', f'gold/dataset_features_{DATASET_VERSION}_{hoje}.parquet')
        commit_sha  = resumo.get('commit_sha', 'local')
        r2_novo     = resultado_retreino.get('r2_novo', 'N/A')
        mae_novo    = resultado_retreino.get('mae', 'N/A')
        drift_score = resumo.get('drift_score')
        if drift_score is not None:
            try:
                drift_score = float(drift_score)
            except (TypeError, ValueError):
                drift_score = None
        nivel_drift = resumo.get('nivel_drift', 'N/A')
        n_features  = schema.get('n_features', 'N/A')

        changelog_path = ROOT_DIR / 'CHANGELOG.md'
        conteudo = changelog_path.read_text(encoding='utf-8')

        import re
        versoes = re.findall(r'## \[(\d+\.\d+\.\d+)', conteudo)
        if versoes:
            ultima = versoes[0]
            partes = ultima.split('.')
            nova_versao = f"{partes[0]}.{partes[1]}.{int(partes[2]) + 1}"
        else:
            nova_versao = '2.0.1'

        entrada = f"""
## [{nova_versao}] — {hoje}

### Modelo
- Arquivo: `lgbm_{versao}_producao.pkl` → `lgbm_producao_latest.pkl`
- Dataset: `{snapshot}`
- Commit SHA: `{commit_sha}`
- MAE: {mae_novo} casos/semana | R²: {r2_novo}
- Retreino: sim | Motivo: drift detectado → promovido

### Features
- {n_features} features — contrato validado via schema latest
- Contratos: validados (dbt test PASS={resumo.get('dbt_test_pass', 'N/A')})

### Infraestrutura
- Pipeline version: {PIPELINE_VERSION}
- Drift score: {f"{drift_score:.3f}" if drift_score is not None else 'N/A'} | Nível: {nivel_drift}

---
"""

        marcador = '## [2.'
        pos = conteudo.find(marcador)
        if pos == -1:
            marcador = '## [1.'
            pos = conteudo.find(marcador)
        if pos == -1:
            marcador = '\n---\n'
            pos = conteudo.find(marcador)

        novo_conteudo = conteudo[:pos] + entrada + conteudo[pos:]
        changelog_path.write_text(novo_conteudo, encoding='utf-8')

        logger.info(f"CHANGELOG atualizado — versão {nova_versao}")

    except Exception as e:
        logger.error(f"Erro ao atualizar CHANGELOG: {e}")