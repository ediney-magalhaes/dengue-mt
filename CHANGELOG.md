# Changelog — Dengue MT

Todas as mudanças notáveis do projeto são documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

---

## [1.1.0] — 2026-03-27

### Adicionado
- Pipeline versioning — PIPELINE_VERSION, DATASET_VERSION, MODEL_VERSION
- Commit SHA amarrado ao schema e resumo do pipeline
- Feature Schema como fonte de verdade — contrato formal de features
- run_metadata.json — artefato de rastreabilidade por execução
- Snapshot datado Gold HF Hub — `dataset_features_v4_YYYY-MM-DD.parquet`
- Metadata JSON por snapshot — hash MD5, período, libs, commit_sha
- Logs estruturados — duração por etapa, nulos, métricas (observabilidade real)
- Modularização — pipeline de 726 → 130 linhas (src/tasks/)
- calcular_data_corte() — função única anti-leakage com fallback documentado
- DATA_CORTE propagado para todas as tasks de ingestão e retreino
- Cache local por fonte em data/cache/ — validade diferenciada por fonte
- Fallback automático quando API falha — pipeline não quebra
- scripts/verificar_atrasos.py — verificação empírica de atrasos por fonte

### Corrigido
- Feature Schema desatualizado — adicionados pipeline_version, commit_sha, dataset_version
- Data leakage operacional Google Trends — lag=7d obrigatório via DATA_CORTE
- Pipeline monolítico 726 linhas — modularizado em src/tasks/

### Baseado em literatura
- Codeco et al. 2018 (InfoDengue) — atraso SINAN Brasil
- PLOS Neglected Tropical Diseases 2024 — corte 15 semanas captura 95% notificações
- NASA POWER empirical test 27/03/2026 — dado < 7d retorna -999

---

## [1.0.0] — 2026-03-26

### Adicionado
- Dashboard online: https://dengue-mt-ifmt.streamlit.app
- Pipeline MLOps automático — GitHub Actions (domingo 06h Cuiabá)
- 13 testes automatizados pytest + Pandera
- Feature Schema Contract — `lgbm_v4_feature_schema.json`
- Retreino automático com promoção/rollback condicional
- Evidently drift monitoring — 13/13 features com drift 2023-2024
- FastAPI — 4 endpoints REST
- Nowcasting SINAN — fator de correção por semana epidemiológica
- Google Trends MT — r=0.922 com casos confirmados
- NDBI via GEE — índice de urbanização dinâmico
- Arquitetura Medalhão Bronze/Silver/Gold
- Hugging Face Hub — storage custo zero

### Modelo
- LightGBM v4 — MAE=17.6 | R²=0.820 | sMAPE=31.5%
- 59 features: clima + lags + NDVI/NDWI/NDBI + ENSO + Trends + Nowcasting
- Validação: TimeSeriesSplit 5 folds

### Infraestrutura
- Custo total: R$ 0,00
- Stack: Python 3.11 + Polars + LightGBM + Streamlit + FastAPI + Prefect

---

## [0.3.0] — 2026-03-22

### Adicionado
- Arquitetura Medalhão implementada com Polars
- Silver SINAN — 390.048 registros (2007-2024)
- Hugging Face Hub configurado como storage remoto
- Score de risco v2 — percentil rank por unidade de saúde
- Mapa Folium — 191 unidades de saúde mapeadas

---

## [0.2.0] — 2026-03-16

### Adicionado
- Rolling Window LightGBM — R²=0.892
- Ensemble LightGBM + CNN/BiLSTM — R²=0.873
- LSTM v1 e v2 testados
- Dashboard Streamlit v1 — 4 abas

---

## [0.1.0] — 2026-03-11

### Adicionado
- Configuração do ambiente Python 3.11 + Conda
- Pipeline ETL: SINAN, INMET, NASA POWER, GEE, NOAA ONI
- Feature Engineering — 55 features × 2.242 registros
- EDA completa com 10 visualizações
- XGBoost baseline — R²=0.805