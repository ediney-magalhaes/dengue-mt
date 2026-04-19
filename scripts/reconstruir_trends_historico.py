"""
Reconstrução histórica Google Trends — 2018→2025
Técnica: overlapping windows com normalização por fator de alinhamento

Referência: Scientific Data (Nature) 2026 — overlapping windows para
dados de vigilância epidemiológica digital no Brasil.

Metodologia:
1. Busca janelas de 270 dias com overlap de 180 dias
2. Calcula fator de normalização no período de sobreposição
3. Alinha todas as janelas para escala comum
4. Salva série histórica completa no Bronze
"""

import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('trends_historico')

BRONZE_DIR = Path('data/bronze/trends')
BRONZE_DIR.mkdir(parents=True, exist_ok=True)

# Parâmetros das janelas
JANELA_DIAS  = 270   # tamanho de cada janela
OVERLAP_DIAS = 180   # sobreposição entre janelas
PASSO_DIAS   = JANELA_DIAS - OVERLAP_DIAS  # 90 dias por passo

DATA_INICIO = datetime(2018, 1, 1)
DATA_FIM    = datetime(2025, 12, 31)


def buscar_janela(pytrends, data_inicio: datetime,
                  data_fim: datetime) -> pd.DataFrame | None:
    """Busca uma janela de dados do Google Trends."""
    timeframe = (f'{data_inicio.strftime("%Y-%m-%d")} '
                 f'{data_fim.strftime("%Y-%m-%d")}')
    try:
        pytrends.build_payload(
            kw_list=['dengue'],
            timeframe=timeframe,
            geo='BR-MT'
        )
        df = pytrends.interest_over_time()

        if df.empty:
            logger.warning(f'Janela vazia: {timeframe}')
            return None

        df = df.reset_index()[['date', 'dengue']].copy()
        df.columns = ['data', 'valor']
        df['data'] = pd.to_datetime(df['data'])
        return df

    except Exception as e:
        logger.error(f'Erro na janela {timeframe}: {e}')
        return None


def normalizar_janelas(janelas: list[pd.DataFrame]) -> pd.DataFrame:
    """
    Alinha todas as janelas para escala comum usando fatores
    de normalização calculados nos períodos de sobreposição.

    Referência: Scientific Data (Nature) 2026 — alinhamento de curvas
    via fator de normalização no período sobreposto.
    """
    if not janelas:
        return pd.DataFrame()

    # Primeira janela é a referência
    serie = janelas[0].copy()
    serie = serie.set_index('data')

    for i in range(1, len(janelas)):
        nova = janelas[i].set_index('data')

        # Encontra período de sobreposição
        overlap_inicio = nova.index.min()
        overlap_fim    = serie.index.max()

        if overlap_inicio > overlap_fim:
            # Sem sobreposição — concatena diretamente
            serie = pd.concat([serie, nova[nova.index > overlap_fim]])
            continue

        # Calcula fator de normalização no overlap
        overlap_serie = serie.loc[overlap_inicio:overlap_fim, 'valor']
        overlap_nova  = nova.loc[overlap_inicio:overlap_fim, 'valor']

        # Evita divisão por zero
        media_nova = overlap_nova.mean()
        if media_nova == 0:
            fator = 1.0
        else:
            fator = overlap_serie.mean() / media_nova

        logger.info(f'Janela {i}: fator de normalização = {fator:.4f}')

        # Aplica fator e adiciona período novo
        nova_normalizada = nova.copy()
        nova_normalizada['valor'] = nova_normalizada['valor'] * fator

        # Adiciona apenas datas novas (após o fim da série atual)
        novas_datas = nova_normalizada[nova_normalizada.index > overlap_fim]
        serie = pd.concat([serie, novas_datas])

    serie = serie.reset_index()
    serie.columns = ['data', 'valor']

    # Normaliza série final para escala 0-100
    valor_max = serie['valor'].max()
    if valor_max > 0:
        serie['trends_dengue_historico'] = (
            serie['valor'] / valor_max * 100
        ).round(2)
    else:
        serie['trends_dengue_historico'] = serie['valor']

    return serie[['data', 'trends_dengue_historico']]


def reconstruir_historico() -> Path | None:
    """
    Reconstrói série histórica Google Trends 2018→2025
    via overlapping windows com normalização.
    """
    from pytrends.request import TrendReq

    pytrends = TrendReq(hl='pt-BR', tz=-240)

    # Gera janelas de busca
    janelas_params = []
    data_atual = DATA_INICIO

    while data_atual < DATA_FIM:
        fim = min(data_atual + timedelta(days=JANELA_DIAS), DATA_FIM)
        janelas_params.append((data_atual, fim))
        data_atual += timedelta(days=PASSO_DIAS)

    logger.info(f'Total de janelas: {len(janelas_params)}')

    # Busca cada janela
    janelas_dados = []
    for i, (inicio, fim) in enumerate(janelas_params):
        logger.info(f'Janela {i+1}/{len(janelas_params)}: '
                    f'{inicio.strftime("%Y-%m-%d")} → '
                    f'{fim.strftime("%Y-%m-%d")}')

        df = buscar_janela(pytrends, inicio, fim)
        if df is not None:
            janelas_dados.append(df)

        # Delay entre requisições
        time.sleep(2)

    if not janelas_dados:
        logger.error('Nenhuma janela retornou dados')
        return None

    # Normaliza e alinha janelas
    logger.info('Normalizando e alinhando janelas...')
    serie = normalizar_janelas(janelas_dados)

    if serie.empty:
        logger.error('Série histórica vazia após normalização')
        return None

    # Adiciona metadados Bronze
    serie['ingestao_ts'] = datetime.now().isoformat()
    serie['fonte']       = 'google_trends_overlapping_windows'
    serie['geo']         = 'BR-MT'
    serie['metodologia'] = 'Scientific Data Nature 2026'

    # Salva Bronze
    path = BRONZE_DIR / 'trends_dengue_historico_2018_2025.parquet'
    serie.to_parquet(path, index=False)

    logger.info(f'Série histórica salva: {path.name}')
    logger.info(f'Período: {serie["data"].min()} → {serie["data"].max()}')
    logger.info(f'Total semanas: {len(serie)}')

    return path


if __name__ == '__main__':
    print('=== Reconstrução histórica Google Trends ===')
    print(f'Período: {DATA_INICIO.strftime("%Y-%m-%d")} → '
          f'{DATA_FIM.strftime("%Y-%m-%d")}')
    print(f'Janelas: {JANELA_DIAS} dias | Overlap: {OVERLAP_DIAS} dias')
    print()

    path = reconstruir_historico()

    if path:
        import pandas as pd
        df = pd.read_parquet(path)
        print(f'\n✅ Concluído!')
        print(f'Arquivo: {path}')
        print(f'Registros: {len(df)}')
        print(df.head())
    else:
        print('\n❌ Falha na reconstrução')