# Architecture Decision Records — Dengue MT
 
> Registro formal das decisões técnicas e arquiteturais do projeto.
> Cada ADR documenta o contexto, a decisão tomada, as alternativas consideradas
> e as consequências — incluindo caminhos percorridos e substituídos.
 
---
 
## Como ler este índice
 
| Status | Significado |
|--------|-------------|
| ✅ Aceito | Decisão atual em vigor |
| 🔄 Substituído | Foi a decisão, foi trocada — referencia o substituto |
| 🔵 Proposto | Decisão tomada, implementação pendente |
 
---
 
## Infraestrutura e Versionamento
 
| ADR | Título | Status | Data |
|-----|--------|--------|------|
| [ADR-001](001-conventional-commits-gitflow.md) | Conventional Commits + GitFlow dev→main | ✅ Aceito | 09/03/2026 |
 
---
 
## Ingestão de Dados
 
| ADR | Título | Status | Data |
|-----|--------|--------|------|
| [ADR-002](002-sinan-datasus-fetcher.md) | SINAN via datasus-fetcher (pySUS incompatível Windows) | 🔄 Substituído por ADR-004 | 11/03/2026 |
| [ADR-003](003-conversao-dbc-colab.md) | Conversão .dbc → Parquet via Google Colab | 🔄 Substituído por ADR-004 | 11/03/2026 |
| [ADR-004](004-infodengue-nasa-power-fonte-principal.md) | InfoDengue + NASA POWER como fontes principais | ✅ Aceito | 04/04/2026 |
| [ADR-005](005-gee-sentinel2-vegetacao.md) | Google Earth Engine + Sentinel-2 para vegetação | 🔄 Substituído por ADR-014 | 14/03/2026 |
| [ADR-014](014-modis-appeears-substitui-gee.md) | MODIS MOD13A3 via AppEEARS NASA Earthdata | ✅ Aceito | 15/04/2026 |
| [ADR-017](017-google-trends-overlapping-windows.md) | Google Trends: reconstrução histórica via overlapping windows | ✅ Aceito | 18/04/2026 |
 
---
 
## Arquitetura de Dados (dbt + DuckDB)
 
| ADR | Título | Status | Data |
|-----|--------|--------|------|
| [ADR-008](008-dbt-duckdb-medallion.md) | Pipeline ad-hoc → dbt-core + DuckDB Medallion (v2.0) | ✅ Aceito | 04/04/2026 |
| [ADR-015](015-macros-dbt-padronizacao-datas.md) | Macros dbt para padronização de tipos de data | ✅ Aceito | 13/04/2026 |
| [ADR-016](016-staging-nao-filtra-periodo.md) | Staging não filtra por período — responsabilidade do marts | ✅ Aceito | 13/04/2026 |
| [ADR-018](018-gold-v5-features-lags-anti-leakage.md) | Gold v5 — features, lags epidemiológicos e anti-leakage | ✅ Aceito | 18/04/2026 |
 
---
 
## Pipeline e Orquestração
 
| ADR | Título | Status | Data |
|-----|--------|--------|------|
| [ADR-007](007-corte-temporal-anti-leakage.md) | Corte temporal anti-leakage — bottleneck operacional 7 dias | ✅ Aceito | 27/03/2026 |
| [ADR-009](009-modularizacao-pipeline-prefect.md) | Modularização do pipeline Prefect (726 linhas → módulos) | ✅ Aceito | 27/03/2026 |
 
---
 
## MLOps e Governança
 
| ADR | Título | Status | Data |
|-----|--------|--------|------|
| [ADR-010](010-feature-schema-fonte-de-verdade.md) | Feature Schema como fonte de verdade + run_metadata.json | ✅ Aceito | 27/03/2026 |
| [ADR-011](011-versionamento-dataset-snapshot.md) | Versionamento do dataset: snapshot datado + ponteiro latest | ✅ Aceito | 27/03/2026 |
| [ADR-012](012-mlflow-sqlite-rastreabilidade.md) | MLflow local (SQLite) para rastreabilidade de experimentos | ✅ Aceito | 02/04/2026 |
| [ADR-013](013-artefatos-commit-sha.md) | Artefatos amarrados ao commit SHA via GITHUB_SHA | ✅ Aceito | 27/03/2026 |
 
---
 
## Modelagem e Avaliação
 
| ADR | Título | Status | Data |
|-----|--------|--------|------|
| [ADR-006](006-metrica-oficial-timeseriessplit.md) | Métrica oficial: TimeSeriesSplit vs Rolling Window 90 dias | ✅ Aceito | 26/03/2026 |
| [ADR-019](019-lightgbm-optuna-algoritmo-principal.md) | LightGBM + Optuna como algoritmo principal | ✅ Aceito | 19/04/2026 |
| [ADR-020](020-transformacao-log1p-target.md) | Transformação log1p no target | ✅ Aceito | 19/04/2026 |
| [ADR-021](021-modis-ndvi-removido-shap.md) | MODIS NDVI/EVI removido do modelo via análise SHAP | ✅ Aceito | 19/04/2026 |
 
---
 
## Dashboard e Produto
 
| ADR | Título | Status | Data |
|-----|--------|--------|------|
| [ADR-022](022-idw-mapa-risco-bairro-dashboard.md) | IDW dinâmico para mapa de risco por bairro — acoplado ao modelo | 🔵 Proposto | 20/04/2026 |
 
---
 
## Resumo por status
 
| Status | ADRs |
|--------|------|
| ✅ Aceito (18) | 001, 004, 007, 008, 009, 010, 011, 012, 013, 014, 015, 016, 017, 018, 019, 020, 021 |
| 🔄 Substituído (3) | 002 → ADR-004, 003 → ADR-004, 005 → ADR-014 |
| 🔵 Proposto (1) | 022 |
 
---
 
## Linha do tempo
 
```
Mar/2026  ADR-001  Conventional Commits + GitFlow
          ADR-002  SINAN datasus-fetcher          [substituído]
          ADR-003  Conversão .dbc Colab           [substituído]
          ADR-005  GEE Sentinel-2                 [substituído]
          ADR-006  Métrica oficial TimeSeriesSplit
          ADR-007  Corte temporal anti-leakage
          ADR-009  Modularização Prefect
          ADR-010  Feature Schema
          ADR-011  Versionamento dataset snapshot
          ADR-013  Artefatos commit SHA
 
Abr/2026  ADR-012  MLflow SQLite
          ADR-004  InfoDengue + NASA POWER        [substitui 002 e 003]
          ADR-008  dbt-core + DuckDB Medallion    [substitui pipeline ad-hoc]
          ADR-015  Macros dbt padronização datas
          ADR-016  Staging não filtra período
          ADR-014  MODIS AppEEARS                 [substitui 005]
          ADR-017  Google Trends overlapping windows
          ADR-018  Gold v5 features e lags
          ADR-019  LightGBM + Optuna
          ADR-020  Transformação log1p
          ADR-021  MODIS NDVI removido SHAP
          ADR-022  IDW dinâmico dashboard         [proposto]
```
 
---
 
*Instituto Federal de Mato Grosso (IFMT) — Projeto Extensionista Dengue MT*