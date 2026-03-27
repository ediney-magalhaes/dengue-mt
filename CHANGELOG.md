# Changelog — Dengue MT

Todas as mudanças notáveis do projeto são documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

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