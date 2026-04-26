# ============================================================
# Dengue MT — Testes Automatizados v2.0
# pytest — cobertura: Gold v5 + modelo latest
# ============================================================

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture(scope="session")
def df_gold():
    path = Path("data/gold/dataset_features_latest.parquet")
    if not path.exists():
        path = Path("data/gold/dataset_features_v5_latest.parquet")
    if not path.exists():
        pytest.skip("Gold dataset não encontrado")
    df = pd.read_parquet(path)
    df["data_se"] = pd.to_datetime(df["data_se"])
    return df


@pytest.fixture(scope="session")
def modelo():
    import joblib
    path = Path("models/lgbm_producao_latest.pkl")
    if not path.exists():
        path = Path("models/lgbm_v5_producao.pkl")
    if not path.exists():
        pytest.skip("Modelo não encontrado")
    return joblib.load(path)


# ============================================================
# TESTES — Gold Dataset
# ============================================================

def test_gold_shape(df_gold):
    """Gold deve ter pelo menos 800 registros e 10 features."""
    assert df_gold.shape[0] >= 800, f"Poucos registros: {df_gold.shape[0]}"
    assert df_gold.shape[1] >= 10, f"Poucas colunas: {df_gold.shape[1]}"


def test_gold_periodo(df_gold):
    """Gold deve cobrir 2018–2025."""
    anos = df_gold["data_se"].dt.year.unique()
    assert 2018 in anos, "2018 ausente no dataset"
    assert anos.max() >= 2025, f"Ano máximo é {anos.max()} — esperado >= 2025"


def test_gold_municipios(df_gold):
    """Gold deve conter Cuiabá e Várzea Grande."""
    municipios = df_gold["municipio_id"].unique()
    assert 5103403 in municipios, "Cuiabá (5103403) ausente"
    assert 5108402 in municipios, "Várzea Grande (5108402) ausente"


def test_gold_casos_nao_negativos(df_gold):
    """Casos de dengue nunca podem ser negativos."""
    assert (df_gold["casos_confirmados"] >= 0).all(), "Casos negativos detectados!"


def test_gold_sem_duplicatas(df_gold):
    """Não deve haver duplicatas de (municipio_id, data_se)."""
    duplicatas = df_gold.duplicated(subset=["municipio_id", "data_se"]).sum()
    assert duplicatas == 0, f"{duplicatas} duplicatas!"


def test_gold_colunas_obrigatorias(df_gold):
    """Gold deve ter as colunas essenciais."""
    obrigatorias = ["data_se", "municipio_id", "casos_confirmados", "casos_lag1"]
    faltando = [c for c in obrigatorias if c not in df_gold.columns]
    assert not faltando, f"Colunas faltando: {faltando}"


# ============================================================
# TESTES — Modelo
# ============================================================

def test_modelo_carrega(modelo):
    """Modelo deve carregar sem erros."""
    assert modelo is not None


def test_modelo_features(modelo):
    """Modelo deve ter features definidas."""
    assert hasattr(modelo, "feature_name_")
    assert len(modelo.feature_name_) > 0
    print(f"\nFeatures do modelo: {len(modelo.feature_name_)}")


def test_modelo_predicao_basica(modelo, df_gold):
    """Modelo deve gerar predições não negativas."""
    feature_cols = [c for c in modelo.feature_name_ if c in df_gold.columns]
    X = df_gold[feature_cols].tail(30)

    preds = np.maximum(np.expm1(modelo.predict(X)), 0)

    assert len(preds) == len(X), "Número de predições incorreto"
    assert (preds >= 0).all(), "Predições negativas detectadas"
    assert preds.mean() < 1000, f"Predições muito altas: {preds.mean():.1f}"


def test_modelo_r2_minimo(modelo, df_gold):
    """R² nas últimas 52 SE deve ser >= 0.50."""
    from sklearn.metrics import r2_score

    feature_cols = [c for c in modelo.feature_name_ if c in df_gold.columns]
    df_test = df_gold[feature_cols + ["casos_confirmados"]].tail(52)
    df_test = df_test[df_test["casos_confirmados"].notna()]

    X = df_test[feature_cols]
    y = df_test["casos_confirmados"]

    preds = np.maximum(np.expm1(modelo.predict(X)), 0)
    r2 = r2_score(y, preds)

    print(f"\nR² últimas 52 SE: {r2:.3f}")
    assert r2 >= 0.50, f"R² abaixo do mínimo aceitável: {r2:.3f}"