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

    if data_corte:
        logger.info(f"DATA_CORTE registrado: {data_corte} (aplicar na ingestão real)")

    try:
        from src.tasks.cache import salvar_cache

        # TODO Semana 10: substituir por download real da API INMET
        # aplicar filtro: dados apenas até data_corte
        # Ref: ATRASOS_FONTES['inmet'] = 2 dias
        silver_path = DATA_DIR / 'silver' / 'inmet' / 'inmet_cuiaba_2018_2024.parquet'
        if silver_path.exists():
            df = pd.read_parquet(silver_path)

            # Normalizar coluna de data
            df = df.reset_index(drop=True)
            if 'data' not in df.columns:
                df.columns = ['data'] + list(df.columns[1:])
            df['data'] = pd.to_datetime(df.iloc[:, 0] if 'data' not in df.columns else df['data'])

            # Aplicar corte temporal
            if data_corte:
                df = df[df['data'] <= pd.Timestamp(data_corte)]

            ultima_data = df['data'].max()

            # Salvar no cache
            salvar_cache('inmet', df, extra={'ultima_data': str(ultima_data.date())})

            logger.info(f"INMET Silver — última data: {ultima_data.date()}")
            return {
                'status':     'ok',
                'ultima_data': str(ultima_data.date()),
                'fonte':      'inmet',
                'fallback':   False
            }

        raise FileNotFoundError("Silver INMET não encontrado")

    except Exception as e:
        logger.error(f"INMET erro: {e}")

        # Fallback — usar cache local
        from src.tasks.cache import carregar_cache
        df_fallback = carregar_cache('inmet')
        if df_fallback is not None:
            return {'status': 'ok', 'fonte': 'inmet', 'fallback': True}

        logger.warning("INMET — sem Silver e sem cache — requer ingestão manual")
        return {'status': 'pendente', 'fonte': 'inmet', 'fallback': False}


@task(name="ingest_nasa_power", retries=3, retry_delay_seconds=60)
def ingerir_nasa_power(data_corte=None):
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
            'start': (data_corte or datetime.now()).strftime('%Y%m%d'),
            'end':   (data_corte or datetime.now()).strftime('%Y%m%d'),
            'format': 'JSON'
        }
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            data = r.json()
            valor = list(data['properties']['parameter']['ALLSKY_SFC_SW_DWN'].values())[0]
            if valor != -999:
                # Cache: salvar resultado válido
                df_cache = pd.DataFrame([{
                    'data': (data_corte or datetime.now()).strftime('%Y-%m-%d'),
                    'radiacao': valor
                }])
                from src.tasks.cache import salvar_cache
                salvar_cache('nasa_power', df_cache)
                logger.info("NASA POWER API — conectividade OK")
                return {'status': 'ok', 'fonte': 'nasa_power', 'fallback': False}
            else:
                raise ValueError(f"NASA POWER retornou -999 para {data_corte}")

    except Exception as e:
        logger.error(f"NASA POWER erro: {e}")

        # Fallback — usar cache local
        from src.tasks.cache import carregar_cache
        df_fallback = carregar_cache('nasa_power')
        if df_fallback is not None:
            return {'status': 'ok', 'fonte': 'nasa_power', 'fallback': True}

    return {'status': 'erro', 'fonte': 'nasa_power', 'fallback': False}

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
        from src.tasks.cache import salvar_cache
        url = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            linhas = [l.split() for l in r.text.strip().split('\n')[1:] if l.strip()]
            df_oni = pd.DataFrame(linhas, columns=['seas', 'yr', 'total', 'anom'])
            salvar_cache('oni_index', df_oni)
            logger.info(f"ONI Index — {len(r.text.splitlines())} linhas")
            return {'status': 'ok', 'fonte': 'oni', 'fallback': False}

    except Exception as e:
        logger.error(f"ONI erro: {e}")

        # Fallback — usar cache local
        from src.tasks.cache import carregar_cache
        df_fallback = carregar_cache('oni_index')
        if df_fallback is not None:
            return {'status': 'ok', 'fonte': 'oni', 'fallback': True}

    return {'status': 'erro', 'fonte': 'oni', 'fallback': False}

@task(name="ingest_google_trends", retries=2, retry_delay_seconds=120)
def ingerir_google_trends(data_corte: datetime = None):
    """Atualiza Google Trends para MT."""
    logger = get_run_logger()
    logger.info("Atualizando Google Trends...")

    try:
        from pytrends.request import TrendReq
        from src.tasks.cache import salvar_cache
        import time

        pytrends = TrendReq(hl='pt-BR', tz=-240)
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
            df_cache = df.reset_index()[['date', 'dengue']].rename(
                columns={'date': 'data', 'dengue': 'trends_dengue'}
            )
            salvar_cache('google_trends', df_cache)
            logger.info(f"Google Trends — {len(df)} semanas atualizadas")
            return {'status': 'ok', 'n_semanas': len(df), 'fonte': 'google_trends', 'fallback': False}

        time.sleep(2)

    except Exception as e:
        logger.error(f"Google Trends erro: {e}")

        # Fallback — usar cache local
        from src.tasks.cache import carregar_cache
        df_fallback = carregar_cache('google_trends')
        if df_fallback is not None:
            return {'status': 'ok', 'fonte': 'google_trends', 'fallback': True,
                    'n_semanas': len(df_fallback)}

    return {'status': 'erro', 'fonte': 'google_trends', 'fallback': False}
