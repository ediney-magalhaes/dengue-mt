# ADR-008 — Pipeline ad-hoc Python → dbt-core + DuckDB Medallion (v2.0)
 
**Status:** Aceito (substitui pipeline ad-hoc original)  
**Data:** 04/04/2026  
**Tema:** Arquitetura de Dados
 
---
 
## Contexto
 
A versão inicial do pipeline (v1.x) era composta por scripts Python ad-hoc
que misturavam ingestão, transformação e geração de features em um único
fluxo sem separação de responsabilidades. Problemas identificados:
 
- **Sem camadas:** ingestão, limpeza e feature engineering no mesmo script
- **Transformações na ingestão:** scripts modificavam dados na coleta,
  impossibilitando reprocessamento sem re-download
- **Sem testes de dados:** qualquer mudança nas APIs silenciosamente
  corromperia o dataset de treino
- **Sem rastreabilidade de linhagem:** impossível saber qual transformação
  gerou qual coluna
- **Manutenção difícil:** `pipeline_prefect.py` com 726 linhas (ver ADR-009)
- **Dataset com problemas estruturais:** o dataset gerado por esse pipeline
  tinha inconsistências que só foram identificadas após EDA — motivando a
  refatoração completa para v2.0
## Decisão
 
Refatorar completamente para arquitetura **medallion** com **dbt-core + DuckDB**:
 
### Camadas
 
```
Bronze  →  Silver (dbt staging)  →  Gold (dbt marts)
```
 
| Camada | Responsabilidade | Tecnologia |
|--------|-----------------|------------|
| Bronze | Dados brutos da API, sem transformação | Python (src/ingestion/) |
| Silver | Limpeza, tipagem, padronização por fonte | dbt staging models |
| Gold | Features para ML, lags, joins entre fontes | dbt mart models |
 
### Stack adotada
 
- **dbt-core 1.11.7** + **dbt-duckdb 1.10.1** — transformações SQL versionadas
- **DuckDB** — banco colunar embarcado, sem servidor, custo zero
- **Parquet** — formato de armazenamento Bronze e Gold
- `external_location` via `meta.external_location` em `sources.yml`
### Princípios estabelecidos
 
- **Staging nunca filtra por período** — responsabilidade exclusiva do marts
- **Bronze é imutável** — scripts de ingestão só escrevem Bronze, nunca transformam
- **Testes dbt** validam cada camada antes de avançar
- **Linhagem completa** — dbt documenta dependências automaticamente
### Resultado após refatoração
 
```
dbt run  → PASS=9  WARN=0 ERROR=0
dbt test → PASS=62 WARN=0 ERROR=0
```
 
- 6 staging models (stg_infodengue, stg_nasa_power, stg_oni,
  stg_gee, stg_trends, stg_modis)
- Intermediate: `int_dengue_mt` — 832 registros (416 SE × 2 municípios)
- Gold: `mart_dengue_features` — 54 features × 824 registros
## Consequências
 
- Pipeline reproduzível e testável por camada
- Qualquer fonte pode ser reprocessada sem afetar as demais
- Testes de dados (not_null, unique, accepted_values) detectam problemas
  nas APIs antes que corrompam o dataset de treino
- Documentação de linhagem gerada automaticamente pelo dbt
## Alternativas consideradas
 
- **Apache Spark** — descartado por overhead de infraestrutura para o volume
  de dados do projeto (~800 registros semanais)
- **Pandas puro com funções modulares** — descartado por ausência de testes
  de dados nativos e linhagem
- **SQLModel / SQLAlchemy** — descartado por não ter o conceito de camadas
  e testes integrados que o dbt fornece nativamente
## Referências
 
- Reis et al. (2022) — medallion architecture para dados de saúde pública
- dbt-core docs: https://docs.getdbt.com