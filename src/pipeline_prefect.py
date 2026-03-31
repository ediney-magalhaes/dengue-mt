# ============================================================
# Dengue MT — Pipeline Semanal
# Orquestrador: Prefect 3.x
# ============================================================

from prefect import flow, get_run_logger
from src.tasks.relatorio import gerar_relatorio_execucao
from datetime import datetime
from pathlib import Path
import time
import json

from src.config import (
    PIPELINE_VERSION, DATASET_VERSION, MODEL_VERSION,
    METADATA_DIR, COMMIT_SHA, RUN_ENV,
    ATRASO_OPERACIONAL_DIAS, ATRASOS_FONTES,
    calcular_data_corte
)
from src.observabilidade import (
    obs_logger, log_etapa, log_nulos, log_metricas,
    log_pipeline_start, log_pipeline_end
)
from src.tasks.ingestao import (
    ingerir_inmet, ingerir_nasa_power,
    ingerir_oni_index, ingerir_google_trends
)
from src.tasks.validacao  import validar_contratos_dados
from src.tasks.drift      import monitorar_drift_modelo
from src.tasks.retreino   import retreinar_modelo
from src.tasks.publicacao import publicar_gold_versionado
from src.tasks.alertas    import enviar_alerta_email

import pandas as pd


# ============================================================
# FLOW PRINCIPAL
# ============================================================

@flow(
    name="dengue-mt-pipeline-semanal",
    description="Pipeline semanal de ingestão, validação e monitoramento — Dengue MT"
)
def pipeline_semanal():
    logger = get_run_logger()

    # Identidade
    logger.info(f"Iniciando Pipeline Semanal — Dengue MT")
    logger.info(f"Pipeline version: {PIPELINE_VERSION}")
    logger.info(f"Dataset version:  {DATASET_VERSION}")
    logger.info(f"Model version:    {MODEL_VERSION}")
    logger.info(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    logger.info(f"Commit SHA:       {COMMIT_SHA}")
    logger.info(f"Ambiente:         {RUN_ENV}")

    log_pipeline_start(PIPELINE_VERSION, DATASET_VERSION, MODEL_VERSION, COMMIT_SHA)

    # Calcular DATA_CORTE anti-leakage
    data_corte = calcular_data_corte()
    obs_logger.info(f"DATA_CORTE | data={data_corte.strftime('%Y-%m-%d')} | atraso={ATRASO_OPERACIONAL_DIAS}d")
    logger.info(f"Data corte operacional: {data_corte.strftime('%Y-%m-%d')}")

    # 1. Ingestão — todas as tasks recebem data_corte
    t0 = time.time(); resultado_inmet  = ingerir_inmet(data_corte=data_corte);          log_etapa('ingest_inmet',  t0, resultado_inmet)
    t0 = time.time(); resultado_nasa   = ingerir_nasa_power(data_corte=data_corte);     log_etapa('ingest_nasa',   t0, resultado_nasa)
    t0 = time.time(); resultado_oni    = ingerir_oni_index(data_corte=data_corte);      log_etapa('ingest_oni',    t0, resultado_oni)
    t0 = time.time(); resultado_trends = ingerir_google_trends(data_corte=data_corte);  log_etapa('ingest_trends', t0, resultado_trends)

    # 1.5 Publicar Gold versionado
    t0 = time.time()
    publicacao_gold = publicar_gold_versionado()
    log_etapa('publicar_gold', t0, publicacao_gold)

    # 2. Validar contratos
    t0 = time.time()
    contratos = validar_contratos_dados()
    log_etapa('validar_contratos', t0, contratos)

    # Logar % nulos features críticas
    try:
        from src.config import DATA_DIR
        df_check = pd.read_parquet(DATA_DIR / 'gold' / 'dataset_features_v4.parquet')
        log_nulos(df_check, ['casos', 'temp_media', 'precipitacao_total',
                             'umidade_media', 'casos_lag_7d'])
    except Exception as e:
        obs_logger.warning(f"Não foi possível checar nulos: {e}")

    if contratos['status'] == 'erro':
        enviar_alerta_email(
            assunto="ALERTA: Contratos de dados violados — Dengue MT",
            mensagem=f"Erros: {contratos.get('erros', [])}"
        )

    # 3. Drift
    t0 = time.time()
    drift = monitorar_drift_modelo()
    log_etapa('monitorar_drift', t0, drift)
    if drift.get('mae_recente'):
        log_metricas(drift['mae_recente'], drift['r2_recente'])
        obs_logger.info(
            f"DRIFT_SCORE | score={drift.get('drift_score')} "
            f"| nivel={drift.get('nivel_drift')} "
            f"| retreinar={drift.get('retreinar')}"
        )

    # 4. Retreino
    resultado_retreino = {'status': 'nao_executado'}
    if drift.get('retreinar', False):
        logger.info("Drift detectado — iniciando retreino...")
        obs_logger.info("RETREINO_INICIO | motivo=drift_detectado")
        t0 = time.time()
        resultado_retreino = retreinar_modelo(data_corte=data_corte, params_retreino=drift.get('params_retreino'))
        log_etapa('retreinar_modelo', t0, resultado_retreino)
        obs_logger.info(
            f"RETREINO_DECISAO | status={resultado_retreino['status']} "
            f"| r2_novo={resultado_retreino.get('r2_novo')} "
            f"| r2_anterior={resultado_retreino.get('r2_anterior')}"
        )

        if resultado_retreino['status'] == 'promovido':
            logger.info(f"Retreino concluído — R²={resultado_retreino['r2_novo']}")
        elif resultado_retreino['status'] == 'mantido':
            enviar_alerta_email(
                assunto="Retreino executado mas modelo anterior mantido",
                mensagem=f"Novo R²={resultado_retreino['r2_novo']} inferior ao atual={resultado_retreino['r2_anterior']}"
            )
        else:
            enviar_alerta_email(
                assunto="ERRO no retreino — Dengue MT",
                mensagem=f"Motivo: {resultado_retreino.get('motivo', 'desconhecido')}"
            )
    else:
        logger.info("Sem drift — retreino não necessário")

    if drift.get('retreinar', False) and resultado_retreino['status'] != 'promovido':
        enviar_alerta_email(
            assunto="ALERTA: Retreino necessário — Dengue MT",
            mensagem=(
                f"MAE recente: {drift.get('mae_recente')} \n"
                f"R² recente: {drift.get('r2_recente')}"
            )
        )

    # Resumo final
    # Status do cache de todas as fontes
    from src.tasks.cache import status_cache
    resumo = {
        'pipeline_version': PIPELINE_VERSION,
        'dataset_version':  DATASET_VERSION,
        'model_version':    MODEL_VERSION,
        'commit_sha':       COMMIT_SHA,
        'run_env':          RUN_ENV,
        'timestamp':        datetime.now().isoformat(),
        'inmet':            resultado_inmet['status'],
        'nasa_power':       resultado_nasa['status'],
        'oni':              resultado_oni['status'],
        'trends':           resultado_trends['status'],
        'contratos':        contratos['status'],
        'drift_mae':        drift.get('mae_recente'),
        'drift_r2':         drift.get('r2_recente'),
        'retreinar':        drift.get('retreinar', False),
        'retreino':         resultado_retreino['status'],
        'data_corte':       data_corte.strftime('%Y-%m-%d'),
        'gold_snapshot':    publicacao_gold.get('snapshot'),
        'drift_score':  drift.get('drift_score'),
        'nivel_drift':  drift.get('nivel_drift'),
        'fallbacks':        {
            'inmet':   resultado_inmet.get('fallback', False),
            'nasa':    resultado_nasa.get('fallback', False),
            'oni':     resultado_oni.get('fallback', False),
            'trends':  resultado_trends.get('fallback', False),
        },
        'cache_status': status_cache()
    }

    logger.info(f"Pipeline concluído: {resumo}")

    # Salvar metadata
    METADATA_DIR.mkdir(exist_ok=True)
    run_metadata = {
        'pipeline_version': PIPELINE_VERSION,
        'dataset_version':  DATASET_VERSION,
        'model_version':    MODEL_VERSION,
        'commit_sha':       COMMIT_SHA,
        'run_env':          RUN_ENV,
        'timestamp':        datetime.now().isoformat(),
        'data_corte':       data_corte.strftime('%Y-%m-%d'),
        'atraso_dias':      ATRASO_OPERACIONAL_DIAS,
        'atrasos_fontes':   ATRASOS_FONTES,
        'resultados':       resumo
    }
    with open(METADATA_DIR / 'run_metadata.json', 'w', encoding='utf-8') as f:
        json.dump(run_metadata, f, ensure_ascii=False, indent=2)

    logger.info("Metadata salvo em metadata/run_metadata.json")

    log_pipeline_end(datetime.now().isoformat(), resultado_retreino['status'])

    # Gerar relatório de execução automático
    gerar_relatorio_execucao(resumo)

    return resumo

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