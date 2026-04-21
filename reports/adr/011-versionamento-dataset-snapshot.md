# ADR-011 — Versionamento do Dataset: Snapshot Datado + Ponteiro Latest
 
**Status:** Aceito  
**Data:** 27/03/2026  
**Tema:** MLOps / Reprodutibilidade
 
---
 
## Contexto
 
Antes desta decisão, o pipeline sobrescrevia o dataset Gold a cada execução
com um arquivo único. Isso tornava impossível responder: "esse modelo foi
treinado com qual versão exata dos dados?" — requisito básico de
reprodutibilidade científica e de auditoria MLOps.
 
Se um retreino gerasse um modelo pior, não havia como voltar ao dataset
anterior para diagnóstico ou rollback.
 
## Decisão
 
A cada execução do pipeline, salvar o Gold no Hugging Face Hub em dois arquivos:
 
**Snapshot imutável datado:**
```
gold/dataset_features_v5_YYYY-MM-DD.parquet
gold/dataset_features_v5_YYYY-MM-DD.metadata.json
```
 
**Ponteiro para o mais recente:**
```
gold/dataset_features_v5_latest.parquet
```
 
### Metadata JSON por snapshot
 
Cada snapshot acompanha um `.metadata.json` com:
 
```json
{
  "dataset_version": "v5",
  "pipeline_version": "2.0.0-dev",
  "commit_sha": "6da0241",
  "snapshot_date": "2026-04-19",
  "start_date": "2018-02-04",
  "end_date": "2025-12-28",
  "n_registros": 824,
  "n_features": 54,
  "municipios": [5103403, 5108402],
  "file_hash_md5": "...",
  "libs": {
    "dbt-core": "1.11.7",
    "duckdb": "...",
    "lightgbm": "..."
  }
}
```
 
**Hash MD5** garante integridade do arquivo — detecta corrupção ou
modificação acidental.
 
**Versões das libs** garantem reprodutibilidade do ambiente de transformação.
 
## Consequências
 
- Qualquer retreino futuro pode ser reproduzido baixando o snapshot
  da data correspondente no HF Hub
- Diagnóstico de degradação de modelo: compara snapshots de datas diferentes
- Rollback de dataset: basta apontar o pipeline para o snapshot anterior
- Requisito de publicação acadêmica atendido: dataset com DOI implícito
  via HF Hub (versionado por commit)
## Alternativas consideradas
 
- DVC (Data Version Control) — descartado por adicionar complexidade de
  infraestrutura; HF Hub resolve o problema com custo zero
- Git LFS para arquivos Parquet — descartado por limite de tamanho e
  custo em repositórios grandes
 