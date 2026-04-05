# Decisões de Modelagem e Arquitetura — Dengue MT

> Registro formal das decisões técnicas do projeto, com justificativa e contexto.
> Separado do diário de bordo (cronológico) para facilitar consulta e revisão acadêmica.

---

## Sobre as métricas do modelo — R²=0.892 vs R²=0.820

**Data:** 15-26/03/2026  
**Decisão:** Adotar R²=0.820 (TimeSeriesSplit) como métrica oficial do projeto.

**Contexto:**
Ao longo do projeto dois valores de R² aparecem na documentação:
- R²=0.892 — obtido com Rolling Window de 90 dias (sessão 16/03)
- R²=0.820 — obtido com TimeSeriesSplit 5 folds no dataset completo (sessão 25/03)

**Justificativa:**
O R²=0.892 foi obtido avaliando o modelo treinado nos últimos 90 dias e testado nos próximos 28 — janela pequena e dados recentes, métrica otimista.
O R²=0.820 com TimeSeriesSplit avalia o modelo em 5 janelas temporais distintas cobrindo todo o período 2018-2024 — métrica mais conservadora, honesta e academicamente defensável.

**Referência:** Hyndman & Athanasopoulos (2021) recomendam validação temporal com múltiplas janelas para séries temporais. O TimeSeriesSplit é o padrão da literatura de predição de dengue (Oliveira et al., 2023).

**Impacto:** Todos os documentos acadêmicos (resumo expandido, artigo) usarão R²=0.820.

---

## Governança mínima do pipeline (items 1.1–1.3)

**Data:** 27/03/2026  
**Branch:** `feature/governanca-minima`

### 1.1 — Versionamento da identidade do pipeline

**Decisão:** Adicionar constantes de versão ao `pipeline_prefect.py`:
```python
PIPELINE_VERSION = "1.0.1-dev"
DATASET_VERSION  = "v4"
MODEL_VERSION    = "lgbm_v4"
```

**Justificativa:** Sem identidade formal, não é possível rastrear qual versão do pipeline gerou qual artefato. Em auditoria ou reprodução do experimento, essa informação é crítica.

**Impacto:** Toda execução do pipeline loga e persiste sua versão no resumo final.

---

### 1.2 — Amarrar artefatos ao commit SHA

**Decisão:** Capturar `GITHUB_SHA` do ambiente CI e registrar no resumo e no schema do modelo.
```python
commit_sha = os.environ.get('GITHUB_SHA', 'local')[:8]
```

**Justificativa:** Permite responder "qual commit gerou este modelo?" — requisito básico de rastreabilidade MLOps. Quando rodado localmente retorna `local`; no CI retorna o SHA real do commit.

**Impacto:** `run_metadata.json` e `lgbm_v4_feature_schema.json` registram o SHA de cada execução.

---

### 1.3 — Feature Schema como fonte de verdade + run_metadata.json

**Decisão:** 
- `models/lgbm_v4_feature_schema.json` é a **única fonte de verdade** sobre quais features o modelo aceita
- `metadata/run_metadata.json` registra os metadados de cada execução do pipeline

**Justificativa:** Sem um contrato formal de features, cada retreino pode usar features diferentes — problema de deriva silenciosa identificado como lacuna crítica. O schema garante que treino e serving usem exatamente as mesmas features.

**Campos do schema:**
```json
{
  "feature_names": [...59 features...],
  "n_features": 59,
  "pipeline_version": "1.0.1-dev",
  "commit_sha": "...",
  "dataset_version": "v4",
  "drop_cols": ["data", "casos", "casos_nowcast", "municipio_id"],
  "data_treino": "2024-12-28",
  "r2": 0.820,
  "mae": 17.6
}
```

**Impacto:** O pipeline valida compatibilidade de features antes de qualquer retreino. Features faltando bloqueiam o retreino com alerta. Features extras são ignoradas com warning.

---

## Reprodutibilidade — Versionamento real do Gold (item 2.1 e 2.2)

**Data:** 27/03/2026
**Branch:** `feature/reprodutibilidade`

### 2.1 — Snapshot datado + ponteiro latest

**Decisão:** A cada execução do pipeline, salvar o Gold no HF Hub em dois arquivos:
- `gold/dataset_features_v4_YYYY-MM-DD.parquet` — snapshot imutável datado
- `gold/dataset_features_v4_latest.parquet` — ponteiro para o mais recente

**Justificativa:** Antes desta mudança não era possível responder "esse modelo foi treinado com qual versão exata do dataset?". O snapshot datado garante rastreabilidade completa entre modelo e dados.

**Impacto:** Qualquer retreino futuro pode ser reproduzido baixando o snapshot da data correspondente.

---

### 2.2 — Metadata JSON por snapshot

**Decisão:** Junto com cada snapshot, salvar `dataset_features_v4_YYYY-MM-DD.metadata.json` contendo:
```json
{
  "dataset_version": "v4",
  "pipeline_version": "1.0.1-dev",
  "commit_sha": "...",
  "snapshot_date": "2026-03-27",
  "start_date": "2018-01-01",
  "end_date": "2024-12-28",
  "n_registros": 2242,
  "n_features": 67,
  "file_hash_md5": "...",
  "libs": {
    "polars": "...",
    "lightgbm": "...",
    "pandas": "..."
  }
}
```

**Justificativa:** O hash MD5 garante integridade do arquivo. As versões das libs garantem reprodutibilidade do ambiente. O período confirma cobertura temporal.

**Impacto:** Auditoria completa de cada versão do dataset — requisito para publicação acadêmica e reprodutibilidade.

---

---

## Modularização do pipeline (feature/observabilidade)

**Data:** 27/03/2026
**Branch:** `dev` (direto após merge)

### Decisão: separar pipeline_prefect.py em módulos

**Problema:** `pipeline_prefect.py` atingiu 726 linhas — anti-pattern que dificulta manutenção, testes unitários e leitura do código.

**Estrutura adotada:**
```
src/
├── pipeline_prefect.py   ← flow principal ~130 linhas
├── config.py             ← constantes e paths centralizados
├── observabilidade.py    ← logger estruturado independente do Prefect
└── tasks/
    ├── ingestao.py       ← INMET, NASA, ONI, Trends
    ├── validacao.py      ← contratos Pandera
    ├── drift.py          ← monitoramento de drift
    ├── retreino.py       ← retreino + promoção/rollback
    ├── publicacao.py     ← HF Hub versionado
    └── alertas.py        ← notificações JSONL
```

**Justificativa:**
- Separação de responsabilidades — cada módulo tem uma função clara
- `observabilidade.py` independente do Prefect resolve o problema de logs estruturados
- Facilita testes unitários por módulo
- `config.py` centraliza todas as constantes — evita valores hardcoded espalhados
- Pipeline principal legível — só orquestra, não implementa

**Benefícios observados:**
- Logs estruturados funcionando: duração por etapa, % nulos, métricas
- `pipeline.log` gravado em `reports/` a cada execução
- Comando de execução: `python -m src.pipeline_prefect`

**Impacto no artigo:** cada módulo corresponde a uma subseção da metodologia.

---

---

## Corte Temporal Anti-Leakage (item 4)

**Data:** 27/03/2026
**Branch:** `feature/corte-temporal`

### Problema identificado

O pipeline original não tinha controle de corte temporal — cada fonte de dados
podia trazer dados além do que seria disponível em produção real, causando
data leakage operacional silencioso.

### Atrasos reais verificados empiricamente (27/03/2026)

| Fonte | Atraso real | Método de verificação |
|---|---|---|
| NASA POWER | 14 dias | Teste empírico — dado < 14d retorna -999 (verificado 27/03/2026) |
| Google Trends | 7 dias | Semana aberta = leakage (dado "futuro" -1 dia) |
| ONI Index | ~2 meses | Teste empírico — último registro DJF 2026 |
| INMET | ~2 dias | Verificação Silver local |
| SINAN | 15 semanas | Codeco et al. 2018; PLOS NTD 2024 |
| GEE/NDVI | ~14 dias | Literatura padrão GEE Sentinel-2 |

### Decisão: DATA_CORTE único com bottleneck operacional

**Corte operacional = hoje - 7 dias** (bottleneck = NASA POWER)

SINAN tem 15 semanas de atraso mas é corrigido via nowcasting (já implementado).
O bottleneck do pipeline diário é NASA POWER = 7 dias.

**Referências:**
- Codeco et al. 2018 (InfoDengue) — SINAN delay Brasil
- PLOS Neglected Tropical Diseases 2024 — corte 15 semanas captura 95% notificações
- NASA POWER empirical test 27/03/2026

### Implementação

Função `calcular_data_corte()` em `src/config.py`:
- Calcula corte normal: hoje - 7 dias
- Fallback 1: usa último DATA_CORTE do `run_metadata.json`
- Fallback 2: corte conservador de 14 dias (dobro do bottleneck)
- Nunca quebra o pipeline — degradação graciosa com log de warning

DATA_CORTE propagado para todas as tasks:
- `ingerir_nasa_power(data_corte)` — filtra dado inválido
- `ingerir_google_trends(data_corte)` — garante lag=7d
- `ingerir_inmet(data_corte)` — TODO: aplicar na ingestão real (Semana 10)
- `ingerir_oni_index(data_corte)` — TODO: aplicar na ingestão real (Semana 10)
- `retreinar_modelo(data_corte)` — filtra df[data <= DATA_CORTE]
- Gravado no `run_metadata.json` de cada execução

### Comportamento sem DATA_CORTE

Literatura recomenda degradação graciosa, não quebra do produto:
- Fallback para último corte salvo
- Se não existir: corte conservador de 14 dias
- Warning explícito nos logs

---

## Cache e Fallback de APIs Externas (item 5)

**Data:** 27/03/2026  
**Branch:** `feature/robustez`

### Problema identificado
Pipeline dependia silenciosamente de 4 APIs externas sem fallback.
Qualquer falha de conectividade quebraria o pipeline completamente.

### Decisão: cache local com degradação graciosa

Pasta `data/cache/` com arquivo por fonte + `cache_metadata.json`.

**Validade do cache por fonte:**

| Fonte | Validade | Justificativa |
|---|---|---|
| INMET | 7 dias | Atualização diária |
| NASA POWER | 7 dias | Latência operacional |
| Google Trends | 7 dias | Semana epidemiológica |
| ONI Index | 30 dias | Atualização trimestral |
| GEE/NDVI | 30 dias | Latência Sentinel-2 |
| CNES | 90 dias | Cadastro muda pouco |

**Comportamento:**
- API ok → salva cache + retorna `fallback=False`
- API falha → carrega cache + retorna `fallback=True` + warning no log
- Sem cache → retorna `status=pendente` + error no log

**Rastreabilidade:**
- `fallbacks` por fonte gravado no resumo final
- `cache_status` com validade e última atualização no `run_metadata.json`

---

## Drift Acionável — Wasserstein + Níveis (item 6)

**Data:** 30/03/2026
**Branch:** `dev`

### Decisão: integrar Wasserstein distance ao pipeline com ações automáticas

**Problema:** O drift era apenas monitorado — não gerava ações automáticas diferenciadas.

**Níveis implementados:**

| Nível | Score Wasserstein | Ação |
|---|---|---|
| 🟢 Normal | < 0.3 | Pipeline normal |
| 🟡 Moderado | 0.3 – 0.6 | Retreino com params padrão |
| 🔴 Crítico | ≥ 0.6 | Retreino conservador obrigatório |

**Parâmetros conservadores (drift crítico):**
```python
{'n_estimators': 1000, 'learning_rate': 0.01, 'num_leaves': 20}
```

**Regra de promoção reforçada:**
- pytest 13 testes ✅
- R²_novo >= R²_atual - 0.05
- MAE_novo <= MAE_atual * 1.10

**Referência:** BMC Medical Research Methodology 2022 — recomenda examinar pelo menos dois aspectos de desempenho estatístico (discriminação e calibração) para comparar modelos preditivos clínicos.

**Rastreabilidade:**
- `drift_score` e `nivel_drift` gravados no `run_metadata.json`
- `DRIFT_SCORE | score | nivel | retreinar` logado estruturadamente
- Banner visual 🟢🟡🔴 no dashboard lê o `run_metadata.json`

---

## Relatório de Execução Automático (item 6 — entrega)

**Data:** 30/03/2026

### Decisão: gerar relatório markdown por execução

`src/tasks/relatorio.py` gera `reports/execucao_YYYY-MM-DD.md` a cada run com:
1. Status das etapas de ingestão
2. Fallbacks ativados por fonte
3. Cache das fontes (validade + registros)
4. Métricas do modelo (MAE, R², drift)
5. Gold Dataset (snapshot + link HF Hub)
6. Decisão final (promoveu / rollback / estável)

**Justificativa:** Requisito de auditabilidade MLOps — cada execução deve ser rastreável sem acessar logs brutos.

---

## MLflow Tracking — Versionamento Formal de Experimentos (item 10)

**Data:** 02/04/2026

### Decisão: MLflow local com SQLite + artefatos no HF Hub

**Problema:** Não havia rastreabilidade formal de experimentos — impossível comparar runs ao longo do tempo.

**Implementação:** `src/tasks/mlflow_tracking.py`

**Registrado em cada run:**
- Tags: `dataset_version`, `commit_sha`, `data_corte`, `run_env`, `nivel_drift`, `retreino`
- Params: `atraso_dias`, `modelo`, `n_features`, `mae_limiar`, `r2_minimo`, `drift_normal`, `drift_critico`
- Metrics: `mae_recente`, `r2_recente`, `drift_score`, `fallbacks_ativos`, status por fonte
- Metrics por fold: `mae_fold`, `r2_fold` por step (TimeSeriesSplit 5 folds — só no retreino)
- Artifacts: `lgbm_v4_producao.pkl`, `lgbm_v4_feature_schema.json`, `run_metadata.json`, relatório MD

**Backend:** SQLite local (`mlflow.db`) — custo zero, sem servidor
**run_id** gravado no relatório de execução (seção 6 — Rastreabilidade)

---

## CHANGELOG Automático no Retreino (item 11)

**Data:** 03/04/2026

### Decisão: gerar entrada no CHANGELOG automaticamente após retreino promovido

**Problema:** CHANGELOG era atualizado manualmente — risco de desatualização.

**Implementação:** `atualizar_changelog()` em `src/tasks/relatorio.py`

**Comportamento:**
- Só executa quando `resultado_retreino['status'] == 'promovido'`
- Incrementa automaticamente a versão semântica (patch)
- Referencia snapshot datado do dataset, commit SHA, MAE, R²
- Inserido antes do último release no CHANGELOG

---

## Dicionário de Dados (item 12)

**Data:** 03/04/2026

### Decisão: documentar todas as variáveis com metadados formais

**Implementação:** `scripts/gerar_dicionario_dados.py`

**Gerado automaticamente:**
- `reports/data_dictionary.md` — legível no GitHub/HF Hub
- `reports/data_dictionary.csv` — abre no Excel para filtragem

**Cobertura:**
- 65 variáveis documentadas (59 no modelo + 6 fora)
- Campos: feature, descrição, fonte, frequência, lag_dias, imputação, unidade, intervalo_válido, no_modelo, motivo
- Agrupado por fonte de dados

**Justificativa:** Requisito obrigatório para publicação acadêmica — reviewers exigem descrição formal de todas as variáveis.

---

## Módulo Canônico de Features — build_features (item 13)

**Data:** 03/04/2026

### Decisão: fonte única de verdade para construção de features

**Problema:** Feature drift silencioso entre treino e serving — API podia usar features diferentes do modelo treinado.

**Implementação:** `src/features/build_features.py`

**Funções principais:**
- `build_features(df, data_corte, validar)` — usado no treino/retreino
- `build_features_serving(df, n_linhas)` — usado na API
- `get_target(df, data_corte)` — target alinhado com X
- `atualizar_schema(modelo, df_treino, metricas)` — atualiza schema após promoção
- `_validar_features(df, feature_names)` — detecta feature drift com erro explícito

**Regra:** qualquer feature nova entra em `build_features.py` primeiro e automaticamente atualiza o schema.

**Integração:**
- `src/tasks/retreino.py` usa `build_features()` e `get_target()`
- `app/api.py` usa `build_features_serving()`
- Schema atualizado via `atualizar_schema()` após promoção

**Referência:** Feature Store pattern — MLOps best practices (ScienceDirect 2025)


## Arquitetura Medalhão Completa — Bronze→Silver→Gold Incremental (v1.4.0)

**Data:** 04/04/2026

### Problema identificado

O pipeline estava pulando etapas da arquitetura medalhão — dados da InfoDengue API iam direto para o cache e depois para o Gold sem passar pelo Bronze e Silver corretamente. Features históricas (trends_lag, ndbi, ndvi 2018-2024) eram recalculadas do zero a cada execução e perdidas.

### Decisão 1: Módulos de ingestão separados por responsabilidade

**Estrutura adotada:**
```text
src/ingestion/
├── infodengue.py  ← Bronze→Silver InfoDengue (162 linhas)
├── nasa_power.py  ← Bronze→Silver NASA POWER (129 linhas)
├── oni.py         ← Bronze→Silver ONI Index (78 linhas)
└── trends.py      ← Bronze→Silver Google Trends (93 linhas)
```
**Funções padronizadas por módulo:**
- `ingerir_bronze()` — busca API e salva em `data/bronze/`
- `bronze_para_silver()` — limpa, valida e padroniza
- `salvar_silver()` — persiste em `data/silver/`
- `carregar_silver_fallback()` — fallback quando API falha

**Justificativa:** Single Responsibility Principle — cada módulo tem uma função clara. `src/tasks/ingestao.py` passa a ser apenas orquestrador Prefect, delegando lógica de negócio aos módulos.

---

### Decisão 2: Build Gold incremental com contexto histórico

**Problema:** `calcular_todas_features()` recalculava toda a série do zero a cada execução, perdendo features históricas (`trends_lag_*` com 99% nulos, `ndbi_gee` apenas 2018-2024).

**Solução adotada:**
```text
Gold anterior (completo, todas features) ← preservado
+
Silver novo (apenas semanas novas após última data do Gold)
↓
calcular_features_novas() — usa histórico como contexto
↓
pd.concat([Gold anterior, novas semanas com features])
↓
Gold atualizado
```
**Vantagem:** lags e médias móveis calculados corretamente usando o histórico real como contexto — sem perda de informação histórica.

**Referência:** Codeco et al. 2018 — continuidade da série temporal epidemiológica.

---

### Decisão 3: Alinhamento temporal NASA POWER → InfoDengue

**Problema:** NASA POWER é diário e InfoDengue usa Semana Epidemiológica (SE) começando no domingo. O `dt.to_period('W')` do pandas usa segunda-feira como início — causando desalinhamento de 1 dia.

**Solução:**
```python
df_nasa['semana'] = df_nasa['data'] - pd.to_timedelta(
    df_nasa['data'].dt.dayofweek + 1, unit='D'
)
```

**Justificativa:** Portaria SVS/MS nº 5/2010 define SE brasileira com início no domingo. Codeco et al. 2018 usa exatamente essa agregação para dengue.

---

### Decisão 4: LightGBM com NaN nativamente — sem dropna

**Problema:** `dropna()` no drift e retreino removia todos os registros de 2025/2026 que tinham `trends_lag_*` nulos (99% do histórico não tem Trends).

**Decisão:** Remover todos os `dropna()` sobre features — filtrar apenas `casos.notna()` para garantir target disponível. LightGBM lida com NaN nativamente via split ótimo.

**Justificativa:** LightGBM documentation — "LightGBM handles missing values natively by learning the optimal direction for each split."

---

### Decisão 5: Janela de drift — 26 Semanas Epidemiológicas

**Problema:** Janela de 90 dias tinha apenas 13 registros semanais — insuficiente para Wasserstein distance.

**Justificativa:**
- Rabanser et al. 2019 — Wasserstein distance requer mínimo ~50 amostras para validade estatística
- Com dados semanais: 26 SE (~6 meses) é o mínimo epidemiologicamente significativo
- Janela de referência: 52 SE (1 ano anterior)

**Status:** Limiar mínimo atual = 8 registros (temporário). Meta: aumentar para 26 SE quando Gold tiver dados suficientes de 2025/2026 (previsto: julho/2026).

---

### Decisão 6: trends_lag com 99% nulos — impacto e mitigação

**Situação:** Google Trends retorna apenas 90 dias de histórico. Features `trends_lag_7d/14d/21d` ficam nulas para dados 2018-2023 (~99% do dataset).

**Impacto avaliado:**
- LightGBM ignora features com NaN ao escolher splits — sem erro, mas feature subutilizada
- No período 2025/2026 (últimas 91 semanas) Trends está disponível e contribui
- Correlação Trends × casos: r=0.922 (Oliveira et al. 2023) — feature importante no curto prazo

**Mitigação futura:** armazenar Silver histórico Trends no HF Hub para preservar série completa. Pendente para v1.5.

**Para o artigo:** documentar limitação explicitamente e reportar importância de feature via SHAP separadamente para período com/sem Trends.


---

## Próximas decisões pendentes

- [ ] Silver histórico Trends no HF Hub — preservar série completa
- [ ] Aumentar limiar mínimo drift de 8 para 26 SE (julho/2026)
- [ ] Restaurar `test_modelo_r2_minimo` para 0.50 após modelo estabilizar
- [ ] Seed global e ambiente fixo para reprodutibilidade total
- [ ] Relatório extensionista IFMT
- [ ] Artigo SENIC 2026