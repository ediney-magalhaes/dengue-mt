# ============================================================
# Dengue MT — Módulo Canônico de Features v2.0
# ============================================================
# Responsabilidade: carregar schema e selecionar features do Gold
# O dbt gera o Gold completo — este módulo apenas seleciona X e y
# Usado em: retreino, drift, serving, validação
# ============================================================

import json
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

logger = logging.getLogger('dengue-mt.features')

from src.config import (
    SCHEMA_LATEST_PATH, GOLD_LATEST_PATH,
    MODELS_DIR, DATA_DIR
)

# Colunas que nunca são features — sempre removidas
DROP_COLS = ['data_se', 'casos_confirmados', 'casos_estimados',
             'incidencia_100k', 'municipio_id']


def carregar_schema(schema_path: Path = None) -> dict:
    """Carrega feature schema — latest por padrão."""
    path = schema_path or SCHEMA_LATEST_PATH
    if not path.exists():
        raise FileNotFoundError(f"Feature schema não encontrado: {path}")
    with open(path) as f:
        return json.load(f)


def get_feature_names(schema_path: Path = None) -> list:
    """Retorna lista de features do schema."""
    return carregar_schema(schema_path)['feature_names']


def carregar_gold(gold_path: Path = None) -> pd.DataFrame:
    """Carrega Gold dataset — latest por padrão."""
    path = gold_path or GOLD_LATEST_PATH
    if not path.exists():
        raise FileNotFoundError(f"Gold dataset não encontrado: {path}")
    df = pd.read_parquet(path)
    logger.info(f"Gold carregado: {df.shape[0]} registros × {df.shape[1]} colunas")
    return df


def build_features(df: pd.DataFrame,
                   schema_path: Path = None,
                   data_corte: datetime = None) -> pd.DataFrame:
    """
    Seleciona features do Gold alinhadas com o schema.
    O Gold já tem todas as features calculadas pelo dbt.
    """
    df = df.copy()
    if 'data_se' in df.columns:
        df['data_se'] = pd.to_datetime(df['data_se'])
        df = df.sort_values('data_se').reset_index(drop=True)

    if data_corte is not None:
        n_antes = len(df)
        df = df[df['data_se'] <= pd.Timestamp(data_corte)]
        logger.info(f"build_features: corte {data_corte} — {n_antes} → {len(df)} registros")

    schema = carregar_schema(schema_path)
    feature_names = schema['feature_names']

    # Validar compatibilidade
    faltando = [f for f in feature_names if f not in df.columns]
    if faltando:
        raise ValueError(f"Feature drift detectado — features faltando: {faltando}")

    extras = [c for c in df.columns if c not in feature_names and c not in DROP_COLS]
    if extras:
        logger.warning(f"Features extras ignoradas: {len(extras)}")

    X = df[feature_names].copy()
    logger.info(f"build_features: {X.shape[0]} registros × {X.shape[1]} features")
    return X


def get_target(df: pd.DataFrame,
               target_col: str = 'casos_confirmados',
               data_corte: datetime = None) -> pd.Series:
    """Retorna target alinhado com build_features()."""
    df = df.copy()
    if 'data_se' in df.columns:
        df['data_se'] = pd.to_datetime(df['data_se'])
        df = df.sort_values('data_se').reset_index(drop=True)
    if data_corte is not None:
        df = df[df['data_se'] <= pd.Timestamp(data_corte)]
    return df[target_col].reset_index(drop=True)


def atualizar_schema(modelo, df_treino: pd.DataFrame,
                     metricas: dict = None,
                     versao: str = None) -> dict:
    """
    Atualiza feature schema após retreino bem-sucedido.
    Salva tanto versionado quanto latest.
    """
    import os
    from src.config import PIPELINE_VERSION, DATASET_VERSION

    schema = {
        'feature_names':      list(modelo.feature_name_),
        'n_features':         len(modelo.feature_name_),
        'pipeline_version':   PIPELINE_VERSION,
        'commit_sha':         os.environ.get('GITHUB_SHA', 'local')[:8],
        'dataset_version':    DATASET_VERSION,
        'drop_cols':          DROP_COLS,
        'data_treino':        str(df_treino['data_se'].max().date()) if 'data_se' in df_treino.columns else 'N/A',
        'n_registros_treino': len(df_treino),
        'timestamp':          datetime.now().isoformat(),
        'r2':                 metricas.get('r2') if metricas else None,
        'mae':                metricas.get('mae') if metricas else None,
    }

    # Salvar latest
    with open(SCHEMA_LATEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
    logger.info(f"Schema latest atualizado: {len(modelo.feature_name_)} features")

    # Salvar versionado se especificado
    if versao:
        path_v = MODELS_DIR / f'lgbm_{versao}_feature_schema.json'
        with open(path_v, 'w', encoding='utf-8') as f:
            json.dump(schema, f, ensure_ascii=False, indent=2)
        logger.info(f"Schema {versao} salvo: {path_v.name}")

    return schema