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

## Próximas decisões pendentes

- [ ] Reprodutibilidade — seed global e ambiente fixo
- [ ] Versionamento lógico de dados (não só snapshot)
- [ ] Feature Store lógica — serving consistente
- [ ] Controle de data leakage operacional
- [ ] Observabilidade real (logs estruturados)
- [ ] Fallbacks para APIs externas