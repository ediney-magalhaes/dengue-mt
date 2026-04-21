# ADR-010 — Feature Schema como Fonte de Verdade + run_metadata.json
 
**Status:** Aceito  
**Data:** 27/03/2026  
**Tema:** MLOps / Governança de Modelos
 
---
 
## Contexto
 
Sem um contrato formal de features, cada retreino poderia silenciosamente
usar um conjunto diferente de colunas — problema de **deriva de features**
que corromperia previsões em produção sem nenhum alerta explícito.
O modelo em serving e o modelo em treino precisam operar exatamente
sobre as mesmas features, na mesma ordem.
 
Adicionalmente, sem registro de metadados por execução, era impossível
responder perguntas básicas de auditoria: "qual pipeline gerou esse modelo?",
"com qual versão do dataset esse modelo foi treinado?"
 
## Decisão
 
### Feature Schema — contrato formal de features
 
`models/lgbm_v5_feature_schema.json` é a **única fonte de verdade** sobre
quais features o modelo aceita:
 
```json
{
  "feature_names": ["casos_mm4", "casos_lag1", ...],
  "n_features": 54,
  "pipeline_version": "2.0.0-dev",
  "commit_sha": "6da0241",
  "dataset_version": "v5",
  "drop_cols": ["data_se", "casos_confirmados", "municipio_id"],
  "data_treino": "2025-12-28",
  "r2": 0.741,
  "mae": 9.7
}
```
 
**Comportamento do pipeline ao retreinar:**
- Features faltando → retreino bloqueado com alerta explícito
- Features extras → ignoradas com warning no log
- Schema atualizado automaticamente após retreino promovido
### run_metadata.json — rastreabilidade por execução
 
`metadata/run_metadata.json` registra os metadados de cada execução:
- `pipeline_version`, `dataset_version`, `commit_sha`
- Timestamp de início e fim, duração por etapa
- Status de cada fonte (ok / fallback / falha)
- Métricas de drift e decisão de retreino
## Consequências
 
- Qualquer incompatibilidade de features é detectada antes do retreino
- Auditoria completa: dado o modelo, é possível reconstruir exatamente
  qual pipeline, dataset e commit o geraram
- `run_metadata.json` versionado no git — histórico de execuções rastreável
## Alternativas consideradas
 
- MLflow Model Registry — descartado por requerer servidor dedicado
  (custo e complexidade incompatíveis com a premissa do projeto)
- Validação implícita por ordem de colunas — descartado por ser frágil
  e silencioso em caso de falha
 