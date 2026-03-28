# ============================================================
# Dengue MT — Tasks: Ingestão de Dados
# ============================================================

from prefect import task, get_run_logger
from datetime import datetime, timedelta
from src.config import DATA_DIR
import pandas as pd
import requests
from datetime import datetime, timedelta


@task(name="ingest_inmet", retries=3, retry_delay_seconds=60)
def ingerir_inmet(data_corte=None):
    """Baixa dados climáticos INMET mais recentes."""
    logger = get_run_logger()
    logger.info("Iniciando ingestão INMET...")
    # TODO: quando ingestão real for implementada (Semana 10),
    # aplicar filtro: dados apenas até data_corte
    # Ref: ATRASOS_FONTES['inmet'] = 2 dias
    if data_corte:
        logger.info(f"DATA_CORTE registrado: {data_corte} (aplicar na ingestão real)")

    silver_path = DATA_DIR / 'silver' / 'inmet' / 'inmet_cuiaba_2018_2024.parquet'
    if silver_path.exists():
        df = pd.read_parquet(silver_path)
        ultima_data = pd.to_datetime(
            df.index.max() if df.index.dtype != 'O' else df.iloc[:, 0].max()
        )
        logger.info(f"INMET Silver — última data: {ultima_data.date()}")
        return {'status': 'ok', 'ultima_data': str(ultima_data.date()), 'fonte': 'inmet'}

    logger.warning("Silver INMET não encontrado — requer ingestão manual")
    return {'status': 'pendente', 'fonte': 'inmet'}


@task(name="ingest_nasa_power", retries=3, retry_delay_seconds=60)
def ingerir_nasa_power(data_corte: datetime = None):
    """Baixa dados de radiação solar NASA POWER."""
    logger = get_run_logger()
    logger.info("Iniciando ingestão NASA POWER...")
    if data_corte:
        logger.info(f"Corte temporal aplicado: até {data_corte.strftime('%Y-%m-%d')}")

    try:
        url = "https://power.larc.nasa.gov/api/temporal/daily/point"
        params = {
            'parameters': 'ALLSKY_SFC_SW_DWN',
            'community': 'RE',
            'longitude': -56.1,
            'latitude': -15.6,
            'start': datetime.now().strftime('%Y%m%d'),
            'end': datetime.now().strftime('%Y%m%d'),
            'format': 'JSON'
        }
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            logger.info("NASA POWER API — conectividade OK")
            return {'status': 'ok', 'fonte': 'nasa_power'}
    except Exception as e:
        logger.error(f"NASA POWER erro: {e}")

    return {'status': 'erro', 'fonte': 'nasa_power'}


@task(name="ingest_oni", retries=3, retry_delay_seconds=60)
def ingerir_oni_index(data_corte=None):
    """Baixa ONI Index NOAA."""
    logger = get_run_logger()
    logger.info("Iniciando ingestão ONI Index NOAA...")
    # TODO: quando ingestão real for implementada (Semana 10),
    # filtrar apenas trimestres até data_corte
    # Ref: ATRASOS_FONTES['oni_index'] = 60 dias
    if data_corte:
        logger.info(f"DATA_CORTE registrado: {data_corte} (aplicar na ingestão real)")

    try:
        url = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            logger.info(f"ONI Index — {len(r.text.splitlines())} linhas")
            return {'status': 'ok', 'fonte': 'oni'}
    except Exception as e:
        logger.error(f"ONI erro: {e}")

    return {'status': 'erro', 'fonte': 'oni'}

@task(name="ingest_google_trends", retries=2, retry_delay_seconds=120)
def ingerir_google_trends(data_corte: datetime = None):
    """Atualiza Google Trends para MT."""
    logger = get_run_logger()
    logger.info("Atualizando Google Trends...")

    try:
        from pytrends.request import TrendReq
        import time

        pytrends = TrendReq(hl='pt-BR', tz=-240)
        # Respeitar DATA_CORTE — nunca usar dado além do corte
        data_fim = data_corte if data_corte else datetime.now()
        hoje = data_fim.strftime('%Y-%m-%d')
        mes_passado = (data_fim - timedelta(days=90)).strftime('%Y-%m-%d')
        logger.info(f"Google Trends — corte aplicado: até {hoje} (lag=7d garantido)")

        pytrends.build_payload(
            kw_list=['dengue'],
            timeframe=f'{mes_passado} {hoje}',
            geo='BR-MT'
        )
        df = pytrends.interest_over_time()

        if not df.empty:
            logger.info(f"Google Trends — {len(df)} semanas atualizadas")
            return {'status': 'ok', 'n_semanas': len(df), 'fonte': 'google_trends'}

        time.sleep(2)
    except Exception as e:
        logger.error(f"Google Trends erro: {e}")

    return {'status': 'erro', 'fonte': 'google_trends'}