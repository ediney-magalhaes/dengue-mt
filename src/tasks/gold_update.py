# ============================================================
# Dengue MT — Task: Atualização do Gold Dataset
# ============================================================
# Integra dados históricos (Silver 2018-2024) com dados novos
# (InfoDengue 2025+ e NASA POWER 2025+) para gerar Gold atualizado
# ============================================================

import logging
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from prefect import task, get_run_logger

from src.config import DATA_DIR, MODELS_DIR

logger = logging.getLogger('dengue-mt.pipeline')

GOLD_PATH   = DATA_DIR / 'gold' / 'dataset_features_v4.parquet'
SILVER_INMET = DATA_DIR / 'silver' / 'inmet' / 'inmet_cuiaba_2018_2024.parquet'


@task(name="atualizar_gold")
def atualizar_gold_dataset(data_corte=None) -> dict:
    """
    Atualiza o Gold dataset integrando:
    - Silver histórico INMET (2018-2024)
    - InfoDengue API (2025+) — casos + clima semanal
    - NASA POWER (2025+) — radiação diária
    - ONI Index — ENSO
    - Google Trends — infoveillância

    Retorna dict com status e n_registros.
    """
    logger = get_run_logger()
    logger.info("Iniciando atualização do Gold dataset...")

    try:
        # ── 1. Carregar Gold atual ────────────────────────────
        if not GOLD_PATH.exists():
            logger.error("Gold dataset não encontrado!")
            return {'status': 'erro', 'motivo': 'gold não encontrado'}

        df_gold = pd.read_parquet(GOLD_PATH)
        df_gold['data'] = pd.to_datetime(df_gold['data'])
        ultima_data_gold = df_gold['data'].max()
        logger.info(f"Gold atual: {len(df_gold)} registros até {ultima_data_gold.date()}")

        # ── 2. Carregar dados InfoDengue do cache ─────────────
        from src.tasks.cache import carregar_cache
        df_info = carregar_cache('inmet')  # InfoDengue salvo no cache 'inmet'

        if df_info is None or df_info.empty:
            logger.warning("Cache InfoDengue vazio — Gold não atualizado")
            return {'status': 'ok', 'motivo': 'sem dados novos', 'n_registros': len(df_gold)}

        df_info['data'] = pd.to_datetime(df_info['data'])

        # Filtrar apenas dados NOVOS (após última data do Gold)
        df_novos = df_info[df_info['data'] > ultima_data_gold].copy()

        if df_novos.empty:
            logger.info("Gold já está atualizado — sem dados novos")
            return {'status': 'ok', 'motivo': 'gold_atualizado', 'n_registros': len(df_gold)}

        logger.info(f"Dados novos disponíveis: {len(df_novos)} registros")

        # ── 3. Carregar NASA POWER do cache ───────────────────
        df_nasa = carregar_cache('nasa_power')
        if df_nasa is not None and not df_nasa.empty:
            df_nasa['data'] = pd.to_datetime(df_nasa['data'])
            df_nasa = df_nasa[df_nasa['data'] > ultima_data_gold]
            logger.info(f"NASA POWER novos: {len(df_nasa)} registros")

        # ── 4. Carregar ONI do cache ──────────────────────────
        df_oni = carregar_cache('oni_index')

        # ── 5. Carregar Google Trends do cache ────────────────
        df_trends = carregar_cache('google_trends')
        if df_trends is not None:
            df_trends['data'] = pd.to_datetime(df_trends['data'])

        # ── 6. Construir novas linhas do Gold ─────────────────
        novas_linhas = []

        def _get_nasa_valor(df_n, data_ref, col):
            """Busca valor NASA POWER para a semana da data_ref."""
            if df_n is None or df_n.empty:
                return np.nan
            semana = df_n[
                (df_n['data'] >= data_ref) &
                (df_n['data'] < data_ref + pd.Timedelta(days=7))
            ]
            if semana.empty:
                return np.nan
            return float(semana[col].mean())

        for _, row in df_novos.iterrows():
            data_ref = row['data']

            # Casos da semana (InfoDengue — soma Cuiabá + VG)
            casos_semana = df_info[
                (df_info['data'] == data_ref)
            ]['casos_confirmados'].sum() if 'casos_confirmados' in df_info.columns else 0

            # Clima da semana (InfoDengue já tem médias semanais)
            clima = df_info[df_info['data'] == data_ref].iloc[0] if len(
                df_info[df_info['data'] == data_ref]) > 0 else {}

            # Radiação (NASA POWER — média da semana)
            radiacao = np.nan
            if df_nasa is not None and not df_nasa.empty:
                nasa_semana = df_nasa[
                    (df_nasa['data'] >= data_ref) &
                    (df_nasa['data'] < data_ref + pd.Timedelta(days=7))
                ]
                if not nasa_semana.empty:
                    radiacao = nasa_semana['radiacao_mj'].mean()

            # ONI Index (forward fill por trimestre)
            oni_val = np.nan
            fase_enso = 0
            if df_oni is not None and not df_oni.empty:
                mes = data_ref.month
                trimestre_map = {
                    1: 'DJF', 2: 'DJF', 3: 'MAM', 4: 'MAM', 5: 'MAM',
                    6: 'JJA', 7: 'JJA', 8: 'JJA', 9: 'SON', 10: 'SON',
                    11: 'SON', 12: 'DJF'
                }
                seas = trimestre_map.get(mes, 'DJF')
                ano  = str(data_ref.year)
                oni_row = df_oni[
                    (df_oni['seas'] == seas) & (df_oni['yr'] == ano)
                ]
                if not oni_row.empty:
                    oni_val  = float(oni_row.iloc[0]['anom'])
                    fase_enso = 1 if oni_val > 0.5 else (-1 if oni_val < -0.5 else 0)

            # Google Trends (lag 7d)
            trends_7d  = np.nan
            trends_14d = np.nan
            trends_21d = np.nan
            if df_trends is not None:
                t7  = df_trends[df_trends['data'] <= data_ref - pd.Timedelta(days=7)]
                t14 = df_trends[df_trends['data'] <= data_ref - pd.Timedelta(days=14)]
                t21 = df_trends[df_trends['data'] <= data_ref - pd.Timedelta(days=21)]
                if not t7.empty:  trends_7d  = float(t7.iloc[-1]['trends_dengue'])
                if not t14.empty: trends_14d = float(t14.iloc[-1]['trends_dengue'])
                if not t21.empty: trends_21d = float(t21.iloc[-1]['trends_dengue'])

            # Lags de casos (usando Gold histórico)
            def get_lag(dias):
                data_lag = data_ref - pd.Timedelta(days=dias)
                # Buscar no Gold histórico
                row_lag  = df_gold[df_gold['data'] == data_lag]
                if not row_lag.empty:
                    return float(row_lag['casos'].iloc[0])
                # Buscar nas novas linhas já processadas
                for nl in novas_linhas:
                    if nl['data'] == data_lag:
                        return float(nl['casos'])
                return np.nan

            nova_linha = {
                'data':               data_ref,
                'casos':              casos_semana,
                'temp_media':         float(clima.get('temp_media', np.nan)) if hasattr(clima, 'get') else np.nan,
                'temp_max':           float(clima.get('temp_max', np.nan)) if hasattr(clima, 'get') else np.nan,
                'temp_min':           float(clima.get('temp_min', np.nan)) if hasattr(clima, 'get') else np.nan,
                'umidade_media':      float(clima.get('umidade_media', np.nan)) if hasattr(clima, 'get') else np.nan,
                'umidade_max':        float(clima.get('umidade_max', np.nan)) if hasattr(clima, 'get') else np.nan,
                'umidade_min':        float(clima.get('umidade_min', np.nan)) if hasattr(clima, 'get') else np.nan,
                'precipitacao_total': _get_nasa_valor(df_nasa, data_ref, 'precipitacao_nasa'),
                'radiacao_mj':        radiacao,
                'oni_index':          oni_val,
                'fase_enso_num':      fase_enso,
                'trends_lag_7d':      trends_7d,
                'trends_lag_14d':     trends_14d,
                'trends_lag_21d':     trends_21d,
                'casos_lag_7d':       get_lag(7),
                'casos_lag_14d':      get_lag(14),
                'casos_lag_21d':      get_lag(21),
                'casos_lag_28d':      get_lag(28),
            }
            novas_linhas.append(nova_linha)

        if not novas_linhas:
            logger.info("Nenhuma nova linha gerada")
            return {'status': 'ok', 'motivo': 'sem_novas_linhas', 'n_registros': len(df_gold)}

        df_novas = pd.DataFrame(novas_linhas)

        # ── 7. Concatenar com Gold existente ──────────────────
        # Preencher colunas faltantes com NaN
        for col in df_gold.columns:
            if col not in df_novas.columns:
                df_novas[col] = np.nan

        df_gold_atualizado = pd.concat(
            [df_gold, df_novas[df_gold.columns]],
            ignore_index=True
        ).sort_values('data').reset_index(drop=True)

        # Aplicar corte temporal
        if data_corte:
            df_gold_atualizado = df_gold_atualizado[
                df_gold_atualizado['data'] <= pd.Timestamp(data_corte)
            ]

        # ── 8. Salvar Gold atualizado ─────────────────────────
        GOLD_PATH.parent.mkdir(parents=True, exist_ok=True)
        df_gold_atualizado.to_parquet(GOLD_PATH, index=False)

        n_novos = len(df_gold_atualizado) - len(df_gold)
        logger.info(f"Gold atualizado: {len(df_gold_atualizado)} registros (+{n_novos} novos)")
        logger.info(f"Período: {df_gold_atualizado['data'].min().date()} → {df_gold_atualizado['data'].max().date()}")

        return {
            'status':      'ok',
            'n_registros': len(df_gold_atualizado),
            'n_novos':     n_novos,
            'ultima_data': str(df_gold_atualizado['data'].max().date())
        }

    except Exception as e:
        logger.error(f"Erro ao atualizar Gold: {e}")
        return {'status': 'erro', 'motivo': str(e)}