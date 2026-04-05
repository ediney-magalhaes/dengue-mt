# ============================================================
# Dengue MT — Task: Build Gold Dataset
# ============================================================
# Responsabilidade: atualizar Gold preservando histórico
#
# Arquitetura:
# Gold anterior (completo, todas features) ← preservado
#         +
# Silver novo (semanas novas apenas)
#         ↓
# feature_engineering apenas nas semanas novas
#         ↓
# Gold atualizado = Gold anterior + novas semanas
#
# Referência: Codeco et al. 2018 — séries temporais epidemiológicas
# ============================================================

import logging
import numpy as np
import pandas as pd
from prefect import task, get_run_logger
from src.config import DATA_DIR

logger = logging.getLogger('dengue-mt.pipeline')

GOLD_PATH    = DATA_DIR / 'gold' / 'dataset_features_v4.parquet'
GOLD_HIST = DATA_DIR / 'gold' / 'dataset_features_v4_hist.parquet'  # fallback local
SILVER_INFO  = DATA_DIR / 'silver' / 'infodengue' / 'infodengue_2025_atual.parquet'
SILVER_NASA  = DATA_DIR / 'silver' / 'nasa_power' / 'nasa_power_2025_atual.parquet'


@task(name="build_gold")
def build_gold_dataset(data_corte=None) -> dict:
    """
    Atualiza o Gold dataset preservando o histórico completo.

    Estratégia incremental:
    1. Carrega Gold anterior como base (todas features preservadas)
    2. Identifica semanas novas no Silver (após última data do Gold)
    3. Calcula features apenas para semanas novas
    4. Concatena Gold anterior + semanas novas
    5. Salva Gold atualizado

    Vantagem: features históricas (trends_lag, ndbi, ndvi)
    são preservadas sem recálculo — sem perda de informação.
    """
    logger_pf = get_run_logger()
    logger_pf.info("Build Gold — atualização incremental...")

    try:
        from src.features.feature_engineering import calcular_features_novas

        # ── 1. Carregar Gold base ─────────────────────────────
        df_gold_base = _carregar_gold_base(logger_pf)

        # ── 2. Carregar semanas novas do Silver ───────────────
        ultima_data_gold = df_gold_base['data'].max()
        df_novo = _carregar_semanas_novas(ultima_data_gold, data_corte, logger_pf)

        if df_novo is None or df_novo.empty:
            logger_pf.info(f"Gold já atualizado até {ultima_data_gold.date()}")
            return {
                'status':      'ok',
                'motivo':      'gold_atualizado',
                'n_registros': len(df_gold_base),
                'ultima_data': str(ultima_data_gold.date())
            }

        # ── 3. Calcular features para semanas novas ───────────
        df_novas_com_features = calcular_features_novas(df_novo, df_gold_base)
        logger_pf.info(f"Features calculadas para {len(df_novas_com_features)} semanas novas")

        # ── 4. Concatenar Gold anterior + semanas novas ───────
        df_gold = pd.concat([df_gold_base, df_novas_com_features], ignore_index=True)
        df_gold = df_gold.sort_values('data').reset_index(drop=True)

        if data_corte:
            df_gold = df_gold[df_gold['data'] <= pd.Timestamp(data_corte)]

        # ── 5. Salvar Gold ────────────────────────────────────
        GOLD_PATH.parent.mkdir(parents=True, exist_ok=True)
        df_gold.to_parquet(GOLD_PATH, index=False)

        periodo = f"{df_gold['data'].min().date()} → {df_gold['data'].max().date()}"
        logger_pf.info(f"Gold salvo: {len(df_gold)} registros | {periodo}")

        return {
            'status':      'ok',
            'n_registros': len(df_gold),
            'n_novos':     len(df_novas_com_features),
            'n_features':  df_gold.shape[1],
            'ultima_data': str(df_gold['data'].max().date()),
            'periodo':     periodo
        }

    except Exception as e:
        import traceback
        logger_pf.error(f"Erro no build Gold: {e}\n{traceback.format_exc()}")
        return {'status': 'erro', 'motivo': str(e)}


def _carregar_gold_base(logger_pf) -> pd.DataFrame:
    """
    Carrega Gold base — fonte de verdade histórica.
    Prioridade:
    1. Gold local atual (se já tem dados 2025+)
    2. Gold local hist snapshot
    3. HF Hub — download automático
    """
    # 1. Gold local atual com dados 2025+
    if GOLD_PATH.exists():
        df = pd.read_parquet(GOLD_PATH)
        df['data'] = pd.to_datetime(df['data'])
        if df['data'].max().year >= 2025:
            logger_pf.info(f"Gold base local: {len(df)} registros até {df['data'].max().date()}")
            return df.sort_values('data').reset_index(drop=True)

    # 2. Snapshot histórico local
    if GOLD_HIST.exists():
        df = pd.read_parquet(GOLD_HIST)
        df['data'] = pd.to_datetime(df['data'])
        logger_pf.info(f"Gold hist snapshot: {len(df)} registros até {df['data'].max().date()}")
        return df.sort_values('data').reset_index(drop=True)

    # 3. Fallback — HF Hub
    logger_pf.warning("Gold local não encontrado — baixando do HF Hub...")
    try:
        from huggingface_hub import hf_hub_download
        import shutil
        path = hf_hub_download(
            repo_id='edyestatistica/dengue-mt-medallion',
            filename='gold/dataset_features_v4_latest.parquet',
            repo_type='dataset'
        )
        GOLD_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(path, GOLD_PATH)
        df = pd.read_parquet(GOLD_PATH)
        df['data'] = pd.to_datetime(df['data'])
        logger_pf.info(f"Gold baixado do HF Hub: {len(df)} registros até {df['data'].max().date()}")
        return df.sort_values('data').reset_index(drop=True)
    except Exception as e:
        raise FileNotFoundError(f"Gold base não encontrado local nem no HF Hub: {e}")


def _carregar_semanas_novas(ultima_data: pd.Timestamp,
                             data_corte,
                             logger_pf) -> pd.DataFrame | None:
    """
    Carrega apenas semanas novas do Silver InfoDengue + NASA POWER.
    Retorna None se não há dados novos.
    """
    if not SILVER_INFO.exists():
        logger_pf.warning("Silver InfoDengue não disponível")
        return None

    df = pd.read_parquet(SILVER_INFO)
    df['data'] = pd.to_datetime(df['data'])

    # Agregar por data (soma casos Cuiabá + VG, média clima)
    agg = {c: ('sum' if c in ['casos_confirmados', 'casos_nowcast']
                else 'first' if c in ['municipio', 'geocode', 'SE', 'pop',
                                       'receptivo', 'transmissao', 'nivel_alerta']
                else 'mean')
           for c in df.columns if c != 'data'}
    df = df.groupby('data').agg(agg).reset_index()

    # Apenas semanas NOVAS — após última data do Gold
    df = df[df['data'] > ultima_data].copy()

    if df.empty:
        return None

    # Adicionar NASA POWER (diário → semanal, alinhado ao domingo)
    if SILVER_NASA.exists():
        df_nasa = pd.read_parquet(SILVER_NASA)
        df_nasa['data'] = pd.to_datetime(df_nasa['data'])
        # Alinhar ao domingo da SE (InfoDengue)
        df_nasa['semana'] = df_nasa['data'] - pd.to_timedelta(
            df_nasa['data'].dt.dayofweek + 1, unit='D'
        )
        df_nasa['semana'] = df_nasa['semana'].dt.normalize()
        df_nasa_sem = df_nasa.groupby('semana').agg({
            'radiacao_mj':       'mean',
            'precipitacao_nasa': 'sum',
            'umidade_nasa':      'mean',
        }).reset_index().rename(columns={'semana': 'data'})
        df = df.merge(df_nasa_sem, on='data', how='left')

    # Padronizar nomes de colunas
    df = df.rename(columns={
        'casos_confirmados': 'casos',
        'precipitacao_nasa': 'precipitacao_total',
        'umidade_nasa':      'umidade_media',
    })

    # Garantir colunas mínimas
    for col in ['casos', 'temp_media', 'temp_max', 'temp_min',
                'precipitacao_total', 'umidade_media',
                'umidade_max', 'umidade_min', 'radiacao_mj']:
        if col not in df.columns:
            df[col] = np.nan

    if data_corte:
        df = df[df['data'] <= pd.Timestamp(data_corte)]

    logger_pf.info(f"Semanas novas: {len(df)} registros após {ultima_data.date()}")
    return df.sort_values('data').reset_index(drop=True)