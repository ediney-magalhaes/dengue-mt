# ============================================================
# Dengue MT — Tasks: Ingestão de Dados
# ============================================================
# Fontes reais:
# - InfoDengue API — casos + nowcasting + clima semanal
# - NASA POWER API — radiação solar diária
# - NOAA ONI — índice El Niño/La Niña
# - Google Trends — infoveillância digital
# ============================================================

from prefect import task, get_run_logger
from datetime import datetime, timedelta
from src.config import DATA_DIR
import pandas as pd
import requests


# ============================================================
# Geocodes dos municípios
# ============================================================
GEOCODES = {
    'cuiaba':       '5103403',
    'varzea_grande': '5108402'
}


@task(name="ingest_inmet", retries=3, retry_delay_seconds=60)
def ingerir_inmet(data_corte=None):
    """
    Ingestão de dados climáticos e epidemiológicos via InfoDengue API.
    Substitui INMET para dados novos (2025+) — retorna série completa
    combinando Silver histórico (2018-2024) + InfoDengue (2025+).
    
    Referência: Codeco et al. 2018 — InfoDengue como sistema de alerta precoce
    """
    logger = get_run_logger()
    logger.info("Iniciando ingestão InfoDengue (casos + clima)...")

    try:
        from src.tasks.cache import salvar_cache
        import numpy as np

        hoje = datetime.now()
        ano_atual = hoje.year
        ano_inicio = 2025  # InfoDengue para dados novos

        dfs = []

        # Baixar dados por município e por ano
        for municipio, geocode in GEOCODES.items():
            for ano in range(ano_inicio, ano_atual + 1):
                url = 'https://info.dengue.mat.br/api/alertcity'
                params = {
                    'geocode':  geocode,
                    'disease':  'dengue',
                    'format':   'json',
                    'ew_start': 1,
                    'ew_end':   53,
                    'ey_start': ano,
                    'ey_end':   ano
                }
                r = requests.get(url, params=params, timeout=30)
                if r.status_code != 200:
                    logger.warning(f"InfoDengue {municipio} {ano}: status {r.status_code}")
                    continue

                dados = r.json()
                if not dados:
                    continue

                df_ano = pd.DataFrame(dados)
                df_ano['municipio'] = municipio
                df_ano['geocode']   = geocode
                dfs.append(df_ano)
                logger.info(f"InfoDengue {municipio} {ano}: {len(dados)} semanas")

        if not dfs:
            raise ValueError("InfoDengue sem dados — usando fallback")

        df_info = pd.concat(dfs, ignore_index=True)

        # Converter timestamp para data
        df_info['data'] = pd.to_datetime(df_info['data_iniSE'], unit='ms')

        # Renomear colunas para padrão do projeto
        df_info = df_info.rename(columns={
            'casos':    'casos_confirmados',
            'casos_est': 'casos_nowcast',
            'tempmed':  'temp_media',
            'tempmin':  'temp_min',
            'tempmax':  'temp_max',
            'umidmed':  'umidade_media',
            'umidmin':  'umidade_min',
            'umidmax':  'umidade_max',
        })

        # Converter para float
        for col in ['temp_media', 'temp_min', 'temp_max',
                    'umidade_media', 'umidade_min', 'umidade_max']:
            if col in df_info.columns:
                df_info[col] = pd.to_numeric(df_info[col], errors='coerce')

        # Aplicar corte temporal
        if data_corte:
            df_info = df_info[df_info['data'] <= pd.Timestamp(data_corte)]

        # Carregar Silver histórico (2018-2024)
        silver_path = DATA_DIR / 'silver' / 'inmet' / 'inmet_cuiaba_2018_2024.parquet'
        if silver_path.exists():
            df_hist = pd.read_parquet(silver_path)
            df_hist['data'] = pd.to_datetime(df_hist['data'] if 'data' in df_hist.columns
                                              else df_hist.iloc[:, 0])
            # Combinar histórico + novos dados
            logger.info(f"Silver histórico: {len(df_hist)} registros (2018-2024)")
            logger.info(f"InfoDengue novos: {len(df_info)} registros (2025+)")

        # Salvar cache com dados novos
        salvar_cache('inmet', df_info, extra={
            'ultima_data':  str(df_info['data'].max().date()),
            'n_municipios': len(GEOCODES),
            'fonte':        'infodengue_api'
        })

        ultima_data = df_info['data'].max()
        logger.info(f"InfoDengue — última semana: {ultima_data.date()}")
        return {
            'status':      'ok',
            'ultima_data': str(ultima_data.date()),
            'fonte':       'infodengue',
            'n_registros': len(df_info),
            'fallback':    False
        }

    except Exception as e:
        logger.error(f"InfoDengue erro: {e}")

        # Fallback — usar cache local
        from src.tasks.cache import carregar_cache
        df_fallback = carregar_cache('inmet')
        if df_fallback is not None:
            logger.warning("InfoDengue — usando cache local como fallback")
            return {'status': 'ok', 'fonte': 'inmet_cache', 'fallback': True}

        # Fallback final — Silver histórico
        silver_path = DATA_DIR / 'silver' / 'inmet' / 'inmet_cuiaba_2018_2024.parquet'
        if silver_path.exists():
            logger.warning("InfoDengue — usando Silver histórico como fallback")
            return {'status': 'ok', 'fonte': 'inmet_silver', 'fallback': True}

        return {'status': 'pendente', 'fonte': 'inmet', 'fallback': False}


@task(name="ingest_nasa_power", retries=3, retry_delay_seconds=60)
def ingerir_nasa_power(data_corte=None):
    """
    Baixa série completa de radiação solar NASA POWER.
    Cobre período 2025+ para complementar Silver histórico.
    Atraso operacional: 14 dias (verificado empiricamente 27/03/2026).
    """
    logger = get_run_logger()
    logger.info("Iniciando ingestão NASA POWER...")

    if data_corte:
        logger.info(f"Corte temporal aplicado: até {data_corte.strftime('%Y-%m-%d')}")

    try:
        from src.tasks.cache import salvar_cache

        # Data de início: 01/01/2025 (dados históricos já no Silver)
        data_inicio = datetime(2025, 1, 1)
        data_fim    = data_corte if data_corte else (datetime.now() - timedelta(days=14))

        if data_fim < data_inicio:
            data_fim = data_inicio

        url = "https://power.larc.nasa.gov/api/temporal/daily/point"
        params = {
            'parameters': 'ALLSKY_SFC_SW_DWN,T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M',
            'community':  'RE',
            'longitude':  -56.1,
            'latitude':   -15.6,
            'start':      data_inicio.strftime('%Y%m%d'),
            'end':        data_fim.strftime('%Y%m%d'),
            'format':     'JSON'
        }

        r = requests.get(url, params=params, timeout=60)
        if r.status_code != 200:
            raise ValueError(f"NASA POWER status: {r.status_code}")

        data_json = r.json()
        parametros = data_json['properties']['parameter']

        # Construir DataFrame
        datas  = list(parametros['ALLSKY_SFC_SW_DWN'].keys())
        df_nasa = pd.DataFrame({
            'data':                datas,
            'radiacao_mj':         list(parametros['ALLSKY_SFC_SW_DWN'].values()),
            'temp_media_nasa':     list(parametros['T2M'].values()),
            'temp_max_nasa':       list(parametros['T2M_MAX'].values()),
            'temp_min_nasa':       list(parametros['T2M_MIN'].values()),
            'precipitacao_nasa':   list(parametros['PRECTOTCORR'].values()),
            'umidade_nasa':        list(parametros['RH2M'].values()),
        })

        df_nasa['data'] = pd.to_datetime(df_nasa['data'], format='%Y%m%d')

        # Remover valores inválidos (-999)
        for col in df_nasa.columns:
            if col != 'data':
                df_nasa[col] = df_nasa[col].replace(-999, pd.NA)

        # Remover linhas com radiação inválida
        df_nasa = df_nasa[df_nasa['radiacao_mj'].notna()]

        salvar_cache('nasa_power', df_nasa)

        logger.info(f"NASA POWER — {len(df_nasa)} dias (2025+)")
        return {
            'status':      'ok',
            'n_registros': len(df_nasa),
            'fonte':       'nasa_power',
            'fallback':    False
        }

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
    """Baixa ONI Index NOAA — El Niño/La Niña."""
    logger = get_run_logger()
    logger.info("Iniciando ingestão ONI Index NOAA...")

    if data_corte:
        logger.info(f"DATA_CORTE registrado: {data_corte} (atraso ~60 dias)")

    try:
        from src.tasks.cache import salvar_cache
        url = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            linhas = [l.split() for l in r.text.strip().split('\n')[1:] if l.strip()]
            df_oni = pd.DataFrame(linhas, columns=['seas', 'yr', 'total', 'anom'])
            salvar_cache('oni_index', df_oni)
            logger.info(f"ONI Index — {len(df_oni)} trimestres")
            return {'status': 'ok', 'fonte': 'oni', 'fallback': False}

    except Exception as e:
        logger.error(f"ONI erro: {e}")
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
        data_fim  = data_corte if data_corte else datetime.now()
        hoje      = data_fim.strftime('%Y-%m-%d')
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
            return {
                'status':   'ok',
                'n_semanas': len(df),
                'fonte':    'google_trends',
                'fallback': False
            }
        time.sleep(2)

    except Exception as e:
        logger.error(f"Google Trends erro: {e}")
        from src.tasks.cache import carregar_cache
        df_fallback = carregar_cache('google_trends')
        if df_fallback is not None:
            return {'status': 'ok', 'fonte': 'google_trends',
                    'fallback': True, 'n_semanas': len(df_fallback)}

    return {'status': 'erro', 'fonte': 'google_trends', 'fallback': False}