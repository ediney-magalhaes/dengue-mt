# ============================================================
# Dengue MT — Tasks: Ingestão de Dados (Orquestração)
# ============================================================
# Responsabilidade: orquestrar Bronze → Silver → Cache
# Lógica de negócio em src/ingestion/
#
# Arquitetura Medalhão:
# API → Bronze (bruto) → Silver (limpo) → Cache → Gold
# ============================================================

from prefect import task, get_run_logger
from datetime import datetime, timedelta
from src.config import DATA_DIR


@task(name="ingest_inmet", retries=3, retry_delay_seconds=60)
def ingerir_inmet(data_corte=None):
    """InfoDengue API → Bronze → Silver → Cache."""
    logger = get_run_logger()
    logger.info("Iniciando ingestão InfoDengue — Bronze → Silver...")

    try:
        from src.ingestion.infodengue import (
            ingerir_bronze, bronze_para_silver,
            salvar_silver, carregar_silver_fallback
        )
        from src.tasks.cache import salvar_cache

        df_bronze = ingerir_bronze(ano_inicio=2025, data_corte=data_corte)
        df_silver = bronze_para_silver(df_bronze, data_corte=data_corte)
        salvar_silver(df_silver)
        salvar_cache('inmet', df_silver, extra={
            'ultima_data': str(df_silver['data'].max().date()),
            'fonte':       'infodengue_silver',
            'camada':      'silver'
        })

        logger.info(f"InfoDengue Silver — última semana: {df_silver['data'].max().date()}")
        return {
            'status':      'ok',
            'ultima_data': str(df_silver['data'].max().date()),
            'fonte':       'infodengue',
            'n_registros': len(df_silver),
            'fallback':    False
        }

    except Exception as e:
        logger.error(f"InfoDengue erro: {e}")
        return _fallback_inmet(logger)


def _fallback_inmet(logger):
    from src.ingestion.infodengue import carregar_silver_fallback
    from src.tasks.cache import carregar_cache, salvar_cache

    df = carregar_silver_fallback()
    if df is not None:
        salvar_cache('inmet', df)
        return {'status': 'ok', 'fonte': 'infodengue_silver', 'fallback': True}

    df = carregar_cache('inmet')
    if df is not None:
        return {'status': 'ok', 'fonte': 'inmet_cache', 'fallback': True}

    silver_hist = DATA_DIR / 'silver' / 'inmet' / 'inmet_cuiaba_2018_2024.parquet'
    if silver_hist.exists():
        return {'status': 'ok', 'fonte': 'inmet_silver_hist', 'fallback': True}

    return {'status': 'pendente', 'fonte': 'inmet', 'fallback': False}


@task(name="ingest_nasa_power", retries=3, retry_delay_seconds=60)
def ingerir_nasa_power(data_corte=None):
    """NASA POWER API → Bronze → Silver → Cache."""
    logger = get_run_logger()
    logger.info("Iniciando ingestão NASA POWER — Bronze → Silver...")

    if data_corte:
        logger.info(f"Corte temporal: até {data_corte.strftime('%Y-%m-%d')}")

    try:
        from src.ingestion.nasa_power import (
            ingerir_bronze, bronze_para_silver,
            salvar_silver, carregar_silver_fallback
        )
        from src.tasks.cache import salvar_cache

        data_inicio = datetime(2025, 1, 1)
        data_fim    = data_corte if data_corte else (datetime.now() - timedelta(days=14))
        if data_fim < data_inicio:
            data_fim = data_inicio

        df_bronze = ingerir_bronze(data_inicio, data_fim)
        df_silver = bronze_para_silver(df_bronze)
        salvar_silver(df_silver)
        salvar_cache('nasa_power', df_silver)

        logger.info(f"NASA POWER Silver — {len(df_silver)} dias")
        return {
            'status':      'ok',
            'n_registros': len(df_silver),
            'fonte':       'nasa_power',
            'fallback':    False
        }

    except Exception as e:
        logger.error(f"NASA POWER erro: {e}")
        return _fallback_nasa(logger)


def _fallback_nasa(logger):
    from src.ingestion.nasa_power import carregar_silver_fallback
    from src.tasks.cache import carregar_cache, salvar_cache

    df = carregar_silver_fallback()
    if df is not None:
        salvar_cache('nasa_power', df)
        return {'status': 'ok', 'fonte': 'nasa_power_silver', 'fallback': True}

    df = carregar_cache('nasa_power')
    if df is not None:
        return {'status': 'ok', 'fonte': 'nasa_power_cache', 'fallback': True}

    return {'status': 'erro', 'fonte': 'nasa_power', 'fallback': False}


@task(name="ingest_oni", retries=3, retry_delay_seconds=60)
def ingerir_oni_index(data_corte=None):
    """ONI NOAA → Bronze → Silver → Cache."""
    logger = get_run_logger()
    logger.info("Iniciando ingestão ONI Index NOAA...")

    try:
        from src.ingestion.oni import (
            ingerir_bronze, bronze_para_silver,
            salvar_silver
        )
        from src.tasks.cache import salvar_cache

        df_bronze = ingerir_bronze()
        df_silver = bronze_para_silver(df_bronze)
        salvar_silver(df_silver)
        salvar_cache('oni_index', df_silver)

        logger.info(f"ONI Silver — {len(df_silver)} trimestres")
        return {'status': 'ok', 'fonte': 'oni', 'fallback': False}

    except Exception as e:
        logger.error(f"ONI erro: {e}")
        return _fallback_oni(logger)


def _fallback_oni(logger):
    from src.ingestion.oni import carregar_silver_fallback
    from src.tasks.cache import carregar_cache, salvar_cache

    df = carregar_silver_fallback()
    if df is not None:
        salvar_cache('oni_index', df)
        return {'status': 'ok', 'fonte': 'oni_silver', 'fallback': True}

    df = carregar_cache('oni_index')
    if df is not None:
        return {'status': 'ok', 'fonte': 'oni_cache', 'fallback': True}

    return {'status': 'erro', 'fonte': 'oni', 'fallback': False}


@task(name="ingest_google_trends", retries=2, retry_delay_seconds=120)
def ingerir_google_trends(data_corte=None):
    """Google Trends → Bronze → Silver → Cache."""
    logger = get_run_logger()
    logger.info("Iniciando ingestão Google Trends...")

    try:
        from src.ingestion.trends import (
            ingerir_bronze, bronze_para_silver,
            salvar_silver
        )
        from src.tasks.cache import salvar_cache

        df_bronze = ingerir_bronze(data_corte=data_corte)
        df_silver = bronze_para_silver(df_bronze, data_corte=data_corte)
        salvar_silver(df_silver)
        salvar_cache('google_trends', df_silver)

        logger.info(f"Trends Silver — {len(df_silver)} semanas")
        return {
            'status':    'ok',
            'n_semanas': len(df_silver),
            'fonte':     'google_trends',
            'fallback':  False
        }

    except Exception as e:
        logger.error(f"Google Trends erro: {e}")
        return _fallback_trends(logger)


def _fallback_trends(logger):
    from src.ingestion.trends import carregar_silver_fallback
    from src.tasks.cache import carregar_cache, salvar_cache

    df = carregar_silver_fallback()
    if df is not None:
        salvar_cache('google_trends', df)
        return {'status': 'ok', 'fonte': 'trends_silver', 'fallback': True}

    df = carregar_cache('google_trends')
    if df is not None:
        return {'status': 'ok', 'fonte': 'google_trends_cache',
                'fallback': True, 'n_semanas': len(df)}

    return {'status': 'erro', 'fonte': 'google_trends', 'fallback': False}