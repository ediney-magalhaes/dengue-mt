# ============================================================
# Dengue MT — Ingestão Google Trends → Bronze
# ============================================================

import logging
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from src.config import DATA_DIR

# Configuração de logs
logger = logging.getLogger('dengue-mt.ingestion')

# Definição da pasta onde os arquivos serão salvos
BRONZE_DIR = DATA_DIR / 'bronze' / 'trends'

# Criar pasta Bronze/trends se não existir / parents=True: cria as pastas intermediárias automaticamente / exist_ok=True: não gera erro se a pasta já existir
BRONZE_DIR.mkdir(parents=True, exist_ok=True)

# Função de ingestão -> retorna data frame bruto
def ingerir_bronze(data_corte=None) -> pd.DataFrame | None:
    
    # Biblioteca para busca no Google Trends
    from pytrends.request import TrendReq

    # Definição do idioma e fuso horário Cuiabá
    pytrends  = TrendReq(hl='pt-BR', tz=-240)

    # Definição da data que será usada
    data_fim  = data_corte if data_corte else datetime.now()
    
    # Formatação da data fim como string
    data_fim_str = data_fim.strftime('%Y-%m-%d')
    
    # Calcula o inicio: 90 dias antes da data fim
    inicio = (data_fim - timedelta(days=90)).strftime('%Y-%m-%d')

    try:
        # Termo buscado no trends / período de busca / região (estado)
        pytrends.build_payload(
            kw_list=['dengue'],
            timeframe=f'{inicio} {data_fim_str}',
            geo='BR-MT'
        )
        # Retorna data frame com índice de interesse (0-100) por semana
        df = pytrends.interest_over_time()

        # Verifica se a busca retornou vazio
        if df.empty:
            logger.warning("Google Trends retornou vazio")
            return None

        # Bronze — valores brutos da API
        df = df.reset_index()[['date', 'dengue']].copy()
        df.columns = ['data', 'trends_dengue_raw']
        df['ingestao_ts'] = datetime.now().isoformat()
        df['fonte']       = 'google_trends_api'
        df['geo']         = 'BR-MT'

        # Definição do caminho e nome do arquivo salvo
        path = BRONZE_DIR / 'trends_dengue_latest.parquet'
        
        # Salva os dados em formato parquet
        df.to_parquet(path, index=False)
        logger.info(f"Bronze Trends: {len(df)} semanas → {path.name}")
        return df
    except Exception as e:
        logger.error(f'Google Trends: ERRO - {e}')
        return None