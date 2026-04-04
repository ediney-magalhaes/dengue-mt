# ============================================================
# Dengue MT — Feature Engineering
# ============================================================
# Responsabilidade: calcular features a partir do Silver
# Usado por: build_gold.py (pipeline semanal)
#
# Princípio: Single Responsibility
# - calcular_todas_features: série completa (inicial)
# - calcular_features_novas: apenas semanas novas (incremental)
#
# Referência: Codeco et al. 2018, Souza et al. 2022
# ============================================================

import logging
import numpy as np
import pandas as pd
from src.config import DATA_DIR

logger = logging.getLogger('dengue-mt.features')

# ── Silver paths ──────────────────────────────────────────────
SILVER_ONI   = DATA_DIR / 'silver' / 'oni'    / 'oni_index_latest.parquet'
SILVER_TREND = DATA_DIR / 'silver' / 'trends' / 'trends_dengue_latest.parquet'
SILVER_GEE   = DATA_DIR / 'silver' / 'gee'    / 'gee_ndvi_ndwi_blend_2018_2024.parquet'

# ── Constantes ────────────────────────────────────────────────
POP_CUIABA_VG    = 694244 + 315711  # Censo IBGE 2022
PICOS_EPIDEMICOS = [2020, 2024]

TRIM_MAP = {
     1: 'DJF',  2: 'DJF',  3: 'MAM',  4: 'MAM',  5: 'MAM',
     6: 'JJA',  7: 'JJA',  8: 'JJA',  9: 'SON', 10: 'SON',
    11: 'SON', 12: 'DJF'
}

FATORES_NOWCAST = {
     1: 3.0,  2: 3.0,  3: 2.5,  4: 2.0,  5: 1.5,
     6: 1.2,  7: 1.1,  8: 1.05, 9: 1.0, 10: 1.0,
    11: 1.0, 12: 1.07
}

# Colunas que não devem ir ao Gold
COLS_REMOVER = ['municipio', 'geocode', 'rt_index', 'nivel_alerta',
                'incidencia_100k', 'SE', 'pop', 'receptivo', 'transmissao',
                'trends_dengue', 'ndvi_x', 'ndvi_y', 'ndwi_x', 'ndwi_y']

# Colunas base para contexto histórico nos cálculos incrementais
COLS_BASE = ['data', 'casos', 'temp_media', 'temp_max', 'temp_min',
             'precipitacao_total', 'umidade_media', 'umidade_max',
             'umidade_min', 'radiacao_mj']


# ============================================================
# API pública
# ============================================================

def calcular_todas_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula TODAS as features para uma série completa.
    Usado na inicialização do Gold — não no pipeline semanal.
    Entrada: DataFrame Silver integrado
    Saída:   DataFrame Gold com todas as features
    """
    df = df.copy()
    df['data'] = pd.to_datetime(df['data'])
    df = df.sort_values('data').reset_index(drop=True)

    df = _temporais(df)
    df = _lags_casos(df)
    df = _climaticas(df)
    df = _oni(df)
    df = _trends(df)
    df = _gee(df)
    df = _epidemicas(df)
    df = _nowcast(df)
    df = df.drop(columns=[c for c in COLS_REMOVER if c in df.columns])

    logger.info(f"calcular_todas_features: {len(df)} registros × {df.shape[1]} colunas")
    return df


def calcular_features_novas(df_novo: pd.DataFrame,
                             df_gold_hist: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula features apenas para semanas novas usando Gold histórico
    como contexto para lags e médias móveis.

    Estratégia incremental:
    - Concatena colunas base do histórico + novas semanas
    - Calcula features na série completa
    - Retorna apenas as semanas novas com features calculadas

    Vantagem: lags calculados corretamente sem perder histórico.
    Referência: Codeco et al. 2018 — continuidade da série temporal
    """
    if df_novo is None or df_novo.empty:
        return pd.DataFrame()

    # Selecionar colunas base do histórico (evitar duplicatas)
    cols_base_disp = [c for c in COLS_BASE if c in df_gold_hist.columns]
    df_hist_base   = df_gold_hist[cols_base_disp].copy()
    df_hist_base['data'] = pd.to_datetime(df_hist_base['data'])

    df_novo = df_novo.copy()
    df_novo['data'] = pd.to_datetime(df_novo['data'])
    cols_novo_disp  = [c for c in COLS_BASE if c in df_novo.columns]

    # Série completa = histórico base + novas semanas
    df_completo = pd.concat(
        [df_hist_base, df_novo[cols_novo_disp]],
        ignore_index=True
    )
    df_completo = df_completo.sort_values('data').reset_index(drop=True)

    # Calcular todas as features na série completa
    df_completo = _temporais(df_completo)
    df_completo = _lags_casos(df_completo)
    df_completo = _climaticas(df_completo)
    df_completo = _oni(df_completo)
    df_completo = _trends(df_completo)
    df_completo = _gee(df_completo)
    df_completo = _epidemicas(df_completo)
    df_completo = _nowcast(df_completo)
    df_completo = df_completo.drop(
        columns=[c for c in COLS_REMOVER if c in df_completo.columns]
    )

    # Retornar apenas as semanas novas
    datas_novas  = pd.to_datetime(df_novo['data'].values)
    df_resultado = df_completo[df_completo['data'].isin(datas_novas)].copy()

    logger.info(f"calcular_features_novas: {len(df_resultado)} semanas novas")
    return df_resultado.reset_index(drop=True)


# ============================================================
# Funções privadas de feature engineering
# ============================================================

def _temporais(df: pd.DataFrame) -> pd.DataFrame:
    df['ano']            = df['data'].dt.year
    df['mes']            = df['data'].dt.month
    df['semana_ano']     = df['data'].dt.isocalendar().week.astype(int)
    df['dia_ano']        = df['data'].dt.dayofyear
    df['trimestre']      = df['data'].dt.quarter
    df['mes_seno']       = np.sin(2 * np.pi * df['mes'] / 12)
    df['mes_cosseno']    = np.cos(2 * np.pi * df['mes'] / 12)
    df['semana_seno']    = np.sin(2 * np.pi * df['semana_ano'] / 53)
    df['semana_cosseno'] = np.cos(2 * np.pi * df['semana_ano'] / 53)
    return df


def _lags_casos(df: pd.DataFrame) -> pd.DataFrame:
    for lag in [7, 14, 21, 28]:
        df[f'casos_lag_{lag}d'] = df['casos'].shift(lag)
    for janela in [7, 14, 28]:
        df[f'casos_mm_{janela}d'] = (
            df['casos'].rolling(window=janela, min_periods=1).mean()
        )
    df['casos_acum_ano'] = df.groupby('ano')['casos'].cumsum()
    return df


def _climaticas(df: pd.DataFrame) -> pd.DataFrame:
    if {'temp_max', 'temp_min'}.issubset(df.columns):
        df['amplitude_termica'] = df['temp_max'] - df['temp_min']

    if 'precipitacao_total' in df.columns:
        sem_chuva            = (df['precipitacao_total'] == 0)
        df['dias_sem_chuva'] = sem_chuva.groupby((~sem_chuva).cumsum()).cumsum()
        for lag in [28, 35, 42]:
            df[f'precip_lag_{lag}d'] = df['precipitacao_total'].shift(lag)
        for j in [7, 14, 28]:
            df[f'precip_mm_{j}d']   = df['precipitacao_total'].rolling(j, min_periods=1).mean()
            df[f'precip_acum_{j}d'] = df['precipitacao_total'].rolling(j, min_periods=1).sum()

    if 'umidade_media' in df.columns:
        for lag in [28, 35, 42]:
            df[f'umidade_lag_{lag}d'] = df['umidade_media'].shift(lag)
        for j in [7, 14, 28]:
            df[f'umidade_mm_{j}d'] = df['umidade_media'].rolling(j, min_periods=1).mean()

    if 'temp_media' in df.columns:
        for lag in [28, 35, 42]:
            df[f'temp_lag_{lag}d'] = df['temp_media'].shift(lag)

    if 'radiacao_mj' in df.columns:
        df['radiacao_lag_28d'] = df['radiacao_mj'].shift(28)
        df['radiacao_mm_14d']  = df['radiacao_mj'].rolling(14, min_periods=1).mean()

    return df


def _oni(df: pd.DataFrame) -> pd.DataFrame:
    if not SILVER_ONI.exists():
        df['oni_index']     = np.nan
        df['fase_enso_num'] = 0
        return df

    df_oni         = pd.read_parquet(SILVER_ONI)
    df_oni['yr']   = pd.to_numeric(df_oni['yr'],   errors='coerce')
    df_oni['anom'] = pd.to_numeric(df_oni['anom'], errors='coerce')

    def _lookup(row):
        seas  = TRIM_MAP.get(row['data'].month, 'DJF')
        match = df_oni[(df_oni['seas'] == seas) &
                       (df_oni['yr']   == row['data'].year)]
        return float(match.iloc[0]['anom']) if not match.empty else np.nan

    df['oni_index']     = df.apply(_lookup, axis=1)
    df['fase_enso_num'] = df['oni_index'].apply(
        lambda x: 1 if x > 0.5 else (-1 if x < -0.5 else 0)
        if pd.notna(x) else 0
    )
    return df


def _trends(df: pd.DataFrame) -> pd.DataFrame:
    # Remover trends existentes para evitar duplicatas
    for lag in [7, 14, 21]:
        if f'trends_lag_{lag}d' in df.columns:
            df = df.drop(columns=[f'trends_lag_{lag}d'])

    if not SILVER_TREND.exists():
        for lag in [7, 14, 21]:
            df[f'trends_lag_{lag}d'] = np.nan
        return df

    df_tr         = pd.read_parquet(SILVER_TREND)
    df_tr['data'] = pd.to_datetime(df_tr['data'])

    for lag in [7, 14, 21]:
        df_lag         = df_tr.copy()
        df_lag['data'] = df_lag['data'] + pd.Timedelta(days=lag)
        df_lag         = df_lag.rename(columns={'trends_dengue': f'trends_lag_{lag}d'})
        df = df.merge(df_lag[['data', f'trends_lag_{lag}d']], on='data', how='left')
    return df


def _gee(df: pd.DataFrame) -> pd.DataFrame:
    # Remover GEE existentes para evitar duplicatas
    for col in ['ndvi', 'ndwi', 'ndbi_gee', 'ndbi_lag_30d', 'ndbi_lag_60d',
                'ndvi_x', 'ndvi_y', 'ndwi_x', 'ndwi_y']:
        if col in df.columns:
            df = df.drop(columns=[col])

    if not SILVER_GEE.exists():
        for col in ['ndvi', 'ndwi', 'ndbi_gee', 'ndbi_lag_30d', 'ndbi_lag_60d']:
            df[col] = np.nan
        return df

    df_gee         = pd.read_parquet(SILVER_GEE)
    data_col       = 'data' if 'data' in df_gee.columns else 'mes'
    df_gee['data'] = pd.to_datetime(df_gee[data_col])
    df_gee         = df_gee.rename(columns={'ndvi_final': 'ndvi', 'ndwi_final': 'ndwi'})

    df['mes_ref']     = df['data'].dt.to_period('M').dt.start_time
    df_gee['mes_ref'] = df_gee['data'].dt.to_period('M').dt.start_time

    cols = ['mes_ref'] + [c for c in ['ndvi', 'ndwi', 'ndbi_gee'] if c in df_gee.columns]
    df   = df.merge(df_gee[cols], on='mes_ref', how='left')
    df   = df.drop(columns=['mes_ref'])

    if 'ndbi_gee' in df.columns:
        df['ndbi_lag_30d'] = df['ndbi_gee'].shift(30)
        df['ndbi_lag_60d'] = df['ndbi_gee'].shift(60)
    else:
        for col in ['ndbi_gee', 'ndbi_lag_30d', 'ndbi_lag_60d']:
            df[col] = np.nan
    return df


def _epidemicas(df: pd.DataFrame) -> pd.DataFrame:
    df['ciclo_epidemico'] = df['ano'].isin(PICOS_EPIDEMICOS).astype(int)
    df['anos_desde_pico'] = df['ano'].apply(
        lambda a: min(abs(a - p) for p in PICOS_EPIDEMICOS)
    )
    return df


def _nowcast(df: pd.DataFrame) -> pd.DataFrame:
    if 'casos_nowcast' not in df.columns:
        df['fator_nowcasting'] = df['mes'].map(FATORES_NOWCAST)
        df['casos_nowcast']    = (df['casos'] * df['fator_nowcasting']).round()
    elif 'fator_nowcasting' not in df.columns:
        df['fator_nowcasting'] = df['mes'].map(FATORES_NOWCAST)

    df['municipio_id']           = df.get('municipio_id', 0)
    df['casos_por_100k']         = (df['casos'] / POP_CUIABA_VG * 100000).round(2)
    df['casos_nowcast_por_100k'] = (df['casos_nowcast'] / POP_CUIABA_VG * 100000).round(2)
    return df