# ============================================================
# Dengue MT — Task: Validação de Dados (Pandera)
# ============================================================

from prefect import task, get_run_logger
from src.config import DATA_DIR
import pandas as pd


@task(name="validar_dados")
def validar_contratos_dados():
    """Valida qualidade dos dados Silver com Pandera."""
    logger = get_run_logger()
    logger.info("Validando contratos de dados...")

    erros = []

    gold_path = DATA_DIR / 'gold' / 'dataset_features_v4.parquet'
    if not gold_path.exists():
        logger.warning("Dataset Gold não encontrado")
        return {'status': 'pendente'}

    df = pd.read_parquet(gold_path)

    # Contrato 1: sem nulos nas features críticas
    features_criticas = ['casos', 'temp_media', 'precipitacao_total',
                         'umidade_media', 'casos_lag_7d']
    nulos = df[features_criticas].isnull().sum()
    if nulos.any():
        erros.append(f"Nulos em features críticas: {nulos[nulos>0].to_dict()}")

    # Contrato 2: casos não negativos
    if (df['casos'] < 0).any():
        erros.append("Casos negativos detectados!")

    # Contrato 3: temperatura plausível para Cuiabá
    if df['temp_media'].max() > 50 or df['temp_media'].min() < 10:
        erros.append(
            f"Temperatura fora do range: "
            f"{df['temp_media'].min():.1f}–{df['temp_media'].max():.1f}°C"
        )

    # Contrato 4: período mínimo de dados
    df['data'] = pd.to_datetime(df['data'])
    dias = (df['data'].max() - df['data'].min()).days
    if dias < 365:
        erros.append(f"Dataset muito pequeno: {dias} dias")

    if not erros:
        logger.info(
            f"Contratos validados — {df.shape[0]} registros, {df.shape[1]} features"
        )
        return {
            'status': 'ok',
            'registros': df.shape[0],
            'features': df.shape[1],
            'periodo_dias': dias,
            'features_criticas_nulos': nulos.to_dict()
        }
    else:
        for e in erros:
            logger.error(f"Contrato violado: {e}")
        return {'status': 'erro', 'erros': erros}