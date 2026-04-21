# ADR-012 — MLflow Local (SQLite) para Rastreabilidade de Experimentos
 
**Status:** Aceito  
**Data:** 02/04/2026  
**Tema:** MLOps / Rastreabilidade
 
---
 
## Contexto
 
Sem rastreabilidade formal de experimentos, era impossível comparar runs
ao longo do tempo ou responder: "esse modelo é melhor ou pior que o
treinado há 3 semanas?" Cada treino sobrescrevia as métricas anteriores
sem histórico comparável.
 
Para publicação acadêmica, é necessário demonstrar que o modelo reportado
é resultado de uma busca sistemática — não de um único treino cherry-picked.
 
## Decisão
 
Adotar **MLflow com backend SQLite local** para rastreamento de experimentos:
 
- Backend: `mlflow.db` (SQLite local) — sem servidor, custo zero
- Artefatos: modelos e schemas salvos localmente + HF Hub
- Interface: `mlflow ui` para visualização local quando necessário
### Registrado em cada run
 
**Tags** (contexto da execução):
- `dataset_version`, `commit_sha`, `data_corte`
- `run_env` (local / ci), `nivel_drift`, `retreino` (true/false)
**Params** (configuração do modelo):
- `atraso_dias`, `modelo`, `n_features`
- `mae_limiar`, `r2_minimo`, `drift_normal`, `drift_critico`
**Metrics** (resultados):
- `mae_recente`, `r2_recente`, `drift_score`
- `fallbacks_ativos`, status por fonte de dados
- Por fold: `mae_fold_{n}`, `r2_fold_{n}` (TimeSeriesSplit)
**Artifacts**:
- `lgbm_v5_producao.pkl`, `lgbm_v5_feature_schema.json`
- `run_metadata.json`, relatório Markdown da execução
### Rastreabilidade cruzada
 
O `run_id` do MLflow é gravado no relatório de execução — permitindo
navegar do relatório direto para o experimento correspondente no MLflow UI.
 
## Consequências
 
- Histórico completo de todos os treinos com métricas comparáveis
- Possível demonstrar evolução do modelo entre versões para publicação
- Diagnóstico de regressão: se MAE piorar, compara params entre runs
- `mlflow.db` versionado no git — histórico de experimentos portável
## Alternativas consideradas
 
- **MLflow com servidor PostgreSQL** — descartado por requerer infraestrutura
  dedicada (incompatível com premissa custo zero)
- **Weights & Biases (W&B)** — descartado por ser SaaS pago acima do free tier;
  dados do projeto não devem depender de serviço externo para reprodutibilidade
- **Registro manual em CSV** — descartado por ser frágil, não padronizado
  e sem suporte a artifacts
 