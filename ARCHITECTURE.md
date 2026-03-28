# Arquitetura — Dengue MT

> Documentação técnica da arquitetura de dados, modelos e infraestrutura do sistema preditivo de surtos de dengue em Cuiabá e Várzea Grande/MT.

---

## Visão Geral
```
FONTES PÚBLICAS          INGESTÃO              ARMAZENAMENTO
SINAN/DATASUS       →   Scripts Python    →   Bronze (local)
INMET / NASA POWER  →   (src/ + Prefect)  →   Silver (HF Hub)
GEE Sentinel-2      →   agendamento       →   Gold  (HF Hub)
NOAA ONI Index      →   semanal           →
Google Trends       →
                              ↓
                    medallion_migration.py (Polars)
                              ↓
                    Rolling Window LightGBM v4
                    R²=0.820 | sMAPE=31.5% | 59 features
                              ↓
              ┌───────────────┴───────────────┐
              ↓                               ↓
    Dashboard Streamlit              API REST FastAPI
    https://dengue-mt-ifmt.streamlit.app
```

---

## Arquitetura Medalhão

### Bronze — Dados Brutos (Local)
Cópia fiel e imutável. Nunca modificado.

### Silver — Dados Limpos (HF Hub)
390.048 registros SINAN | 2.478 dias INMET | 84 meses GEE

### Gold — Features ML (HF Hub)
dataset_features_v4.parquet — 2.182 dias × 59 features

| Versão | Features | Novidades |
|---|---|---|
| v2 | 51 | Base: clima + lags + NDVI/NDWI + ENSO |
| v3 | 53 | + Nowcasting + normalização 100k hab |
| v4 | 59 | + Google Trends + NDBI dinâmico GEE |

---

## Stack Tecnológica

| Camada | Tecnologia | Justificativa |
|---|---|---|
| Ingestão | Python + Prefect 3.x | Pipelines dinâmicos, free tier |
| Transformação | Polars | 5-10x mais rápido que Pandas |
| Formato | Parquet | Compressão eficiente, tipagem forte |
| Modelo | Rolling Window LightGBM | R²=0.820, retreino automático |
| Validação | TimeSeriesSplit | Evita data leakage temporal |
| Otimização | Optuna 50 trials | Bayesian search |
| Interpretabilidade | SHAP | Features ambientais confirmadas |
| Drift monitoring | Evidently 0.7.x | Wasserstein distance |
| Nowcasting | Fator semanal epidemiológico | Corrige subnotificação SINAN |
| Storage | Hugging Face Hub | Gratuito, ilimitado público |
| Dashboard | Streamlit Community Cloud | Gratuito, online |
| API | FastAPI + Uvicorn | Local / Render.com |
| Cache/Fallback | data/cache/ Parquet | Resiliência APIs externas |
| Observabilidade | logging estruturado | reports/pipeline.log |
| Corte temporal | calcular_data_corte() | Anti-leakage operacional |
| Rastreabilidade | run_metadata.json | Artefato por execução |

> **Custo total de infraestrutura: R$ 0,00**

---

## Métricas do Modelo de Produção

| Métrica | Valor | ±DP |
|---|---|---|
| MAE | 17.6 casos/dia | ±5.3 |
| RMSE | 28.4 casos/dia | ±9.3 |
| R² | 0.820 | ±0.052 |
| sMAPE | 31.5% | ±4.9% |

### Ranking Completo

| Modelo | R² | Status |
|---|---|---|
| Rolling Window LightGBM | 0.892 | PRODUÇÃO |
| LightGBM v4 otimizado | 0.820 | atual |
| Ensemble LightGBM+CNN/BiLSTM | 0.873 | experimental |
| CNN + BiLSTM | 0.756 | experimental |
| LSTM v2 | 0.664 | experimental |

---

## Monitoramento de Drift (Evidently)

Resultado — Referência 2018-2023 vs Atual 2023-2024:
- 13/13 features com drift detectado (100%)
- Teste: Wasserstein distance normalizada
- Causa: El Niño 2023-2024 excepcional + surto histórico 2024
- Justifica retreino contínuo via Rolling Window

Limiares do pipeline Prefect:
- MAE_LIMIAR = 25.0 casos/dia
- R2_MINIMO  = 0.75

---

## Nowcasting SINAN

Fator de correção por semana epidemiológica:
- Semanas 1-10 (jan/fev): fator 3.0 — período crítico
- Semanas 20-40: fator ~1.0 — dados maduros
- Semanas 48+: fator ~1.07 — pequena correção

Este é exatamente o período de pico de dengue em Cuiabá.

---

## Fontes de Dados

| Fonte | Dados | Período | Registros |
|---|---|---|---|
| SINAN/DATASUS | Notificações confirmadas | 2007–2024 | 390.048 |
| INMET A901 | Temperatura, precipitação, umidade | 2018–2024 | 2.557 dias |
| NASA POWER API | Radiação solar | 2018–2024 | 2.557 dias |
| GEE Sentinel-2 + MODIS | NDVI, NDWI, NDBI | 2018–2024 | 84 meses |
| NOAA ONI Index | El Niño/La Niña | 2018–2024 | 84 meses |
| IBGE Censo 2022 | População, densidade | 2022 | estático |
| Google Trends | Interesse por "dengue" MT (r=0.922) | 2018–2024 | 367 semanas |
| API CNES | Estabelecimentos Cuiabá/VG | 2024 | 191 unidades |

---

## Reprodutibilidade
```bash
git clone https://github.com/ediney-magalhaes/dengue-mt.git
cd dengue-mt
conda create -n dengue-mt python=3.11 -y
conda activate dengue-mt
pip install -r requirements.txt

# Baixar dados do HF Hub
python -c "
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='edyestatistica/dengue-mt-medallion',
    repo_type='dataset',
    local_dir='data/'
)
"

# Rodar dashboard
streamlit run app/dashboard.py

# Rodar API
uvicorn app.api:app --port 8000
```

---

## Roadmap

v1.0 — concluída 25/03/2026
- Rolling Window LightGBM v4 — R²=0.820
- Dashboard Streamlit + FastAPI
- Deploy: https://dengue-mt-ifmt.streamlit.app
- Prefect pipeline + Evidently + HF Hub

v1.1 — concluída 27/03/2026
- Governança mínima — versioning + commit SHA + feature schema
- Reprodutibilidade — snapshot datado + metadata JSON
- Observabilidade — logs estruturados + modularização
- Corte temporal anti-leakage — calcular_data_corte()
- Resiliência — cache + fallback por fonte

v1.2 — Semana 10
- Ingestão real INMET + GEE + SINAN
- MLflow — versionamento formal
- Dicionário de dados
- Relatório extensionista IFMT

v2.0 — futuro
- Score risco v3 com previsão integrada
- TFT com série histórica completa
- Alertas automáticos email

---

*IFMT — Projeto Extensionista 2026*
*Ediney Magalhães*
*Dashboard: https://dengue-mt-ifmt.streamlit.app*
*Dataset: https://huggingface.co/datasets/edyestatistica/dengue-mt-medallion*