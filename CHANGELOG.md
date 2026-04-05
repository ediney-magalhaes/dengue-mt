# Changelog — Dengue MT

Todas as mudanças notáveis do projeto são documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

## Template para releases futuras
```markdown
## [X.Y.Z] — YYYY-MM-DD

### Modelo
- Arquivo: `lgbm_v4_producao.pkl`
- Dataset: `gold/dataset_features_v4_YYYY-MM-DD.parquet`
- Commit SHA: `xxxxxxxx`
- MAE: X.X casos/dia | R²: X.XXX | sMAPE: XX.X%
- Retreino: [sim/não] | Motivo: [drift/manual/agendado]

### Features
- N features — [sem mudanças / mudanças descritas abaixo]
- Adicionadas: [lista ou "nenhuma"]
- Removidas: [lista ou "nenhuma"]
- Contratos: [validados/alterados]

### Infraestrutura
- Pipeline version: X.X.X
- Drift score: X.XXX | Nível: [normal/moderado/crítico]
- Fontes com fallback: [lista ou "nenhuma"]
```

---

## [1.4.0] — 2026-04-04

### Modelo
- Arquivo: `lgbm_v4_producao.pkl`
- Dataset: `gold/dataset_features_v4_2026-04-04.parquet`
- Commit SHA: `e22fb68`
- MAE: 57.3 casos/semana | R²: 0.063 (dados 2025/2026)
- Retreino: sim | Motivo: drift detectado — MAE=44.4 > limiar 25.0 | R²=-0.69 < 0.75

### Features
- 59 features — sem mudanças no contrato
- Adicionadas: nenhuma
- Removidas: nenhuma
- Contratos: validados — 13/13 testes pytest + Pandera

### Adicionado
- Arquitetura Medalhão completa — Bronze → Silver → Gold respeitando todas as camadas
- `src/ingestion/` — 4 módulos independentes por fonte (infodengue, nasa_power, oni, trends)
- `src/tasks/ingestao.py` — orquestração delegando lógica aos módulos (214 linhas)
- `src/tasks/build_gold.py` — atualização incremental Gold preservando histórico completo
- `src/features/feature_engineering.py` — `calcular_features_novas()` com contexto histórico
- Fallback automático HF Hub quando Gold local não encontrado
- Alinhamento temporal NASA POWER → InfoDengue (domingo = início SE brasileira)

### Corrigido
- `dropna()` no drift e retreino substituído por filtro `casos.notna()` — LightGBM lida com NaN nativamente
- Colunas duplicadas no merge GEE (`ndvi_x`, `ndwi_x`) resolvidas
- `UnboundLocalError: resumo` no pipeline quando retreino falha
- Erro `could not convert string to float: 'N/A'` no CHANGELOG automático
- `.gitignore` corrigido — dados, mlruns, modelos binários excluídos do git

### Infraestrutura
- Pipeline version: 1.0.1-dev
- Drift score: 0.290 | Nível: normal (13 registros — janela 90d)
- Fontes com fallback: nenhuma
- Nota: R² baixo (0.063) esperado — modelo retreinado com 1º ciclo completo 2025/2026. Meta: R²≥0.50 após 3+ ciclos.

### Baseado em literatura
- Rabanser et al. 2019 — Wasserstein distance requer mínimo 50 amostras (26 SE para dados semanais)
- Portaria SVS/MS nº 5/2010 — Semana Epidemiológica brasileira começa no domingo
- Codeco et al. 2018 — agregação climática por SE defensável para dengue

---

## [1.3.0] — 2026-04-03

### Modelo
- Arquivo: `lgbm_v4_producao.pkl`
- Dataset: `gold/dataset_features_v4_2026-03-31.parquet` (último snapshot automático)
- Commit SHA: `ccffb776`
- MAE: 2.41 casos/dia | R²: 0.987 (90d recente) | R²: 0.820 (TimeSeriesSplit oficial)
- Retreino: não | Motivo: modelo estável — drift score 0.205 (normal)

### Features
- 59 features — sem mudanças no contrato
- Adicionadas: nenhuma
- Removidas: nenhuma
- Contratos: validados — 13/13 testes pytest + Pandera

### Adicionado
- MLflow tracking — tags, params, metrics, artifacts, run_id no relatório
- Métricas por fold TimeSeriesSplit registradas no MLflow (retreino)
- Relatórios publicados no HF Hub — snapshot datado + `execucao_latest.md`
- Histórico de runs acumulado em `reports/historico_runs.parquet`
- Aba Monitoramento no dashboard — gráficos históricos de drift, MAE, R²
- CHANGELOG automático gerado a cada retreino promovido
- Dicionário de dados — `reports/data_dictionary.md` + `data_dictionary.csv`
- 65 variáveis documentadas (59 no modelo + 6 fora)
- Módulo canônico `src/features/build_features.py` — elimina feature drift treino/serving
- `build_features_serving()` integrado na API — mesma lógica do treino
- `atualizar_schema()` centralizado no módulo de features
- MLflow run_id na seção 6 do relatório de execução

### Infraestrutura
- Pipeline version: 1.0.1-dev
- MLflow backend: SQLite local (`mlflow.db`)
- Drift score: 0.205 | Nível: normal
- Fontes com fallback: nenhuma

---

## [1.2.0] — 2026-03-30

### Adicionado
- Relatório de execução automático — `src/tasks/relatorio.py` gera `reports/execucao_YYYY-MM-DD.md`
- Drift acionável com Wasserstein distance por feature — níveis Normal/Moderado/Crítico
- Parâmetros conservadores automáticos em drift crítico (n_estimators=1000, lr=0.01)
- Drift score por feature gravado no log e run_metadata.json
- Banner visual 🟢🟡🔴 no dashboard — status do modelo em tempo real
- Fallback ativo sinalizado no banner do dashboard
- Dashboard modularizado em `app/components/` — 6 arquivos de componentes
- Silver INMET disponibilizado no HF Hub para CI/CD
- Primeiro run automático do robô validado — 31/03/2026 00:48 UTC

### Corrigido
- CI/CD: `python src/pipeline_prefect.py` → `python -m src.pipeline_prefect`
- NASA POWER: atraso operacional 7d → 14d (verificação empírica 27/03/2026)
- Polars adicionado nas dependências do job de retreino no CI
- Banner do dashboard: leitura do run_metadata.json corrigida (campo `resultados`)

### Organização
- Scripts históricos de ingestão movidos para `scripts/historico/`
- `.gitignore` atualizado — lightning_logs, checkpoints, modelos obsoletos
- `src/` limpo — apenas pipeline e tasks em produção
- `__pycache__` adicionado ao `.gitignore`

### Baseado em literatura
- BMC Medical Research Methodology 2022 — critérios de promoção de modelos preditivos clínicos
- Wasserstein distance como métrica de drift — MLOps best practices (ScienceDirect 2025)


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