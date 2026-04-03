# ============================================================
# Dengue MT — Módulo Canônico de Features
# ============================================================
# FONTE ÚNICA DE VERDADE para construção de features
# Usado em: treino, retreino, API serving, validação
#
# Regra fundamental: qualquer feature nova entra AQUI primeiro
# e automaticamente atualiza o schema e a API.
#
# Referência: Feature Store pattern — MLOps best practices
# ============================================================

import json
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

logger = logging.getLogger('dengue-mt.features')

# ============================================================
# Paths
# ============================================================
ROOT_DIR   = Path(__file__).parent.parent.parent
MODELS_DIR = ROOT_DIR / 'models'
DATA_DIR   = ROOT_DIR / 'data'

SCHEMA_PATH = MODELS_DIR / 'lgbm_v4_feature_schema.json'

# ============================================================
# Colunas que não são features (target + identificadores)
# ============================================================
DROP_COLS = ['data', 'casos', 'casos_nowcast', 'municipio_id',
             'fator_nowcasting', 'casos_por_100k', 'casos_nowcast_por_100k']


def carregar_schema() -> dict:
    """Carrega o feature schema — fonte de verdade."""
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Feature schema não encontrado: {SCHEMA_PATH}")
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def get_feature_names() -> list:
    """Retorna lista canônica de features do modelo."""
    return carregar_schema()['feature_names']


def build_features(df: pd.DataFrame,
                   data_corte: datetime = None,
                   validar: bool = True) -> pd.DataFrame:
    """
    Constrói o dataset de features a partir do Gold.

    Parâmetros:
    -----------
    df          : DataFrame Gold com todas as colunas
    data_corte  : se informado, filtra dados até essa data (anti-leakage)
    validar     : se True, valida compatibilidade com o schema

    Retorna:
    --------
    X : DataFrame com exatamente as features do schema, na ordem correta
    """
    df = df.copy()

    # Garantir coluna de data
    if 'data' in df.columns:
        df['data'] = pd.to_datetime(df['data'])
        df = df.sort_values('data').reset_index(drop=True)

    # Aplicar corte temporal anti-leakage
    if data_corte is not None:
        n_antes = len(df)
        df = df[df['data'] <= pd.Timestamp(data_corte)]
        n_depois = len(df)
        logger.info(f"build_features: corte {data_corte} — {n_antes} → {n_depois} registros")

    # Carregar schema canônico
    schema        = carregar_schema()
    feature_names = schema['feature_names']

    if validar:
        _validar_features(df, feature_names)

    # Selecionar e ordenar features canonicamente
    X = df[feature_names].copy()

    logger.info(f"build_features: {X.shape[0]} registros × {X.shape[1]} features")
    return X


def build_features_serving(df: pd.DataFrame,
                           n_linhas: int = 1) -> pd.DataFrame:
    """
    Constrói features para serving (API) — mesma lógica do treino.

    Parâmetros:
    -----------
    df       : DataFrame Gold completo
    n_linhas : número de linhas mais recentes a usar (padrão: 1)

    Retorna:
    --------
    X : DataFrame com features canônicas das últimas n_linhas
    """
    df = df.copy()
    df['data'] = pd.to_datetime(df['data'])
    df = df.sort_values('data').dropna().reset_index(drop=True)

    # Usar apenas as últimas n_linhas
    df_serving = df.tail(n_linhas)

    schema        = carregar_schema()
    feature_names = schema['feature_names']

    # Verificar features faltando
    faltando = [f for f in feature_names if f not in df_serving.columns]
    if faltando:
        logger.error(f"build_features_serving: features faltando: {faltando}")
        raise ValueError(f"Features faltando no serving: {faltando}")

    X = df_serving[feature_names].copy()
    logger.info(f"build_features_serving: {len(X)} registro(s) × {len(feature_names)} features")
    return X


def get_target(df: pd.DataFrame,
               data_corte: datetime = None) -> pd.Series:
    """
    Retorna a série target (casos) alinhada com build_features().
    Garante que X e y usam exatamente os mesmos registros.
    """
    df = df.copy()
    df['data'] = pd.to_datetime(df['data'])
    df = df.sort_values('data').reset_index(drop=True)

    if data_corte is not None:
        df = df[df['data'] <= pd.Timestamp(data_corte)]

    return df['casos'].reset_index(drop=True)


def _validar_features(df: pd.DataFrame, feature_names: list):
    """Valida compatibilidade do DataFrame com o schema canônico."""
    faltando = [f for f in feature_names if f not in df.columns]
    extras   = [c for c in df.columns
                if c not in feature_names and c not in DROP_COLS]

    if faltando:
        logger.error(f"FEATURE_DRIFT: features faltando: {faltando}")
        raise ValueError(f"Feature drift detectado — features faltando: {faltando}")

    if extras:
        logger.warning(f"Features extras ignoradas: {extras}")

    logger.info(f"Validação OK — {len(feature_names)} features compatíveis com schema")


def atualizar_schema(modelo, df_treino: pd.DataFrame,
                     metricas: dict = None):
    """
    Atualiza o feature schema após retreino.
    Deve ser chamado sempre que o modelo for promovido.
    """
    import os
    from src.config import PIPELINE_VERSION, DATASET_VERSION

    schema = {
        'feature_names':      modelo.feature_name_,
        'n_features':         len(modelo.feature_name_),
        'pipeline_version':   PIPELINE_VERSION,
        'commit_sha':         os.environ.get('GITHUB_SHA', 'local')[:8],
        'dataset_version':    DATASET_VERSION,
        'drop_cols':          DROP_COLS,
        'data_treino':        str(df_treino['data'].max().date()) if 'data' in df_treino.columns else 'N/A',
        'n_registros_treino': len(df_treino),
        'timestamp':          datetime.now().isoformat(),
        'r2':                 metricas.get('r2', None) if metricas else None,
        'mae':                metricas.get('mae', None) if metricas else None,
    }

    with open(SCHEMA_PATH, 'w', encoding='utf-8') as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)

    logger.info(f"Schema atualizado: {len(modelo.feature_name_)} features")
    return schema