# ============================================================
# Dengue MT — Ingestão NASA POWER → Bronze
# ============================================================

import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from src.config import DATA_DIR

# Configuração do registro de logs
logger = logging.getLogger('dengue-mt.ingestion')

# Definição da pasta onde os arquivos serão salvos
BRONZE_DIR = DATA_DIR / 'bronze' / 'nasa_power'
# Criar pasta Bronze/nasa_power se não existir / parents=True: cria as pastas intermediárias automaticamente / exist_ok=True: não gera erro se a pasta já existir
BRONZE_DIR.mkdir(parents=True, exist_ok=True)

# Caminho da API NASA POWER
NASA_URL    = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMETROS  = 'ALLSKY_SFC_SW_DWN,T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M'

#Tempo de espera entre as requisições para cada ano (evitar sobrecarga no servidor)
DELAY_ENTRE_REQUESTS = 1.5  # segundos

# Códigos dos municípios
MUNICIPIOS = {
    'cuiaba': {
        'geocode': 5103403,
        'latitude': -15.5989,
        'longitude':-56.0949
    },
    'varzea_grande': {
        'geocode': 5108402,
        'latitude': -15.6461,
        'longitude': -56.1324
    }
}

# Função para ingestão
def ingerir_bronze(data_inicio: int = 2018) -> list[Path]:
    
    import time # Biblioteca para gestão do tempo (usada no delay entre as requisições)
    
    # Definição do ano final
    ano_fim = int(datetime.now().year)
    
    # Lista vazia para acumular os caminhos dos paths durante o loop
    salvos = []
    
    # Laço para percorrer os municícpios e suas informações
    for municipio, info in MUNICIPIOS.items():
        geocode = info['geocode']
        latitude = info['latitude']
        longitude = info['longitude']
        
        # Laço para ano do período histórico até o ano atual
        for ano in range(data_inicio, ano_fim + 1):
            
            # Definição do caminho e nome do arquivo salvo
            path = BRONZE_DIR / f'nasa_power_{municipio}_{ano}.parquet'
            
            # Se o arquivo já existe pula (ano atual sempre ingere novamente atualizando a cada semana)
            if path.exists() and ano < ano_fim:
                logger.info(f'Bronze já existe — pulando: {path.name}')
                salvos.append(path)
                continue
            
            # Parâmetros da requisição — filtros enviados para a API Nasa Power
            params = {
                'parameters': PARAMETROS,
                'community':  'RE',
                'geocode':    geocode,
                'longitude':  longitude,
                'latitude':   latitude,
                'start':      f'{ano}0101',
                'end':        f'{ano}1231',
                'format':     'JSON'
            }
            
            # Tratamento e captura de erros
            try:
                r = requests.get(NASA_URL, params=params, timeout=60)
                
                # Lança erro se API retornou status HTTP de falha (4xx, 5xx)
                r.raise_for_status()
                
                # Verifica se lista veio vazia
                resposta = r.json()
                if 'properties' not in resposta:
                    logger.warning(f'Nasa Power {municipio} {ano}: sem dados')
                    continue
                
                # Navega na estrutura do Nasa Power
                dados = resposta['properties']['parameter']
                datas      = list(dados['ALLSKY_SFC_SW_DWN'].keys())
                
                # Bronze — valores brutos da API
                df = pd.DataFrame({
                    'data_str':         datas,
                    'radiacao_raw':     list(dados['ALLSKY_SFC_SW_DWN'].values()),
                    'temp_media_raw':   list(dados['T2M'].values()),
                    'temp_max_raw':     list(dados['T2M_MAX'].values()),
                    'temp_min_raw':     list(dados['T2M_MIN'].values()),
                    'precipitacao_raw': list(dados['PRECTOTCORR'].values()),
                    'umidade_raw':      list(dados['RH2M'].values()),
                })
                
                # Metadados de rastreabilidade
                df['municipio']   = municipio
                df['geocode']     = geocode
                df['ingestao_ts'] = datetime.now().isoformat()
                df['fonte']       = 'nasa_power_api'
                df['latitude']    = latitude
                df['longitude']   = longitude 
                
                # Salva DataFrame em formato Parquet no Bronze / index=False -> não salva índice desnecessário
                df.to_parquet(path, index=False)
                
                # Registra o path na lista de salvos e loga confirmação
                salvos.append(path)
                logger.info(f'Bronze NASA POWER salvo: {path.name} ({len(df)} registros)')
                
                # Captura qualquer erro sem interromper o script / registra no log e continua para o próximo ano/município
            except Exception as e:
                logger.error(f'Nasa Power {municipio} {ano}: ERRO — {e}')
            
            # Pausa entre requisições / executado sempre, independente de sucesso ou erro
            time.sleep(DELAY_ENTRE_REQUESTS)
    
    # Retorna lista com todos os arquivos salvos
    return salvos