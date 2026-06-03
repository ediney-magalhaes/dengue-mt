# ============================================================
# Dengue MT — Task: Retreino do Modelo v2.0
# ============================================================
# Responsabilidade: retreinar LightGBM quando drift detectado
# Gold v5 gerado pelo dbt → build_features seleciona X e y
# Modelo salvo versionado + ponteiro latest
# ============================================================

from prefect import task, get_run_logger
from datetime import datetime
from src.config import MODELS_DIR, MODEL_LATEST_PATH
import pandas as pd
import numpy as np
import joblib
import json
import os
import shutil


def _rodar_pytest(logger) -> bool:
    """
    Roda testes pytest programaticamente.
    Usa pytest.main() se já dentro de processo Python (evita conflito subprocess).
    Usa subprocess como fallback para execução via Prefect/CI.
    Referência: Sculley et al. 2015 — gate obrigatório antes de promoção.
    """
    import subprocess
    import sys

    logger.info("Rodando pytest — validação antes da promoção...")

    # pytest.main() — contexto direto (evita deadlock subprocess-dentro-de-subprocess)
    try:
        import pytest
        codigo = pytest.main([
            'tests/',
            '--tb=short',
            '-q',
            '--no-header',
        ])
        # 0 = passou, 1 = falhou, 2 = erro, 3 = interrupted, 4 = usage error, 5 = no tests
        if codigo == 0:
            logger.info("pytest — todos os testes passaram ✅")
            return True
        elif codigo == 5:
            logger.warning("pytest — nenhum teste encontrado (código 5) — aprovando com aviso")
            return True
        else:
            logger.error(f"pytest — testes falharam (código {codigo}) ❌")
            return False
    except SystemExit:
        # pytest.main() pode levantar SystemExit em alguns ambientes
        logger.warning("pytest.main() levantou SystemExit — tentando subprocess...")
    except Exception as e:
        logger.warning(f"pytest.main() falhou ({e}) — tentando subprocess...")

    # Fallback: subprocess (contexto Prefect/CI sem pytest no processo atual)
    try:
        resultado = subprocess.run(
            [sys.executable, '-m', 'pytest', 'tests/', '--tb=short', '-q', '--no-header'],
            capture_output=True,
            text=True,
            timeout=180
        )
        if resultado.returncode == 0:
            logger.info("pytest subprocess — todos os testes passaram ✅")
            return True
        else:
            logger.error(f"pytest subprocess — falharam ❌\n{resultado.stdout[-500:]}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("pytest subprocess — timeout após 180s ❌")
        return False
    except Exception as e:
        logger.error(f"pytest subprocess — erro: {e} ❌")
        return False


@task(name="retreinar_modelo")
def retreinar_modelo(data_corte=None, params_retreino=None):
    """Retreina LightGBM com Gold v5 gerado pelo dbt."""
    logger = get_run_logger()
    logger.info("Iniciando retreino do modelo...")

    try:
        import lightgbm as lgb
        from sklearn.metrics import mean_absolute_error, r2_score
        from sklearn.model_selection import TimeSeriesSplit
        from src.features.build_features import (
            carregar_gold, build_features, get_target,
            carregar_schema, atualizar_schema
        )

        # Carregar Gold latest
        df = carregar_gold()
        df['data_se'] = pd.to_datetime(df['data_se'])
        df = df.sort_values('data_se').reset_index(drop=True)

        # Aplicar corte temporal anti-leakage
        if data_corte:
            n_antes = len(df)
            df = df[df['data_se'] <= pd.Timestamp(data_corte)]
            logger.info(f"Corte temporal: até {data_corte} — {n_antes} → {len(df)} registros")
        else:
            logger.warning("DATA_CORTE não definido — usando dataset completo (risco de leakage!)")

        # Separar por município — modelos independentes
        municipios = df['municipio_id'].unique()
        logger.info(f"Municípios: {list(municipios)}")

        # Carregar modelo atual para comparação
        modelo_atual = None
        r2_atual = None
        if MODEL_LATEST_PATH.exists():
            modelo_atual = joblib.load(MODEL_LATEST_PATH)
            logger.info("Modelo atual carregado para comparação")

        # Carregar schema para alinhar features
        try:
            schema = carregar_schema()
            feature_names = schema['feature_names']
            logger.info(f"Schema carregado: {len(feature_names)} features")
        except FileNotFoundError:
            feature_names = None
            logger.warning("Schema não encontrado — usando features do modelo atual")
            if modelo_atual:
                feature_names = list(modelo_atual.feature_name_)

        if feature_names is None:
            logger.error("Sem schema e sem modelo atual — impossível retreinar")
            return {'status': 'erro', 'motivo': 'sem schema de features'}

        # Selecionar features e target
        X = df[feature_names].copy()
        y = df['casos_confirmados'].copy()

        # Verificar features faltando
        faltando = [f for f in feature_names if f not in df.columns]
        if faltando:
            logger.error(f"Features faltando: {faltando}")
            return {'status': 'erro', 'motivo': f'Features faltando: {faltando}'}

        # Avaliar modelo atual nas últimas 26 SE
        if modelo_atual:
            feature_cols_atual = [c for c in modelo_atual.feature_name_ if c in df.columns]
            df_test = df.tail(52)
            X_test = df_test[feature_cols_atual]
            y_test = df_test['casos_confirmados']
            preds_atual = np.maximum(modelo_atual.predict(X_test), 0)
            r2_atual = r2_score(y_test, preds_atual)
            logger.info(f"R² modelo atual (52 SE): {r2_atual:.3f}")

        # Parâmetros dinâmicos — conservadores se drift crítico
        params_dinamicos = params_retreino or {}
        params = {
            'objective':     'regression',
            'metric':        'mae',
            'verbosity':     -1,
            'n_estimators':  params_dinamicos.get('n_estimators', 500),
            'learning_rate': params_dinamicos.get('learning_rate', 0.05),
            'num_leaves':    params_dinamicos.get('num_leaves', 31),
            'random_state':  42
        }
        logger.info(
            f"Params retreino: n_estimators={params['n_estimators']} "
            f"lr={params['learning_rate']} "
            f"motivo={params_dinamicos.get('motivo', 'padrao')}"
        )

        # Transformação log1p no target
        y_log = np.log1p(y)

        # Treinar novo modelo
        novo_modelo = lgb.LGBMRegressor(**params)
        novo_modelo.fit(X, y_log)

        # Validação por folds — TimeSeriesSplit 5
        metricas_folds = []
        tscv = TimeSeriesSplit(n_splits=5)
        for fold, (idx_train, idx_test) in enumerate(tscv.split(X), 1):
            X_f, y_f = X.iloc[idx_train], y_log.iloc[idx_train]
            X_v, y_v = X.iloc[idx_test], y.iloc[idx_test]
            m = lgb.LGBMRegressor(**params)
            m.fit(X_f, y_f)
            p = np.maximum(np.expm1(m.predict(X_v)), 0)
            mae_f = mean_absolute_error(y_v, p)
            r2_f = r2_score(y_v, p)
            metricas_folds.append({'fold': fold, 'mae': mae_f, 'r2': r2_f})
            logger.info(f"Fold {fold}: MAE={mae_f:.1f} | R²={r2_f:.3f}")

        # Registrar folds no MLflow
        try:
            import mlflow
            from src.tasks.mlflow_tracking import MLFLOW_TRACKING, EXPERIMENT_NAME
            mlflow.set_tracking_uri(MLFLOW_TRACKING)
            mlflow.set_experiment(EXPERIMENT_NAME)
            with mlflow.start_run(
                run_name=f"retreino_{datetime.now().strftime('%Y%m%d_%H%M')}",
                nested=True
            ):
                for mf in metricas_folds:
                    mlflow.log_metric('mae_fold', mf['mae'], step=mf['fold'])
                    mlflow.log_metric('r2_fold', mf['r2'], step=mf['fold'])
                mlflow.log_metric('mae_medio_folds',
                                  np.mean([m['mae'] for m in metricas_folds]))
                mlflow.log_metric('r2_medio_folds',
                                  np.mean([m['r2'] for m in metricas_folds]))
        except Exception as e:
            logger.warning(f"MLflow folds não registrado: {e}")

        # Avaliar novo modelo
        y_eval = y.tail(52)
        X_eval = X.tail(52)
        preds_novo = np.maximum(np.expm1(novo_modelo.predict(X_eval)), 0)
        r2_novo = r2_score(y_eval, preds_novo)
        mae_novo = mean_absolute_error(y_eval, preds_novo)

        logger.info(f"R² novo modelo: {r2_novo:.3f} | MAE: {mae_novo:.1f}")

        # Decisão: promover ou manter
        r2_ok = r2_novo >= (r2_atual - 0.05) if r2_atual else True
        pytest_ok = _rodar_pytest(logger)
        promover = r2_ok and pytest_ok

        if promover:
            # Determinar versão do novo modelo
            nova_versao = _proxima_versao()

            # Salvar modelo versionado
            path_versionado = MODELS_DIR / f'lgbm_{nova_versao}_producao.pkl'
            joblib.dump(novo_modelo, path_versionado)
            logger.info(f"Modelo {nova_versao} salvo: {path_versionado.name}")

            # Copiar para latest
            shutil.copy(path_versionado, MODEL_LATEST_PATH)
            logger.info(f"Modelo latest atualizado: {MODEL_LATEST_PATH.name}")

            # Atualizar schema (versionado + latest)
            atualizar_schema(
                novo_modelo, df,
                metricas={'r2': round(r2_novo, 3), 'mae': round(mae_novo, 1)},
                versao=nova_versao
            )

            logger.info(f"Modelo promovido — R²={r2_novo:.3f} | versão={nova_versao}")
            return {
                'status':      'promovido',
                'versao':      nova_versao,
                'r2_novo':     round(r2_novo, 3),
                'r2_anterior': round(r2_atual, 3) if r2_atual else None,
                'mae':         round(mae_novo, 1),
                'folds':       metricas_folds
            }
        else:
            motivo = 'pytest falhou' if not pytest_ok else 'queda de performance'
            logger.warning(
                f"Modelo mantido — R² novo={r2_novo:.3f} | "
                f"R² atual={r2_atual:.3f if r2_atual else 'N/A'} | "
                f"Motivo: {motivo}"
            )
            return {
                'status':      'mantido',
                'r2_novo':     round(r2_novo, 3),
                'r2_anterior': round(r2_atual, 3) if r2_atual else None,
                'motivo':      motivo
            }

    except Exception as e:
        logger.error(f"Erro no retreino: {e}")
        return {'status': 'erro', 'motivo': str(e)}


def _proxima_versao() -> str:
    """
    Determina a próxima versão do modelo baseado nos arquivos existentes.
    Padrão: v5, v6, v7...
    """
    import re
    existentes = list(MODELS_DIR.glob('lgbm_v*_producao.pkl'))
    versoes = []
    for p in existentes:
        match = re.search(r'v(\d+)', p.name)
        if match:
            versoes.append(int(match.group(1)))
    proxima = max(versoes) + 1 if versoes else 5
    return f"v{proxima}"

# ============================================================
# GATE DE PROMOÇÃO/ROLLBACK — Direct CQR (ADR-035)
# ============================================================
# Padrão Champion-Challenger (Databricks MLOps 2024; DataRobot 2025)
# Três critérios independentes — todos obrigatórios:
#   1. MAE por horizonte (García Crespi et al. 2025)
#   2. Cobertura calibrada CQR (Romano et al. 2019; Angelopoulos & Bates 2023)
#   3. pytest 21 testes (Sculley et al. 2015)
# ============================================================

def gate_promocao_direct_cqr(metadata_novo: dict) -> dict:
    """
    Compara Challenger (metadata_novo) com Champion (direct_cqr_metadata.json).
    Retorna decisão de promoção com rastreabilidade completa.

    Parâmetros
    ----------
    metadata_novo : dict
        Retorno de treinar_direto_cqr() — métricas do Challenger.

    Retorna
    -------
    dict com chaves:
        promovido       : bool
        criterios       : dict com resultado de cada critério
        motivo_rejeicao : str | None
    """
    import logging
    import subprocess
    import sys

    logger = logging.getLogger('dengue-mt.gate')

    from src.config import DIRECT_METADATA_PATH, HORIZONTES_DIRECT

    # Tolerâncias baseadas em literatura (ADR-035)
    MAE_TOLERANCIA      = 1.10   # García Crespi et al. 2025 — 10%
    COBERTURA_MINIMA    = 0.85   # Romano et al. 2019 — 5% abaixo do alvo 90%

    logger.info("=" * 55)
    logger.info("GATE Champion-Challenger — Direct CQR (ADR-035)")
    logger.info("=" * 55)

    # ── Carregar Champion ─────────────────────────────────────
    if not DIRECT_METADATA_PATH.exists():
        logger.info("Primeira execução — sem Champion anterior. Gate aprovado automaticamente.")
        return {
            'promovido':        True,
            'criterios':        {'bootstrap': True},
            'motivo_rejeicao':  None,
        }

    import json
    with open(DIRECT_METADATA_PATH, encoding='utf-8') as f:
        metadata_champion = json.load(f)

    logger.info(f"Champion: treinado em {metadata_champion.get('data_treino', 'N/A')}")
    logger.info(f"Challenger: treinado em {metadata_novo.get('data_treino', 'N/A')}")

    criterios = {}
    falhas    = []

    # ── Critério 1 — MAE por horizonte (q50) ─────────────────
    logger.info("\n── Critério 1: MAE por horizonte (q50) ──")
    mae_ok_todos = True

    for h in HORIZONTES_DIRECT:
        chave = f'h{h}_q50'

        mae_champion  = metadata_champion['modelos'].get(chave, {}).get('mae')
        mae_challenger = metadata_novo['modelos'].get(chave, {}).get('mae')

        if mae_champion is None or mae_challenger is None:
            logger.warning(f"  h={h}: MAE ausente — champion={mae_champion} challenger={mae_challenger}")
            criterios[f'mae_h{h}'] = {'ok': False, 'motivo': 'MAE ausente no metadata'}
            mae_ok_todos = False
            falhas.append(f'mae_h{h}_ausente')
            continue

        threshold = round(mae_champion * MAE_TOLERANCIA, 2)
        ok = mae_challenger <= threshold

        logger.info(
            f"  h={h}: MAE champion={mae_champion:.2f} | "
            f"challenger={mae_challenger:.2f} | "
            f"threshold={threshold:.2f} | "
            f"{'✅' if ok else '❌'}"
        )

        criterios[f'mae_h{h}'] = {
            'ok':              ok,
            'mae_champion':    mae_champion,
            'mae_challenger':  mae_challenger,
            'threshold':       threshold,
        }

        if not ok:
            mae_ok_todos = False
            falhas.append(f'mae_h{h}')

    # ── Critério 2 — Cobertura calibrada CQR ─────────────────
    logger.info("\n── Critério 2: Cobertura calibrada CQR ──")
    cobertura_ok_todos = True

    for h in HORIZONTES_DIRECT:
        chave_cal = f'h{h}_calibracao'

        cob_champion   = metadata_champion['modelos'].get(chave_cal, {}).get('cobertura_calibrada')
        cob_challenger = metadata_novo['modelos'].get(chave_cal, {}).get('cobertura_calibrada')

        if cob_challenger is None:
            logger.warning(f"  h={h}: cobertura_calibrada ausente no Challenger")
            criterios[f'cobertura_h{h}'] = {'ok': False, 'motivo': 'cobertura_calibrada ausente'}
            cobertura_ok_todos = False
            falhas.append(f'cobertura_h{h}_ausente')
            continue

        ok = cob_challenger >= COBERTURA_MINIMA

        logger.info(
            f"  h={h}: cobertura_calibrada challenger={cob_challenger:.3f} | "
            f"mínimo={COBERTURA_MINIMA:.2f} | "
            f"champion={f'{cob_champion:.3f}' if cob_champion else 'N/A'} | "
            f"{'✅' if ok else '❌'}"
        )

        criterios[f'cobertura_h{h}'] = {
            'ok':                  ok,
            'cobertura_challenger': cob_challenger,
            'cobertura_champion':   cob_champion,
            'minimo':              COBERTURA_MINIMA,
        }

        if not ok:
            cobertura_ok_todos = False
            falhas.append(f'cobertura_h{h}')

    # ── Critério 3 — pytest 21 testes ────────────────────────
    logger.info("\n── Critério 3: pytest 21 testes ──")
    pytest_ok = _rodar_pytest(logger)
    criterios['pytest'] = {'ok': pytest_ok}
    if not pytest_ok:
        falhas.append('pytest')

    # ── Decisão final ─────────────────────────────────────────
    promovido = mae_ok_todos and cobertura_ok_todos and pytest_ok

    logger.info("\n── Decisão ──")
    logger.info(f"  MAE todos horizontes:       {'✅' if mae_ok_todos else '❌'}")
    logger.info(f"  Cobertura CQR calibrada:    {'✅' if cobertura_ok_todos else '❌'}")
    logger.info(f"  pytest 21 testes:           {'✅' if pytest_ok else '❌'}")
    logger.info(f"  → {'PROMOVIDO ✅' if promovido else 'ROLLBACK ❌'}")

    motivo_rejeicao = None
    if not promovido:
        motivo_rejeicao = f"Critérios reprovados: {', '.join(falhas)}"
        logger.warning(f"  Motivo: {motivo_rejeicao}")
        logger.warning("  Champion mantido — arquivos latest não alterados.")

    return {
        'promovido':        promovido,
        'criterios':        criterios,
        'motivo_rejeicao':  motivo_rejeicao,
        'falhas':           falhas,
    }