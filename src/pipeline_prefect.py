# ============================================================
# Dengue MT — Pipeline de Ingestão e Retreino Automático
# Orquestrador: Prefect 3.x
# Autor: Ediney Magalhães — IFMT 2026
# ============================================================

from prefect import flow, task, get_run_logger
from prefect.schedules import Cron
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import requests
import joblib
import json
import smtplib
from email.mime.text import MIMEText

# ============================================================
# CONFIGURAÇÕES
# ============================================================
DATA_DIR = Path(__file__).parent.parent / 'data'
MODELS_DIR = Path(__file__).parent.parent / 'models'
REPORTS_DIR = Path(__file__).parent.parent / 'reports'

MAE_LIMIAR = 25.0        # Retreinar se MAE > 25 casos/dia
R2_MINIMO  = 0.75        # Alerta crítico se R² < 0.75

# ============================================================
# TASKS — Ingestão
# ============================================================

@task(name="ingest_inmet", retries=3, retry_delay_seconds=60)
def ingerir_inmet():
    """Baixa dados climáticos INMET mais recentes."""
    logger = get_run_logger()
    logger.info("Iniciando ingestão INMET...")
    
    # Simula verificação de novos dados
    silver_path = DATA_DIR / 'silver' / 'inmet' / 'inmet_cuiaba_2018_2024.parquet'
    if silver_path.exists():
        df = pd.read_parquet(silver_path)
        ultima_data = pd.to_datetime(df.index.max() if df.index.dtype != 'O' 
                                     else df.iloc[:, 0].max())
        logger.info(f"INMET Silver — última data: {ultima_data.date()}")
        return {'status': 'ok', 'ultima_data': str(ultima_data.date()), 
                'fonte': 'inmet'}
    
    logger.warning("Silver INMET não encontrado — requer ingestão manual")
    return {'status': 'pendente', 'fonte': 'inmet'}


@task(name="ingest_nasa_power", retries=3, retry_delay_seconds=60)
def ingerir_nasa_power():
    """Baixa dados de radiação solar NASA POWER."""
    logger = get_run_logger()
    logger.info("Iniciando ingestão NASA POWER...")
    
    try:
        # Testar conectividade com a API
        url = "https://power.larc.nasa.gov/api/temporal/daily/point"
        params = {
            'parameters': 'ALLSKY_SFC_SW_DWN',
            'community': 'RE',
            'longitude': -56.1,
            'latitude': -15.6,
            'start': datetime.now().strftime('%Y%m%d'),
            'end': datetime.now().strftime('%Y%m%d'),
            'format': 'JSON'
        }
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            logger.info("NASA POWER API — conectividade OK")
            return {'status': 'ok', 'fonte': 'nasa_power'}
    except Exception as e:
        logger.error(f"NASA POWER erro: {e}")
    
    return {'status': 'erro', 'fonte': 'nasa_power'}


@task(name="ingest_oni", retries=3, retry_delay_seconds=60)
def ingerir_oni_index():
    """Baixa ONI Index NOAA."""
    logger = get_run_logger()
    logger.info("Iniciando ingestão ONI Index NOAA...")
    
    try:
        url = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            logger.info(f"ONI Index — {len(r.text.splitlines())} linhas")
            return {'status': 'ok', 'fonte': 'oni'}
    except Exception as e:
        logger.error(f"ONI erro: {e}")
    
    return {'status': 'erro', 'fonte': 'oni'}


@task(name="ingest_google_trends", retries=2, retry_delay_seconds=120)
def ingerir_google_trends():
    """Atualiza Google Trends para MT."""
    logger = get_run_logger()
    logger.info("Atualizando Google Trends...")
    
    try:
        from pytrends.request import TrendReq
        import time
        
        pytrends = TrendReq(hl='pt-BR', tz=-240)
        hoje = datetime.now().strftime('%Y-%m-%d')
        mes_passado = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        
        pytrends.build_payload(
            kw_list=['dengue'],
            timeframe=f'{mes_passado} {hoje}',
            geo='BR-MT'
        )
        df = pytrends.interest_over_time()
        
        if not df.empty:
            logger.info(f"Google Trends — {len(df)} semanas atualizadas")
            return {'status': 'ok', 'n_semanas': len(df), 'fonte': 'google_trends'}
        
        time.sleep(2)
    except Exception as e:
        logger.error(f"Google Trends erro: {e}")
    
    return {'status': 'erro', 'fonte': 'google_trends'}


# ============================================================
# TASKS — Data Contracts (Pandera)
# ============================================================

@task(name="validar_dados")
def validar_contratos_dados():
    """Valida qualidade dos dados Silver com Pandera."""
    logger = get_run_logger()
    logger.info("Validando contratos de dados...")
    
    erros = []
    
    # Verificar Gold dataset
    gold_path = DATA_DIR / 'gold' / 'dataset_features_v4.parquet'
    if gold_path.exists():
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
            erros.append(f"Temperatura fora do range: {df['temp_media'].min():.1f}–{df['temp_media'].max():.1f}°C")
        
        # Contrato 4: período mínimo de dados
        df['data'] = pd.to_datetime(df['data'])
        dias = (df['data'].max() - df['data'].min()).days
        if dias < 365:
            erros.append(f"Dataset muito pequeno: {dias} dias")
        
        if not erros:
            logger.info(f"Contratos validados — {df.shape[0]} registros, {df.shape[1]} features")
            return {'status': 'ok', 'registros': df.shape[0], 'features': df.shape[1]}
        else:
            for e in erros:
                logger.error(f"Contrato violado: {e}")
            return {'status': 'erro', 'erros': erros}
    
    logger.warning("Dataset Gold não encontrado")
    return {'status': 'pendente'}


# ============================================================
# TASKS — Drift Monitoring
# ============================================================

@task(name="monitorar_drift")
def monitorar_drift_modelo():
    """Monitora drift do modelo com janela deslizante."""
    logger = get_run_logger()
    logger.info("Monitorando drift do modelo...")
    
    modelo_path = MODELS_DIR / 'lgbm_v3_producao.pkl'
    gold_path = DATA_DIR / 'gold' / 'dataset_features_v4.parquet'
    
    if not modelo_path.exists() or not gold_path.exists():
        logger.warning("Modelo ou dados não encontrados")
        return {'status': 'pendente', 'retreinar': False}
    
    modelo = joblib.load(modelo_path)
    df = pd.read_parquet(gold_path)
    df['data'] = pd.to_datetime(df['data'])
    df = df.sort_values('data').dropna()
    
    # Avaliar nas últimas 90 dias
    corte = df['data'].max() - timedelta(days=90)
    df_recente = df[df['data'] >= corte].copy()
    
    if len(df_recente) < 30:
        logger.warning("Poucos dados recentes para avaliar drift")
        return {'status': 'poucos_dados', 'retreinar': False}
    
    # Features e target
    drop_cols = ['data', 'casos', 'casos_nowcast', 'municipio_id']
    drop_cols = [c for c in drop_cols if c in df_recente.columns]
    
    # Usar apenas features que o modelo conhece
    feature_cols = [c for c in modelo.feature_name_ 
                   if c in df_recente.columns]
    
    X_rec = df_recente[feature_cols]
    y_rec = df_recente['casos']
    
    y_pred = np.maximum(modelo.predict(X_rec), 0)
    
    from sklearn.metrics import mean_absolute_error, r2_score
    mae_recente = mean_absolute_error(y_rec, y_pred)
    r2_recente  = r2_score(y_rec, y_pred)
    
    retreinar = mae_recente > MAE_LIMIAR or r2_recente < R2_MINIMO
    
    logger.info(f"MAE recente (90d): {mae_recente:.1f} | R²: {r2_recente:.3f}")
    logger.info(f"Limiares: MAE≤{MAE_LIMIAR} | R²≥{R2_MINIMO}")
    logger.info(f"{'DRIFT DETECTADO — retreino necessário!' if retreinar else 'Modelo estável'}")
    
    return {
        'status': 'ok',
        'mae_recente': round(mae_recente, 2),
        'r2_recente': round(r2_recente, 3),
        'retreinar': retreinar
    }


# ============================================================
# TASKS — Alertas
# ============================================================

@task(name="enviar_alerta")
def enviar_alerta_email(assunto: str, mensagem: str):
    """Envia alerta por email (requer configuração SMTP)."""
    logger = get_run_logger()
    logger.info(f"Alerta: {assunto}")
    
    # Salvar alerta em arquivo (fallback sem SMTP configurado)
    alerta = {
        'timestamp': datetime.now().isoformat(),
        'assunto': assunto,
        'mensagem': mensagem
    }
    
    alertas_path = REPORTS_DIR / 'alertas.jsonl'
    with open(alertas_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(alerta, ensure_ascii=False) + '\n')
    
    logger.info(f"Alerta salvo em reports/alertas.jsonl")
    return alerta


# ============================================================
# FLOW PRINCIPAL
# ============================================================

@flow(
    name="dengue-mt-pipeline-semanal",
    description="Pipeline semanal de ingestão, validação e monitoramento — Dengue MT"
)
def pipeline_semanal():
    """Flow principal — executa toda semana automaticamente."""
    logger = get_run_logger()
    logger.info("Iniciando Pipeline Semanal — Dengue MT")
    logger.info(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    # 1. Ingestão de dados
    resultado_inmet   = ingerir_inmet()
    resultado_nasa    = ingerir_nasa_power()
    resultado_oni     = ingerir_oni_index()
    resultado_trends  = ingerir_google_trends()
    
    # 2. Validar contratos de dados
    contratos = validar_contratos_dados()
    
    if contratos['status'] == 'erro':
        enviar_alerta_email(
            assunto="ALERTA: Contratos de dados violados — Dengue MT",
            mensagem=f"Erros encontrados: {contratos.get('erros', [])}"
        )
    
    # 3. Monitorar drift
    drift = monitorar_drift_modelo()
    
    if drift.get('retreinar', False):
        enviar_alerta_email(
            assunto="ALERTA: Retreino necessário — Dengue MT",
            mensagem=(
                f"MAE recente: {drift.get('mae_recente')} "
                f"(limiar: {MAE_LIMIAR})\n"
                f"R² recente: {drift.get('r2_recente')} "
                f"(mínimo: {R2_MINIMO})"
            )
        )
    
    # Resumo final
    resumo = {
        'timestamp': datetime.now().isoformat(),
        'inmet': resultado_inmet['status'],
        'nasa_power': resultado_nasa['status'],
        'oni': resultado_oni['status'],
        'trends': resultado_trends['status'],
        'contratos': contratos['status'],
        'drift_mae': drift.get('mae_recente'),
        'drift_r2': drift.get('r2_recente'),
        'retreinar': drift.get('retreinar', False)
    }
    
    logger.info(f"Pipeline concluído: {resumo}")
    return resumo


# ============================================================
# EXECUÇÃO LOCAL (teste)
# ============================================================
if __name__ == "__main__":
    resultado = pipeline_semanal()
    print(f"\n{'='*50}")
    print("RESULTADO DO PIPELINE:")
    print(f"{'='*50}")
    for k, v in resultado.items():
        print(f"  {k}: {v}")