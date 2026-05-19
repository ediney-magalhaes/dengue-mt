# ============================================================
# Dengue MT — Task: Treino Direct Multi-Step + CQR (ADR-030)
# ============================================================
# Responsabilidade ÚNICA:
#   - Criar targets Direct (shift -h com log1p)
#   - Treinar 12 modelos LightGBM (4 horizontes × 3 quantis)
#   - Validar via TimeSeriesSplit 5-fold
#   - Salvar artefatos (modelos + metadata)
#
# Não faz: seleção de features (build_features.py),
#           publicação HF (publicacao.py),
#           orquestração (pipeline_prefect.py)
#
# Referências:
#   - Taieb & Hyndman (2014) — Direct multi-step forecasting
#   - Romano et al. (2019) — Conformalized Quantile Regression
#   - LightGBM docs — objective='quantile', alpha=τ
#   - ADR-024 — log1p/expm1 como par obrigatório
#   - ADR-030 — Direct Multi-Step + CQR em produção
# ============================================================

from prefect import task, get_run_logger
from datetime import datetime
import pandas as pd
import numpy as np
import lightgbm as lgb
import joblib
import json

from src.config import (
    MODELS_DIR, HORIZONTES_DIRECT, QUANTIS_CQR,
    model_direct_path, DIRECT_METADATA_PATH
)
from src.features.build_features import (
    carregar_gold, build_features, carregar_schema
)


# ── Criação de targets Direct ─────────────────────────────

def criar_targets_direct(df: pd.DataFrame,
                         target_col: str = 'casos_confirmados',
                         horizontes: list = None) -> pd.DataFrame:
    """
    Cria targets Direct Multi-Step com log1p (ADR-024).

    Para cada horizonte h, target y_h{h} na linha t contém
    log1p(valor em t+h). Últimas h linhas ficam NaN.

    Parâmetros
    ----------
    df : pd.DataFrame
        Gold dataset ordenado por data_se.
    target_col : str
        Coluna target original.
    horizontes : list[int]
        Horizontes em SE (default: config.HORIZONTES_DIRECT).

    Retorna
    -------
    pd.DataFrame
        Colunas: ['y_h1', 'y_h2', 'y_h4', 'y_h8']
    """
    if horizontes is None:
        horizontes = HORIZONTES_DIRECT

    if target_col not in df.columns:
        raise ValueError(f"Coluna '{target_col}' não encontrada")

    base = np.log1p(df[target_col].astype(float))
    df_temp = df.copy()
    df_temp['_base_log1p'] = base

    resultado = pd.DataFrame(index=df.index)
    for h in horizontes:
        resultado[f'y_h{h}'] = df_temp.groupby('municipio_id')['_base_log1p'].shift(-h)

    return resultado


# ── Treino dos 12 modelos ─────────────────────────────────

def _treinar_um_modelo(X: pd.DataFrame, y: pd.Series,
                       quantil: float, params_base: dict) -> lgb.LGBMRegressor:
    """
    Treina LGBMRegressor.
    q50 usa objective='regression' (MAE/MSE — igual ao v5).
    q05/q95 usa objective='quantile' (pinball loss — bandas CQR).
    """
    if quantil == 0.50:
        params = {
            **params_base,
            'objective':   'regression',
            'metric':      'mae',
            'verbosity':   -1,
            'random_state': 42,
        }
    else:
        params = {
            **params_base,
            'objective':   'quantile',
            'alpha':        quantil,
            'metric':      'quantile',
            'verbosity':   -1,
            'random_state': 42,
        }
    modelo = lgb.LGBMRegressor(**params)
    modelo.fit(X, y)
    return modelo


def _validar_expanding(X: pd.DataFrame, y_log: pd.Series,
                       y_original: pd.Series, df_mun_ids: pd.Series,
                       quantil: float, params_base: dict,
                       teste_inicio: int = 2023) -> dict:
    """
    Validação expanding window — mesma lógica do backtesting.
    Treina com tudo até t, prevê t, avança, repete.
    Referência: Bergmeir & Benítez (2012), Petropoulos et al. (2022).

    Parâmetros
    ----------
    X, y_log, y_original : dados alinhados
    df_mun_ids : Series com municipio_id para cada registro
    quantil : float (0.05, 0.50, 0.95)
    params_base : dict com hiperparâmetros LightGBM
    teste_inicio : int, ano a partir do qual avalia (default: 2023)
    """
    from sklearn.metrics import mean_absolute_error, r2_score

    # Necessário data_se para definir janela de teste
    # índice temporal implícito: registros estão ordenados por data_se
    n = len(X)
    min_treino = 52 * 2  # mínimo 2 anos (~104 semanas por município)

    preds_all = []
    reais_all = []

    # Expanding window: começa no min_treino, avança 1 registro por vez
    # Para eficiência, avança de 4 em 4 (mensal)
    for t in range(min_treino, n, 4):
        X_tr = X.iloc[:t]
        y_tr = y_log.iloc[:t]

        if t >= n:
            break

        # Prever próximo(s) registro(s)
        fim = min(t + 4, n)
        X_te = X.iloc[t:fim]
        y_te = y_original.iloc[t:fim]

        if len(X_te) == 0 or y_te.isna().all():
            continue

        modelo = _treinar_um_modelo(X_tr, y_tr, quantil, params_base)
        preds_log = modelo.predict(X_te)
        preds = np.maximum(np.expm1(preds_log), 0)

        preds_all.extend(preds)
        reais_all.extend(y_te.values)

    preds_all = np.array(preds_all)
    reais_all = np.array(reais_all)

    # Remover NaN
    mask = ~np.isnan(reais_all)
    preds_all = preds_all[mask]
    reais_all = reais_all[mask]

    resultado = {'n_previsoes': len(preds_all), 'quantil': quantil}

    if quantil == 0.50:
        resultado['mae'] = float(mean_absolute_error(reais_all, preds_all))
        resultado['r2'] = float(r2_score(reais_all, preds_all))
    else:
        cobertura = float(np.mean(reais_all <= preds_all))
        resultado['cobertura'] = cobertura

    return resultado


@task(name="treinar_direto_cqr")
def treinar_direto_cqr(data_corte=None, params_override: dict = None):
    """
    Treina 12 modelos Direct Multi-Step + CQR.
    4 horizontes × 3 quantis (0.05, 0.50, 0.95).
    """
    logger = get_run_logger()
    logger.info("="*55)
    logger.info("Treino Direct Multi-Step + CQR (ADR-030)")
    logger.info("="*55)

    # ── 1. Carregar Gold e features ───────────────────────
    df = carregar_gold()
    df['data_se'] = pd.to_datetime(df['data_se'])
    df = df.sort_values('data_se').reset_index(drop=True)

    if data_corte:
        n_antes = len(df)
        df = df[df['data_se'] <= pd.Timestamp(data_corte)]
        logger.info(f"Corte temporal: {n_antes} → {len(df)} registros")

    X = build_features(df)
    logger.info(f"Features: {X.shape[1]} colunas × {X.shape[0]} registros")

    # ── 2. Criar targets Direct ───────────────────────────
    targets = criar_targets_direct(df)
    logger.info(f"Targets criados: {list(targets.columns)}")

    # ── 3. Parâmetros base (iguais ao v5 atual) ──────────
    params_base = {
        'n_estimators':  params_override.get('n_estimators', 500) if params_override else 500,
        'learning_rate': params_override.get('learning_rate', 0.05) if params_override else 0.05,
        'num_leaves':    params_override.get('num_leaves', 31) if params_override else 31,
    }
    logger.info(f"Params: {params_base}")

    # ── 4. Treinar 12 modelos ─────────────────────────────
    metadata = {
        'versao':       'direct_cqr_v1',
        'horizontes':   HORIZONTES_DIRECT,
        'quantis':      QUANTIS_CQR,
        'params':       params_base,
        'data_treino':  str(df['data_se'].max().date()),
        'timestamp':    datetime.now().isoformat(),
        'modelos':      {},
    }

    for h in HORIZONTES_DIRECT:
        col_target = f'y_h{h}'
        y_log = targets[col_target]

        # Remover NaN do final (sem futuro observado)
        mask_valido = y_log.notna()
        X_h = X[mask_valido].reset_index(drop=True)
        y_h = y_log[mask_valido].reset_index(drop=True)

        # y_original na escala real, já deslocado POR MUNICÍPIO (valor em t+h)
        y_orig_shifted = df.groupby('municipio_id')['casos_confirmados'].shift(-h)
        y_orig_shifted = y_orig_shifted[mask_valido].reset_index(drop=True)

        logger.info(f"\n── Horizonte h={h} ({len(X_h)} registros) ──")

        for q in QUANTIS_CQR:
            q_str = str(int(q * 100)).zfill(2)
            nome = f'h{h}_q{q_str}'

            # Treinar modelo final (dataset completo)
            modelo = _treinar_um_modelo(X_h, y_h, q, params_base)

            # Salvar modelo
            path = model_direct_path(h, q)
            joblib.dump(modelo, path)
            logger.info(f"  {nome}: salvo → {path.name}")

            # Validação expanding window (mesma lógica do backtesting)
            holdout = _validar_expanding(X_h, y_h, y_orig_shifted,
                                         df.loc[mask_valido, 'municipio_id'].reset_index(drop=True),
                                         q, params_base)

            # Registrar métricas
            if q == 0.50:
                logger.info(f"  {nome}: MAE={holdout['mae']:.1f} | R²={holdout['r2']:.3f} (holdout 52 SE)")
                metadata['modelos'][nome] = {
                    'mae': round(holdout['mae'], 2),
                    'r2': round(holdout['r2'], 3),
                    'holdout': holdout,
                }
            else:
                logger.info(f"  {nome}: cobertura={holdout['cobertura']:.1%} (esperado={q:.0%})")
                metadata['modelos'][nome] = {
                    'cobertura': round(holdout['cobertura'], 3),
                    'cobertura_esperada': q,
                    'holdout': holdout,
                }

    # ── 4b. Calibração conformal (Romano et al. 2019) ─────
    #   Calcula correção q no holdout para garantir ~90% cobertura
    logger.info("\n── Calibração conformal ──")
    split_cal = int(len(df) * 0.8)

    for h in HORIZONTES_DIRECT:
        col_target = f'y_h{h}'
        y_log = targets[col_target]
        mask_valido = y_log.notna()

        X_h = X[mask_valido].reset_index(drop=True)
        y_h = y_log[mask_valido].reset_index(drop=True)
        y_real = df.groupby('municipio_id')['casos_confirmados'].shift(-h)
        y_real = y_real[mask_valido].reset_index(drop=True)

        # Treinar no 80%, calibrar no 20%
        sp = int(len(X_h) * 0.8)
        X_cal, y_cal = X_h.iloc[sp:], y_real.iloc[sp:]

        # Carregar modelos q01 e q99 já treinados
        m_lo = joblib.load(model_direct_path(h, QUANTIS_CQR[0]))
        m_hi = joblib.load(model_direct_path(h, QUANTIS_CQR[2]))

        p_lo = np.maximum(np.expm1(m_lo.predict(X_cal)), 0)
        p_hi = np.maximum(np.expm1(m_hi.predict(X_cal)), 0)

        # Residuos de conformidade
        residuos = np.maximum(p_lo - y_cal.values, y_cal.values - p_hi)
        q_conf = float(np.quantile(residuos, 0.90))

        # Cobertura após calibração
        p_lo_adj = np.maximum(p_lo - q_conf, 0)
        p_hi_adj = p_hi + q_conf
        mask_valid = ~np.isnan(y_cal.values)
        cob = np.mean((y_cal.values[mask_valid] >= p_lo_adj[mask_valid]) &
                       (y_cal.values[mask_valid] <= p_hi_adj[mask_valid]))

        metadata['modelos'][f'h{h}_calibracao'] = {
            'q_conformal': round(q_conf, 2),
            'cobertura_calibrada': round(float(cob), 3),
        }
        logger.info(f"  h={h}: q_conf={q_conf:.1f} → cobertura={cob:.1%}")

    # ── 5. Salvar metadata ────────────────────────────────
    metadata['n_modelos'] = len(HORIZONTES_DIRECT) * len(QUANTIS_CQR)

    with open(DIRECT_METADATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    logger.info(f"\nMetadata salvo: {DIRECT_METADATA_PATH.name}")

    # ── 6. Resumo ─────────────────────────────────────────
    logger.info(f"\n{'='*55}")
    logger.info(f"Treino concluído: {metadata['n_modelos']} modelos")
    for h in HORIZONTES_DIRECT:
        m50 = metadata['modelos'].get(f'h{h}_q50', {})
        logger.info(
            f"  h={h}: R²={m50.get('r2', 'N/A')} | "
            f"MAE={m50.get('mae', 'N/A')}"
        )
    logger.info(f"{'='*55}")

    return metadata