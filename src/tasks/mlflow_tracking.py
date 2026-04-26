# ============================================================
# Dengue MT — Task: MLflow Tracking v2.0
# ============================================================
# Registra cada execução do pipeline como um run MLflow
# Stack: MLflow local (mlruns/) + resumo exportado para HF Hub
# ============================================================

import mlflow
import logging
from datetime import datetime
from pathlib import Path
from src.config import (
    ROOT_DIR, PIPELINE_VERSION, DATASET_VERSION, MODEL_VERSION,
    MODEL_LATEST_PATH, SCHEMA_LATEST_PATH
)

logger = logging.getLogger('dengue-mt.pipeline')

# Banco SQLite local do MLflow
MLFLOW_DB       = ROOT_DIR / 'mlflow.db'
MLFLOW_TRACKING = "sqlite:///" + str(MLFLOW_DB).replace("\\", "/")
EXPERIMENT_NAME = 'dengue-mt-pipeline'


def registrar_run_mlflow(resumo: dict, drift: dict = None) -> str:
    """
    Registra execução do pipeline no MLflow.
    Retorna o run_id gerado.
    """
    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING)
        mlflow.set_experiment(EXPERIMENT_NAME)

        with mlflow.start_run(
            run_name=f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M')}"
        ) as run:

            # ── Tags ──
            mlflow.set_tags({
                'pipeline_version': PIPELINE_VERSION,
                'dataset_version':  DATASET_VERSION,
                'model_version':    MODEL_VERSION,
                'commit_sha':       resumo.get('commit_sha', 'local'),
                'data_corte':       resumo.get('data_corte', ''),
                'run_env':          resumo.get('run_env', 'local'),
                'nivel_drift':      resumo.get('nivel_drift', 'desconhecido'),
                'retreino':         resumo.get('retreino', 'nao_executado'),
            })

            # ── Params ──
            mlflow.log_params({
                'atraso_dias':   14,
                'modelo':        MODEL_VERSION,
                'n_features':    resumo.get('dbt_test_pass', 'N/A'),
                'mae_limiar':    25.0,
                'r2_minimo':     0.75,
                'drift_normal':  0.3,
                'drift_critico': 0.6,
            })

            params_retreino = resumo.get('params_retreino') or (
                drift.get('params_retreino') if drift else None
            )
            if params_retreino:
                mlflow.log_params({
                    'n_estimators':  params_retreino.get('n_estimators', 500),
                    'learning_rate': params_retreino.get('learning_rate', 0.05),
                    'num_leaves':    params_retreino.get('num_leaves', 31),
                    'motivo':        params_retreino.get('motivo', 'padrao'),
                })

            # ── Metrics ──
            mae = resumo.get('drift_mae')
            r2  = resumo.get('drift_r2')
            drift_score = resumo.get('drift_score')

            if mae is not None:
                mlflow.log_metric('mae_recente', float(mae))
            if r2 is not None:
                mlflow.log_metric('r2_recente', float(r2))
            if drift_score is not None:
                mlflow.log_metric('drift_score', float(drift_score))

            # Status fontes (1=ok, 0=erro)
            for fonte in ['infodengue', 'nasa_power', 'oni', 'google_trends', 'modis']:
                status = resumo.get(fonte, 'erro')
                mlflow.log_metric(f'fonte_{fonte}_ok', 1 if status == 'ok' else 0)

            # dbt status
            dbt_pass = resumo.get('dbt_test_pass')
            if dbt_pass is not None:
                mlflow.log_metric('dbt_test_pass', int(dbt_pass))

            # ── Artifacts ──
            if MODEL_LATEST_PATH.exists():
                mlflow.log_artifact(str(MODEL_LATEST_PATH), artifact_path='model')

            if SCHEMA_LATEST_PATH.exists():
                mlflow.log_artifact(str(SCHEMA_LATEST_PATH), artifact_path='model')

            meta_path = ROOT_DIR / 'metadata' / 'run_metadata.json'
            if meta_path.exists():
                mlflow.log_artifact(str(meta_path), artifact_path='metadata')

            hoje = datetime.now().strftime('%Y-%m-%d')
            relatorio_path = ROOT_DIR / 'reports' / f'execucao_{hoje}.md'
            if relatorio_path.exists():
                mlflow.log_artifact(str(relatorio_path), artifact_path='reports')

            run_id = run.info.run_id
            logger.info(f"MLflow run registrado: {run_id}")
            return run_id

    except Exception as e:
        logger.error(f"Erro ao registrar no MLflow: {e}")
        return None


def exportar_resumo_mlflow() -> list:
    """Exporta resumo de todos os runs MLflow como lista de dicts."""
    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING)
        client = mlflow.tracking.MlflowClient()

        experiment = client.get_experiment_by_name(EXPERIMENT_NAME)
        if experiment is None:
            return []

        runs = client.search_runs(
            experiment_ids=[experiment.experiment_id],
            order_by=['start_time DESC'],
            max_results=50
        )

        resumo = []
        for run in runs:
            resumo.append({
                'run_id':      run.info.run_id,
                'timestamp':   datetime.fromtimestamp(
                                   run.info.start_time / 1000
                               ).isoformat(),
                'status':      run.info.status,
                'mae':         run.data.metrics.get('mae_recente'),
                'r2':          run.data.metrics.get('r2_recente'),
                'drift_score': run.data.metrics.get('drift_score'),
                'nivel_drift': run.data.tags.get('nivel_drift'),
                'retreino':    run.data.tags.get('retreino'),
                'commit_sha':  run.data.tags.get('commit_sha'),
                'data_corte':  run.data.tags.get('data_corte'),
                'run_env':     run.data.tags.get('run_env'),
            })
        return resumo

    except Exception as e:
        logger.error(f"Erro ao exportar resumo MLflow: {e}")
        return []