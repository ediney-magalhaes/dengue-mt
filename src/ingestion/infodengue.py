# ============================================================
# Dengue MT — Ingestão InfoDengue → Bronze
# ============================================================


import logging
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path
from src.config import DATA_DIR

# configuração dos registros de log
logger = logging.getLogger('dengue-mt.ingestion.infodengue')

#definição da pasta onde os arquivos serão salvos
BRONZE_DIR = DATA_DIR / 'bronze' / 'infodengue'
#criar pasta Bronze/infodengue se não existir / parents=True: cria as pastas intermediárias automaticamente / exist_ok=True: não gera erro se a pasta já existir
BRONZE_DIR.mkdir(parents=True, exist_ok=True)

#caminho da API infodengue
API_URL = 'https://info.dengue.mat.br/api/alertcity'
#Tempo de espera entre as requisições para cada ano (evitar sobrecarga no servidor)
DELAY_ENTRE_REQUESTS = 1.5  # segundos

#códigos das cidades
GEOCODES = {
    'cuiaba':        5103403,
    'varzea_grande': 5108402
}

#função para ingestão
def ingerir_bronze(ano_inicio: int = 2018) -> list[Path]:
    
    import time #biblioteca para gestão do tempo (usada no delay entre as requisições)
    # Definição do ano final
    ano_fim = int(datetime.now().year)
    # lista vazia para acumular os caminhos dos paths durante o loop
    salvos = []

    # laço para percorrer cada município
    for municipio, geocode in GEOCODES.items():
        # laço para ano do período histórico até o ano atual
        for ano in range(ano_inicio, ano_fim + 1):
            # definição do caminho e nome do arquivo salvo
            path = BRONZE_DIR / f'infodengue_{municipio}_{ano}.parquet'
            # Se o arquivo já existe pula (ano atual sempre ingere novamente atualizando a cada semana)
            if path.exists() and ano < ano_fim:
                logger.info(f'Bronze já existe — pulando: {path.name}')
                salvos.append(path)
                continue
            # Parâmetros da requisição — filtros enviados para a API InfoDengue / Busca todas as Semanas Epidemiológicas (1-53) do ano inteiro para o município
            params = {
                'geocode':  geocode, # código IBGE do município
                'disease':  'dengue',# doença alvo
                'format':   'json',  # formato de retorno
                'ew_start': 1,       # SE inicial (1 = primeira semana do ano)
                'ew_end':   53,      # SE final (53 = última semana do ano)
                'ey_start': ano,     # ano inicial
                'ey_end':   ano      # ano final (mesmo ano = 1 ano por requisição)
            }
            # Tratamento e captura de erros
            try:
                # Faz a requisição HTTP GET para a API / timeout=30: desiste se não responder em 30 segundos
                r = requests.get(API_URL, params=params, timeout=30)
                # Lança erro se API retornou status HTTP de falha (4xx, 5xx)
                r.raise_for_status()
                # Converte resposta JSON em lista de dicionários
                dados = r.json()
                # Verifica se a API retornou dados — pode retornar 200 mas lista vazia (ex: ano sem registros ou dados ainda não consolidados)
                if not dados:
                    logger.warning(f'InfoDengue {municipio} {ano}: sem dados')
                    continue

                # Monta DataFrame Bronze — dados da API + metadados de rastreabilidade
                df = pd.DataFrame(dados)
                df['municipio']   = municipio                  # nome padronizado do município
                df['geocode']     = geocode                    # código IBGE
                df['ingestao_ts'] = datetime.now().isoformat() # timestamp da ingestão
                df['fonte']       = 'infodengue_api'           # origem dos dados

                # Salva DataFrame em formato Parquet no Bronze / index=False -> não salva índice desnecessário
                df.to_parquet(path, index=False)
                # Registra o path na lista de salvos e loga confirmação
                salvos.append(path)
                logger.info(f'Bronze salvo: {path.name} ({len(df)} registros)')
            # Captura qualquer erro sem interromper o script / registra no log e continua para o próximo ano/município
            except Exception as e:
                logger.error(f'InfoDengue {municipio} {ano}: ERRO — {e}')
            # Pausa entre requisições — respeita o servidor público da InfoDengue / executado sempre, independente de sucesso ou erro
            time.sleep(DELAY_ENTRE_REQUESTS)
    # Retorna lista com todos os arquivos salvos
    return salvos