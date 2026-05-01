# ============================================================
# Dengue MT — Pipeline Semanal v2.0
# Orquestrador: Prefect 3.x
# ============================================================
# Fluxo:
# 1. Ingestão Bronze (5 fontes)
# 2. Transformação dbt (Bronze → Silver → Intermediate → Gold)
# 3. Exportar Gold → HF Hub
# 4. Drift + Retreino (se necessário)
# 5. Relatório + MLflow
# ============================================================

from dotenv import load_dotenv
load_dotenv()

from prefect import flow, get_run_logger
from datetime import datetime
from pathlib import Path
import time
import json

from src.config import (
    PIPELINE_VERSION, DATASET_VERSION, MODEL_VERSION,
    METADATA_DIR, COMMIT_SHA, RUN_ENV,
    ATRASO_OPERACIONAL_DIAS, ATRASOS_FONTES,
    MODIS_USUARIO, MODIS_SENHA,
    calcular_data_corte
)
from src.observabilidade import (
    obs_logger, log_etapa, log_metricas,
    log_pipeline_start, log_pipeline_end
)
from src.tasks.ingestao import (
    ingerir_infodengue, ingerir_nasa_power,
    ingerir_oni_index, ingerir_google_trends,
    ingerir_modis
)
from src.tasks.dbt_runner  import executar_dbt_run, executar_dbt_test
from src.tasks.drift       import monitorar_drift_modelo
from src.tasks.retreino    import retreinar_modelo
from src.tasks.publicacao  import publicar_bronze_incremental, publicar_gold_versionado, publicar_previsao_bairros
from src.tasks.relatorio   import gerar_relatorio_execucao
from src.tasks.alertas     import (
    alerta_pipeline_ok, alerta_pipeline_falhou,
    alerta_drift, alerta_retreino, alerta_ingestao
)


# ============================================================
# FLOW PRINCIPAL
# ============================================================

@flow(
    name="dengue-mt-pipeline-semanal",
    description="Pipeline semanal v2.0 — dbt + LightGBM — Dengue MT"
)
def pipeline_semanal():
    logger = get_run_logger()

    # --- Identidade ---
    logger.info("Iniciando Pipeline Semanal — Dengue MT v2.0")
    logger.info(f"Pipeline version: {PIPELINE_VERSION}")
    logger.info(f"Dataset version:  {DATASET_VERSION}")
    logger.info(f"Model version:    {MODEL_VERSION}")
    logger.info(f"Data:             {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    logger.info(f"Commit SHA:       {COMMIT_SHA}")
    logger.info(f"Ambiente:         {RUN_ENV}")

    log_pipeline_start(PIPELINE_VERSION, DATASET_VERSION, MODEL_VERSION, COMMIT_SHA)

    data_corte = calcular_data_corte()
    obs_logger.info(
        f"DATA_CORTE | data={data_corte.strftime('%Y-%m-%d')} "
        f"| atraso={ATRASO_OPERACIONAL_DIAS}d"
    )

    # ============================================================
    # ETAPA 1 — INGESTÃO BRONZE
    # ============================================================

    t0 = time.time()
    resultado_infodengue = ingerir_infodengue(data_corte=data_corte)
    log_etapa('ingest_infodengue', t0, resultado_infodengue)
    if resultado_infodengue.get('status') == 'erro':
        alerta_ingestao('infodengue', resultado_infodengue.get('status'), False)

    t0 = time.time()
    resultado_nasa = ingerir_nasa_power(data_corte=data_corte)
    log_etapa('ingest_nasa_power', t0, resultado_nasa)
    if resultado_nasa.get('status') == 'erro':
        alerta_ingestao('nasa_power', resultado_nasa.get('status'), False)

    t0 = time.time()
    resultado_oni = ingerir_oni_index(data_corte=data_corte)
    log_etapa('ingest_oni', t0, resultado_oni)
    if resultado_oni.get('status') == 'erro':
        alerta_ingestao('oni', resultado_oni.get('status'), False)

    t0 = time.time()
    resultado_trends = ingerir_google_trends(data_corte=data_corte)
    log_etapa('ingest_trends', t0, resultado_trends)
    if resultado_trends.get('status') == 'erro':
        alerta_ingestao('google_trends', resultado_trends.get('status'), False)

    t0 = time.time()
    resultado_modis = ingerir_modis(usuario=MODIS_USUARIO, senha=MODIS_SENHA)
    log_etapa('ingest_modis', t0, resultado_modis)
    if resultado_modis.get('status') == 'erro':
        alerta_ingestao('modis', resultado_modis.get('status'), False)

    # ============================================================
    # ETAPA 2 — TRANSFORMAÇÃO dbt
    # Bronze → Silver → Intermediate → Gold
    # ============================================================

    t0 = time.time()
    resultado_dbt_run = executar_dbt_run()
    log_etapa('dbt_run', t0, resultado_dbt_run)

    # dbt run falhou — encerra pipeline sem tocar no Gold ou modelo atual
    if resultado_dbt_run['status'] == 'erro':
        logger.error("dbt run falhou — pipeline encerrado. Gold e modelo anteriores preservados.")
        alerta_pipeline_falhou('dbt_run', resultado_dbt_run.get('detalhe', ''))
        resumo_parcial = _montar_resumo_parcial(
            data_corte, resultado_infodengue, resultado_nasa,
            resultado_oni, resultado_trends, resultado_modis,
            resultado_dbt_run, status='dbt_run_falhou'
        )
        _salvar_metadata(resumo_parcial)
        return resumo_parcial

    t0 = time.time()
    resultado_dbt_test = executar_dbt_test()
    log_etapa('dbt_test', t0, resultado_dbt_test)

    if resultado_dbt_test['status'] == 'warn':
        logger.warning(
            f"dbt test — {resultado_dbt_test['fail']} falhas "
            f"| PASS={resultado_dbt_test['pass']}"
        )

    # ============================================================
    # ETAPA 3 — EXPORTAR GOLD E BRONZE → HF HUB
    # ============================================================

    t0 = time.time()
    publicacao_bronze = publicar_bronze_incremental()
    log_etapa('publicar_bronze', t0, publicacao_bronze)

    t0 = time.time()
    publicacao_gold = publicar_gold_versionado()
    log_etapa('publicar_gold', t0, publicacao_gold)

    t0 = time.time()
    publicacao_bairros = publicar_previsao_bairros()
    log_etapa('publicar_previsao_bairros', t0, publicacao_bairros)

    # ============================================================
    # ETAPA 4 — DRIFT + RETREINO
    # ============================================================

    t0 = time.time()
    drift = monitorar_drift_modelo()
    log_etapa('monitorar_drift', t0, drift)
    alerta_drift(drift)

    if drift.get('mae_recente'):
        log_metricas(drift['mae_recente'], drift['r2_recente'])
        obs_logger.info(
            f"DRIFT_SCORE | score={drift.get('drift_score')} "
            f"| nivel={drift.get('nivel_drift')} "
            f"| retreinar={drift.get('retreinar')}"
        )

    resultado_retreino = {'status': 'nao_executado'}
    if drift.get('retreinar', False):
        logger.info("Drift detectado — iniciando retreino...")
        obs_logger.info("RETREINO_INICIO | motivo=drift_detectado")

        t0 = time.time()
        resultado_retreino = retreinar_modelo(
            data_corte=data_corte,
            params_retreino=drift.get('params_retreino')
        )
        log_etapa('retreinar_modelo', t0, resultado_retreino)

        obs_logger.info(
            f"RETREINO_DECISAO | status={resultado_retreino['status']} "
            f"| r2_novo={resultado_retreino.get('r2_novo')} "
            f"| r2_anterior={resultado_retreino.get('r2_anterior')}"
        )

        resumo_parcial = _montar_resumo_parcial(
        data_corte, resultado_infodengue, resultado_nasa,
        resultado_oni, resultado_trends, resultado_modis,
        resultado_dbt_run,
        publicacao_bairros=publicacao_bairros
    )

        from src.tasks.relatorio import atualizar_changelog
        atualizar_changelog(resumo_parcial, resultado_retreino)
        alerta_retreino(resultado_retreino, resumo_parcial)

        if resultado_retreino['status'] == 'promovido':
            logger.info(f"Retreino concluído — R²={resultado_retreino['r2_novo']}")
        elif resultado_retreino['status'] == 'mantido':
            alerta_pipeline_falhou(
                'retreino_mantido',
                f"R² novo={resultado_retreino.get('r2_novo')} "
                f"< atual={resultado_retreino.get('r2_anterior')}"
            )
        else:
            alerta_pipeline_falhou(
                'retreino_erro',
                resultado_retreino.get('motivo', 'erro desconhecido')
            )
    else:
        logger.info("Sem drift — retreino não necessário")

    # ============================================================
    # ETAPA 5 — RELATÓRIO + MLFLOW
    # ============================================================

    resumo_parcial = _montar_resumo_parcial(
        data_corte, resultado_infodengue, resultado_nasa,
        resultado_oni, resultado_trends, resultado_modis,
        resultado_dbt_run,
        publicacao_bairros=publicacao_bairros  # ← adicionar
    )
    resumo_parcial.update({
        'dbt_test_pass':   resultado_dbt_test.get('pass', 0),
        'dbt_test_fail':   resultado_dbt_test.get('fail', 0),
        'drift_mae':       drift.get('mae_recente'),
        'drift_r2':        drift.get('r2_recente'),
        'drift_score':     drift.get('drift_score'),
        'nivel_drift':     drift.get('nivel_drift'),
        'retreinar':       drift.get('retreinar', False),
        'retreino':        resultado_retreino['status'],
        'bronze_publicados': publicacao_bronze.get('publicados', 0),
        'bronze_skipped':    publicacao_bronze.get('skipped', 0),
        'gold_snapshot':     publicacao_gold.get('snapshot'),
    })

    _salvar_metadata(resumo_parcial)
    log_pipeline_end(datetime.now().isoformat(), resultado_retreino['status'])
    alerta_pipeline_ok(resumo_parcial)

    # MLflow
    from src.tasks.mlflow_tracking import registrar_run_mlflow
    run_id = registrar_run_mlflow(resumo_parcial, drift=drift)
    if run_id:
        resumo_parcial['mlflow_run_id'] = run_id
        logger.info(f"MLflow run_id: {run_id}")

    # Relatório
    from src.tasks.relatorio import publicar_relatorio_hf, atualizar_historico_runs
    relatorio_path = gerar_relatorio_execucao(resumo_parcial)
    resultado_relatorio = publicar_relatorio_hf(relatorio_path, resumo_parcial)
    if resultado_relatorio.get('status') == 'ok':
        resumo_parcial['relatorio_url'] = resultado_relatorio.get('url_latest')
        logger.info(f"Relatório publicado: {resultado_relatorio.get('url_latest')}")
    else:
        logger.warning(f"Relatório não publicado: {resultado_relatorio.get('motivo')}")

    atualizar_historico_runs(resumo_parcial)
    logger.info("Pipeline concluído com sucesso!")

    return resumo_parcial


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def _montar_resumo_parcial(
    data_corte, resultado_infodengue, resultado_nasa,
    resultado_oni, resultado_trends, resultado_modis,
    resultado_dbt_run, status='ok',
    publicacao_bairros=None
):
    return {
        'pipeline_version': PIPELINE_VERSION,
        'dataset_version':  DATASET_VERSION,
        'model_version':    MODEL_VERSION,
        'commit_sha':       COMMIT_SHA,
        'run_env':          RUN_ENV,
        'timestamp':        datetime.now().isoformat(),
        'data_corte':       data_corte.strftime('%Y-%m-%d'),
        'atraso_dias':      ATRASO_OPERACIONAL_DIAS,
        'status':           status,
        'infodengue':       resultado_infodengue['status'],
        'nasa_power':       resultado_nasa['status'],
        'oni':              resultado_oni['status'],
        'google_trends':    resultado_trends['status'],
        'modis':            resultado_modis['status'],
        'dbt_run':          resultado_dbt_run['status'],
        'previsao_bairros': publicacao_bairros.get('status', 'nao_executado')
                            if publicacao_bairros else 'nao_executado',
    }


def _salvar_metadata(resumo: dict):
    METADATA_DIR.mkdir(exist_ok=True)
    run_metadata = {
        'pipeline_version': PIPELINE_VERSION,
        'dataset_version':  DATASET_VERSION,
        'model_version':    MODEL_VERSION,
        'commit_sha':       COMMIT_SHA,
        'run_env':          RUN_ENV,
        'timestamp':        datetime.now().isoformat(),
        'data_corte':       resumo.get('data_corte'),
        'atraso_dias':      ATRASO_OPERACIONAL_DIAS,
        'atrasos_fontes':   ATRASOS_FONTES,
        'resultados':       resumo
    }
    with open(METADATA_DIR / 'run_metadata.json', 'w', encoding='utf-8') as f:
        json.dump(run_metadata, f, ensure_ascii=False, indent=2)


# ============================================================
# EXECUÇÃO LOCAL
# ============================================================

if __name__ == "__main__":
    resultado = pipeline_semanal()
    print(f"\n{'='*50}")
    print("RESULTADO DO PIPELINE:")
    print(f"{'='*50}")
    for k, v in resultado.items():
        print(f"  {k}: {v}")