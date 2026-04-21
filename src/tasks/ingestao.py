# ============================================================
# Dengue MT — Tasks: Ingestão Bronze
# ============================================================
# Responsabilidade ÚNICA: orquestrar chamadas aos módulos de
# ingestão Bronze (src/ingestion/). Não faz transformações.
# Silver, Intermediate e Gold são responsabilidade do dbt.
# ============================================================
 
from prefect import task, get_run_logger
from datetime import datetime
 
 
@task(name="ingest_infodengue", retries=3, retry_delay_seconds=60)
def ingerir_infodengue(data_corte=None):
    """InfoDengue API → Bronze. Silver é responsabilidade do dbt."""
    logger = get_run_logger()
    logger.info("Iniciando ingestão InfoDengue → Bronze...")
 
    try:
        from src.ingestion.infodengue import ingerir_bronze
        paths = ingerir_bronze(ano_inicio=2018)
 
        logger.info(f"InfoDengue Bronze — {len(paths)} arquivos salvos")
        return {
            'status':     'ok',
            'n_arquivos': len(paths),
            'fonte':      'infodengue',
            'fallback':   False
        }
 
    except Exception as e:
        logger.error(f"InfoDengue erro: {e}")
        return {'status': 'erro', 'fonte': 'infodengue', 'fallback': False}
 
 
@task(name="ingest_nasa_power", retries=3, retry_delay_seconds=60)
def ingerir_nasa_power(data_corte=None):
    """NASA POWER API → Bronze. Silver é responsabilidade do dbt."""
    logger = get_run_logger()
    logger.info("Iniciando ingestão NASA POWER → Bronze...")
 
    try:
        from src.ingestion.nasa_power import ingerir_bronze
        paths = ingerir_bronze(data_inicio=2018)
 
        logger.info(f"NASA POWER Bronze — {len(paths)} arquivos salvos")
        return {
            'status':     'ok',
            'n_arquivos': len(paths),
            'fonte':      'nasa_power',
            'fallback':   False
        }
 
    except Exception as e:
        logger.error(f"NASA POWER erro: {e}")
        return {'status': 'erro', 'fonte': 'nasa_power', 'fallback': False}
 
 
@task(name="ingest_oni", retries=3, retry_delay_seconds=60)
def ingerir_oni_index(data_corte=None):
    """ONI NOAA → Bronze. Silver é responsabilidade do dbt."""
    logger = get_run_logger()
    logger.info("Iniciando ingestão ONI Index NOAA → Bronze...")
 
    try:
        from src.ingestion.oni import ingerir_bronze
        df = ingerir_bronze()
 
        if df is None:
            raise ValueError("ONI retornou None")
 
        logger.info(f"ONI Bronze — {len(df)} trimestres salvos")
        return {
            'status':       'ok',
            'n_registros':  len(df),
            'fonte':        'oni',
            'fallback':     False
        }
 
    except Exception as e:
        logger.error(f"ONI erro: {e}")
        return {'status': 'erro', 'fonte': 'oni', 'fallback': False}
 
 
@task(name="ingest_google_trends", retries=2, retry_delay_seconds=120)
def ingerir_google_trends(data_corte=None):
    """Google Trends → Bronze. Silver é responsabilidade do dbt."""
    logger = get_run_logger()
    logger.info("Iniciando ingestão Google Trends → Bronze...")
 
    try:
        from src.ingestion.trends import ingerir_bronze
        df = ingerir_bronze(data_corte=data_corte)
 
        if df is None:
            raise ValueError("Trends retornou None")
 
        logger.info(f"Trends Bronze — {len(df)} semanas salvas")
        return {
            'status':    'ok',
            'n_semanas': len(df),
            'fonte':     'google_trends',
            'fallback':  False
        }
 
    except Exception as e:
        logger.error(f"Google Trends erro: {e}")
        return {'status': 'erro', 'fonte': 'google_trends', 'fallback': False}
 
 
@task(name="ingest_modis", retries=2, retry_delay_seconds=120)
def ingerir_modis(usuario: str, senha: str):
    """MODIS AppEEARS NASA → Bronze. Silver é responsabilidade do dbt."""
    logger = get_run_logger()
    logger.info("Iniciando ingestão MODIS AppEEARS → Bronze...")
 
    try:
        from src.ingestion.modis import ingerir_bronze
        paths = ingerir_bronze(usuario=usuario, senha=senha, ano_inicio=2018)
 
        if not paths:
            raise ValueError("MODIS não retornou arquivos")
 
        logger.info(f"MODIS Bronze — {len(paths)} arquivos salvos")
        return {
            'status':     'ok',
            'n_arquivos': len(paths),
            'fonte':      'modis',
            'fallback':   False
        }
 
    except Exception as e:
        logger.error(f"MODIS erro: {e}")
        return {'status': 'erro', 'fonte': 'modis', 'fallback': False}