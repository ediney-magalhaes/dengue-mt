# ============================================================
# Dengue MT — Ingestão MODIS MOD13A3 → Bronze
# ============================================================
# Responsabilidade ÚNICA: buscar API AppEEARS NASA e salvar Bronze
# Produto: MOD13A3.061 — NDVI e EVI mensais 1km
# Substitui GEE como fonte de índices de vegetação
# Período: 2018→atual | Municípios: Cuiabá + Várzea Grande
# ============================================================

import logging
import requests
import pandas as pd
import time
from datetime import datetime
from pathlib import Path
from src.config import DATA_DIR

logger = logging.getLogger('dengue-mt.ingestion.modis')

BRONZE_DIR = DATA_DIR / 'bronze' / 'modis'
BRONZE_DIR.mkdir(parents=True, exist_ok=True)

# API AppEEARS NASA Earthdata
APPEEARS_URL = 'https://appeears.earthdatacloud.nasa.gov/api'

# Produto MODIS — NDVI e EVI mensais 1km
PRODUTO     = 'MOD13A3.061'
CAMADAS     = ['_1_km_monthly_NDVI', '_1_km_monthly_EVI',
               '_1_km_monthly_pixel_reliability']

# Municípios com coordenadas
MUNICIPIOS = {
    'cuiaba': {
        'geocode':   5103403,
        'latitude':  -15.5989,
        'longitude': -56.0949
    },
    'varzea_grande': {
        'geocode':   5108402,
        'latitude':  -15.6461,
        'longitude': -56.1324
    }
}


def autenticar(usuario: str, senha: str) -> str:
    """Autentica no AppEEARS e retorna token."""
    r = requests.post(
        f'{APPEEARS_URL}/login',
        auth=(usuario, senha),
        timeout=30
    )
    r.raise_for_status()
    token = r.json()['token']
    logger.info('AppEEARS autenticado com sucesso')
    return token


def submeter_tarefa(token: str, municipio: str, info: dict,
                    data_inicio: str, data_fim: str) -> str:
    """
    Submete tarefa de extração de série temporal para um ponto.
    Retorna o task_id da tarefa submetida.
    """
    headers = {'Authorization': f'Bearer {token}'}

    tarefa = {
        'task_type': 'point',
        'task_name': f'dengue_mt_{municipio}_{data_inicio}_{data_fim}',
        'params': {
            'dates': [{'startDate': data_inicio, 'endDate': data_fim}],
            'layers': [
                {'product': PRODUTO, 'layer': camada}
                for camada in CAMADAS
            ],
            'coordinates': [{
                'latitude':  info['latitude'],
                'longitude': info['longitude'],
                'id':        municipio,
                'category':  'dengue_mt'
            }]
        }
    }

    r = requests.post(
        f'{APPEEARS_URL}/task',
        json=tarefa,
        headers=headers,
        timeout=30
    )
    r.raise_for_status()
    task_id = r.json()['task_id']
    logger.info(f'Tarefa submetida: {municipio} — task_id: {task_id}')
    return task_id


def aguardar_tarefa(token: str, task_id: str,
                    timeout_min: int = 60) -> bool:
    """
    Aguarda conclusão da tarefa. Retorna True se concluída com sucesso.
    Verifica a cada 30 segundos por até timeout_min minutos.
    """
    headers  = {'Authorization': f'Bearer {token}'}
    inicio   = time.time()
    timeout  = timeout_min * 60

    while time.time() - inicio < timeout:
        r = requests.get(
            f'{APPEEARS_URL}/task/{task_id}',
            headers=headers,
            timeout=30
        )
        status = r.json().get('status', '')
        logger.info(f'Tarefa {task_id}: {status}')

        if status == 'done':
            return True
        if status == 'error':
            logger.error(f'Tarefa {task_id} falhou')
            return False

        time.sleep(30)

    logger.error(f'Tarefa {task_id} timeout após {timeout_min} min')
    return False


def baixar_resultado(token: str, task_id: str,
                     municipio: str, geocode: int) -> pd.DataFrame | None:
    """
    Baixa o resultado CSV da tarefa e retorna DataFrame Bronze.
    """
    headers = {'Authorization': f'Bearer {token}'}

    # Lista arquivos da tarefa
    r = requests.get(
        f'{APPEEARS_URL}/bundle/{task_id}',
        headers=headers,
        timeout=30
    )
    arquivos = r.json().get('files', [])

    # Busca o CSV de resultado
    for arq in arquivos:
        if arq['file_name'].endswith('.csv'):
            file_id = arq['file_id']
            r_csv = requests.get(
                f'{APPEEARS_URL}/bundle/{task_id}/{file_id}',
                headers=headers,
                stream=True,
                timeout=60
            )

            # Lê CSV diretamente da resposta
            from io import StringIO
            df = pd.read_csv(StringIO(r_csv.text))

            # Metadados Bronze
            df['municipio']   = municipio
            df['geocode']     = geocode
            df['ingestao_ts'] = datetime.now().isoformat()
            df['fonte']       = 'modis_appeears_api'

            return df

    logger.error(f'Nenhum CSV encontrado para tarefa {task_id}')
    return None


def ingerir_bronze(usuario: str, senha: str,
                   ano_inicio: int = 2018) -> list[Path]:
    """
    Ingere NDVI e EVI mensais do MODIS via AppEEARS NASA.
    Período: ano_inicio → ano atual.
    Retorna lista de paths dos arquivos Bronze salvos.
    """
    ano_fim     = datetime.now().year
    data_inicio = f'01-01-{ano_inicio}'
    data_fim    = f'12-31-{ano_fim}'

    # Verifica se Bronze já existe e está completo
    path = BRONZE_DIR / 'modis_ndvi_evi_latest.parquet'
    if path.exists():
        df_exist = pd.read_parquet(path)
        max_data = pd.to_datetime(df_exist['Date']).max()
        if max_data.year >= ano_fim:
            logger.info(f'Bronze MODIS já existe e está atualizado — pulando')
            return [path]

    try:
        # Autentica
        token = autenticar(usuario, senha)

        todos_dfs = []

        for municipio, info in MUNICIPIOS.items():
            # Submete tarefa
            task_id = submeter_tarefa(
                token, municipio, info, data_inicio, data_fim
            )

            # Aguarda conclusão
            logger.info(f'Aguardando tarefa {municipio}...')
            sucesso = aguardar_tarefa(token, task_id)

            if not sucesso:
                logger.error(f'MODIS {municipio}: tarefa falhou')
                continue

            # Baixa resultado
            df = baixar_resultado(token, task_id, municipio, info['geocode'])
            if df is not None:
                todos_dfs.append(df)
                logger.info(f'MODIS {municipio}: {len(df)} registros')

        if not todos_dfs:
            logger.error('MODIS: nenhum dado baixado')
            return []

        # Une municípios e salva Bronze
        df_final = pd.concat(todos_dfs, ignore_index=True)
        df_final.to_parquet(path, index=False)
        logger.info(f'Bronze MODIS salvo: {path.name} ({len(df_final)} registros)')
        return [path]

    except Exception as e:
        logger.error(f'MODIS AppEEARS: ERRO — {e}')
        return []