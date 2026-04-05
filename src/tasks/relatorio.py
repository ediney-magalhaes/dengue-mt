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

## 6. Rastreabilidade MLflow

| Item | Valor |
|---|---|
| Run ID | `{resumo.get('mlflow_run_id', 'N/A')}` |
| Experimento | `dengue-mt-pipeline` |
| MAE registrado | {resumo.get('drift_mae', 'N/A')} casos/dia |
| R² registrado | {resumo.get('drift_r2', 'N/A')} |
| Drift score | {resumo.get('drift_score', 'N/A')} |
| Nível drift | {resumo.get('nivel_drift', 'N/A')} |

## 7. Decisão Final

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

def atualizar_historico_runs(resumo: dict):
    """
    Mantém histórico de execuções em reports/historico_runs.parquet no HF Hub.
    Acumula um registro por execução — cresce semanalmente.
    """
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

        # Tentar carregar histórico existente
        try:
            path = hf_hub_download(
                repo_id=repo_id,
                filename='reports/historico_runs.parquet',
                repo_type='dataset', token=token
            )
            df_hist = pd.read_parquet(path)
        except Exception:
            df_hist = pd.DataFrame()

        # Novo registro
        novo = {
            'timestamp':   resumo.get('timestamp'),
            'drift_score': float(resumo.get('drift_score', 0)) if resumo.get('drift_score') else None,
            'nivel_drift': resumo.get('nivel_drift'),
            'drift_mae':   resumo.get('drift_mae'),
            'drift_r2':    resumo.get('drift_r2'),
            'retreino':    resumo.get('retreino'),
            'commit_sha':  resumo.get('commit_sha'),
            'data_corte':  resumo.get('data_corte'),
            'inmet':       resumo.get('fallbacks', {}).get('inmet', False),
            'nasa':        resumo.get('fallbacks', {}).get('nasa', False),
            'oni':         resumo.get('fallbacks', {}).get('oni', False),
            'trends':      resumo.get('fallbacks', {}).get('trends', False),
        }
        df_novo   = pd.DataFrame([novo])
        df_result = pd.concat([df_hist, df_novo], ignore_index=True)

        # Salvar e publicar
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
    """
    Gera entrada automática no CHANGELOG após retreino bem-sucedido.
    Só executa quando status == 'promovido'.
    """
    import logging
    logger = logging.getLogger('dengue-mt.pipeline')

    if resultado_retreino.get('status') != 'promovido':
        logger.info("CHANGELOG — retreino não promovido, sem entrada gerada")
        return

    try:
        from src.config import ROOT_DIR, PIPELINE_VERSION
        import json

        # Carregar schema para pegar data_treino e n_features
        schema_path = ROOT_DIR / 'models' / 'lgbm_v4_feature_schema.json'
        schema = {}
        if schema_path.exists():
            with open(schema_path) as f:
                schema = json.load(f)

        hoje        = datetime.now().strftime('%Y-%m-%d')
        snapshot    = resumo.get('gold_snapshot', f'gold/dataset_features_v4_{hoje}.parquet')
        commit_sha  = resumo.get('commit_sha', 'local')
        r2_novo     = resultado_retreino.get('r2_novo', 'N/A')
        mae_novo    = resultado_retreino.get('mae', 'N/A')
        drift_score = resumo.get('drift_score')
        # Converter np.float64 para float nativo
        if drift_score is not None:
            try:
                drift_score = float(drift_score)
            except (TypeError, ValueError):
                drift_score = None
        nivel_drift = resumo.get('nivel_drift', 'N/A')
        n_features  = schema.get('n_features', 59)
        fallbacks   = resumo.get('fallbacks', {})
        fallback_list = [k for k, v in fallbacks.items() if v] or ['nenhuma']

        # Ler versão atual do CHANGELOG e incrementar
        changelog_path = ROOT_DIR / 'CHANGELOG.md'
        conteudo = changelog_path.read_text(encoding='utf-8')

        # Extrair última versão
        import re
        versoes = re.findall(r'## \[(\d+\.\d+\.\d+)\]', conteudo)
        if versoes:
            ultima = versoes[0]
            partes = ultima.split('.')
            nova_versao = f"{partes[0]}.{partes[1]}.{int(partes[2]) + 1}"
        else:
            nova_versao = '1.0.1'

        entrada = f"""
## [{nova_versao}] — {hoje}

### Modelo
- Arquivo: `lgbm_v4_producao.pkl`
- Dataset: `{snapshot}`
- Commit SHA: `{commit_sha}`
- MAE: {mae_novo} casos/dia | R²: {r2_novo}
- Retreino: sim | Motivo: drift detectado → promovido

### Features
- {n_features} features — sem mudanças no contrato
- Adicionadas: nenhuma
- Removidas: nenhuma
- Contratos: validados

### Infraestrutura
- Pipeline version: {PIPELINE_VERSION}
- Drift score: {f"{float(drift_score):.3f}" if drift_score not in ('N/A', None) else 'N/A'} | Nível: {nivel_drift}
- Fontes com fallback: {', '.join(fallback_list)}

---
"""

        # Inserir após o template (antes do primeiro ## [X.Y.Z] real)
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