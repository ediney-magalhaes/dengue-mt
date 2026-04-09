# ============================================================
# Dengue MT — Ingestão ONI Index NOAA → Bronze
# ============================================================

import logging
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path
from src.config import DATA_DIR

# Configurações de log
logger = logging.getLogger('dengue-mt.ingestion')

# Definição da pasta onde os arquivos serão salvos
BRONZE_DIR = DATA_DIR / 'bronze' / 'oni'

# Criar pasta Bronze/oni se não existir / parents=True: cria as pastas intermediárias automaticamente / exist_ok=True: não gera erro se a pasta já existir
BRONZE_DIR.mkdir(parents=True, exist_ok=True)

# Caminho da API ONI
ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"

# Função de ingestão -> retorna data frame bruto
def ingerir_bronze() -> pd.DataFrame:
    
    # Tratamento de erros
    try:
        r = requests.get(ONI_URL, timeout=15)

        # Lança erro se API retornou status HTTP de falha (4xx, 5xx)
        r.raise_for_status()
        
        linhas = [l.split() for l in r.text.strip().split('\n')[1:] if l.strip()]
        
        # Bronze — valores brutos da API
        df     = pd.DataFrame(linhas, columns=['seas', 'yr', 'total', 'anom'])
        
        # Metadados de rastreabilidade
        df['ingestao_ts'] = datetime.now().isoformat()
        df['fonte']       = 'noaa_oni'
        
        path = BRONZE_DIR / 'oni_index_latest.parquet'
        
        # Salva DataFrame em formato Parquet no Bronze / index=False -> não salva índice desnecessário
        df.to_parquet(path, index=False)
        logger.info(f"Bronze ONI: {len(df)} trimestres → {path.name}")
        return df
    
    # Captura qualquer erro sem interromper o script / registra no log e continua para o próximo ano/município
    except Exception as e:
        logger.error(f'ONI NOAA: ERRO — {e}')
        return None

