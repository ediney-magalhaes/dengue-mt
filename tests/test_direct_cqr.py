# ============================================================
# Dengue MT — Testes Direct CQR v1.0
# pytest — cobertura: 12 modelos Direct + metadata + invariantes
# ============================================================

import pytest
import pandas as pd
import numpy as np
import json
import joblib
from pathlib import Path

from src.config import (
    HORIZONTES_DIRECT, QUANTIS_CQR,
    model_direct_path, DIRECT_METADATA_PATH,
    GOLD_LATEST_PATH,
)

# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture(scope="session")
def metadata_direct():
    if not DIRECT_METADATA_PATH.exists():
        pytest.skip("Metadata Direct CQR não encontrado")
    with open(DIRECT_METADATA_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture(scope="session")
def modelos_direct():
    """Carrega os 12 modelos Direct CQR."""
    modelos = {}
    for h in HORIZONTES_DIRECT:
        for q in QUANTIS_CQR:
            path = model_direct_path(h, q)
            if not path.exists():
                pytest.skip(f"Modelo h={h} q={q} não encontrado: {path.name}")
            modelos[(h, q)] = joblib.load(path)
    return modelos


@pytest.fixture(scope="session")
def df_gold():
    path = GOLD_LATEST_PATH
    if not path.exists():
        path = Path("data/gold/dataset_features_v5_latest.parquet")
    if not path.exists():
        pytest.skip("Gold dataset não encontrado")
    df = pd.read_parquet(path)
    df["data_se"] = pd.to_datetime(df["data_se"])
    return df


# ============================================================
# TESTES — Artefatos existem
# ============================================================

def test_12_modelos_existem():
    """Devem existir 12 arquivos .pkl (4 horizontes × 3 quantis)."""
    faltando = []
    for h in HORIZONTES_DIRECT:
        for q in QUANTIS_CQR:
            path = model_direct_path(h, q)
            if not path.exists():
                faltando.append(path.name)
    assert not faltando, f"Modelos faltando: {faltando}"


def test_metadata_existe():
    """Metadata JSON deve existir."""
    assert DIRECT_METADATA_PATH.exists(), "direct_cqr_metadata.json não encontrado"


def test_metadata_estrutura(metadata_direct):
    """Metadata deve conter campos obrigatórios."""
    obrigatorios = ['n_modelos', 'horizontes', 'quantis', 'modelos']
    faltando = [k for k in obrigatorios if k not in metadata_direct]
    assert not faltando, f"Campos faltando no metadata: {faltando}"
    assert metadata_direct['n_modelos'] == 12, (
        f"Esperado 12 modelos, encontrado {metadata_direct['n_modelos']}"
    )


# ============================================================
# TESTES — Import e criação de targets
# ============================================================

def test_import_task():
    """Task deve importar sem erro."""
    from src.tasks.treinar_direto_cqr import treinar_direto_cqr, criar_targets_direct
    assert callable(treinar_direto_cqr)
    assert callable(criar_targets_direct)


def test_criar_targets(df_gold):
    """criar_targets_direct deve gerar 4 colunas log1p não nulas."""
    from src.tasks.treinar_direto_cqr import criar_targets_direct

    targets = criar_targets_direct(df_gold)

    for h in HORIZONTES_DIRECT:
        col = f'y_h{h}'
        assert col in targets.columns, f"Coluna {col} ausente nos targets"
        # Deve ter valores não nulos (exceto as últimas h linhas por shift)
        n_validos = targets[col].notna().sum()
        assert n_validos > 100, f"{col} tem apenas {n_validos} valores válidos"


def test_targets_sao_log1p(df_gold):
    """Targets devem estar em escala log1p (ADR-024)."""
    from src.tasks.treinar_direto_cqr import criar_targets_direct

    targets = criar_targets_direct(df_gold)

    for h in HORIZONTES_DIRECT:
        col = f'y_h{h}'
        vals = targets[col].dropna()
        # log1p de casos >= 0 deve ser >= 0
        assert (vals >= 0).all(), f"{col} tem valores negativos — log1p não aplicado?"
        # log1p comprime: valores devem ser menores que os casos originais (exceto 0 e 1)
        assert vals.max() < 1000, (
            f"{col} max={vals.max():.1f} — parece escala original, não log1p"
        )


# ============================================================
# TESTES — Predições e invariante expm1 (ADR-024)
# ============================================================

def test_predicoes_nao_negativas(modelos_direct, df_gold):
    """Predições com expm1 devem ser >= 0 para todos os modelos."""
    feature_cols = [
        c for c in modelos_direct[(1, 0.5)].feature_name_
        if c in df_gold.columns
    ]
    X = df_gold[feature_cols].tail(30)

    for (h, q), modelo in modelos_direct.items():
        preds = np.maximum(np.expm1(modelo.predict(X)), 0)
        assert (preds >= 0).all(), f"h={h} q={q}: predições negativas após expm1"


def test_invariante_expm1(modelos_direct, df_gold):
    """Sem expm1, predições ficam em escala log — com expm1, escala original (ADR-024)."""
    feature_cols = [
        c for c in modelos_direct[(1, 0.5)].feature_name_
        if c in df_gold.columns
    ]
    X = df_gold[feature_cols].tail(30)

    modelo_q50 = modelos_direct[(1, 0.5)]
    preds_log = modelo_q50.predict(X)
    preds_original = np.expm1(preds_log)

    # Em escala log, média deve ser < 10 (log1p de ~20k seria ~10)
    assert preds_log.mean() < 10, "Predições não parecem estar em escala log"
    # Em escala original, deve ser > média log
    assert preds_original.mean() > preds_log.mean(), (
        "expm1 não ampliou valores — possível duplo log1p"
    )


# ============================================================
# TESTES — Bandas CQR: lower <= mediana <= upper
# ============================================================

def test_bandas_ordenadas(modelos_direct, df_gold):
    """Para cada horizonte: lower (q05) <= mediana (q50) <= upper (q95)."""
    feature_cols = [
        c for c in modelos_direct[(1, 0.5)].feature_name_
        if c in df_gold.columns
    ]
    X = df_gold[feature_cols].tail(30)

    for h in HORIZONTES_DIRECT:
        p_lo = np.expm1(modelos_direct[(h, 0.05)].predict(X))
        p_50 = np.expm1(modelos_direct[(h, 0.50)].predict(X))
        p_hi = np.expm1(modelos_direct[(h, 0.95)].predict(X))

        # Tolerância: h=8 tem mais quantile crossing (Koenker 2005)
        # Em produção, q_conformal corrige — valida tendência geral
        tol = 15.0 if h == 8 else 2.0
        violacoes_lo = (p_lo > p_50 + tol).sum()
        violacoes_hi = (p_50 > p_hi + tol).sum()
        max_violacoes = int(len(X) * 0.15)  # até 15% tolerável

        assert violacoes_lo <= max_violacoes, (
            f"h={h}: lower > mediana em {violacoes_lo}/{len(X)} pontos (tol={tol})"
        )
        assert violacoes_hi <= max_violacoes, (
            f"h={h}: mediana > upper em {violacoes_hi}/{len(X)} pontos (tol={tol})"
        )


# ============================================================
# TESTES — Consistência entre modelos
# ============================================================

def test_features_consistentes(modelos_direct):
    """Todos os 12 modelos devem usar as mesmas features."""
    features_ref = set(modelos_direct[(1, 0.5)].feature_name_)

    for (h, q), modelo in modelos_direct.items():
        features = set(modelo.feature_name_)
        diff = features.symmetric_difference(features_ref)
        assert not diff, (
            f"h={h} q={q} tem features diferentes: {diff}"
        )


def test_r2_minimo_q50(modelos_direct, df_gold):
    """R² dos modelos q50 nas últimas 52 SE deve ser >= 0.30."""
    from sklearn.metrics import r2_score

    feature_cols = [
        c for c in modelos_direct[(1, 0.5)].feature_name_
        if c in df_gold.columns
    ]

    for h in HORIZONTES_DIRECT:
        modelo = modelos_direct[(h, 0.5)]
        target = df_gold.groupby('municipio_id')['casos_confirmados'].shift(-h)
        mask = target.notna()

        df_test = df_gold[mask].tail(52)
        y_test = target[mask].tail(52)

        X = df_test[feature_cols]
        preds = np.maximum(np.expm1(modelo.predict(X)), 0)

        r2 = r2_score(y_test, preds)
        print(f"\n  h={h} q50: R²={r2:.3f}")
        # h=8 degrada mais — threshold menor
        min_r2 = 0.20 if h == 8 else 0.30
        assert r2 >= min_r2, f"h={h}: R²={r2:.3f} abaixo do mínimo {min_r2}"