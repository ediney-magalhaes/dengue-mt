# ADR-035: Gate de Promoção/Rollback para Modelos Direct CQR

## Status
Implementado — 2026-06-02

## Contexto
Com 12 modelos Direct CQR em produção (ADR-030), o pipeline semanal executava
`treinar_direto_cqr()` incondicionalmente, sobrescrevendo os arquivos `latest`
sem qualquer validação comparativa. Isso representa o anti-padrão "boundary
erosion" descrito por Sculley et al. (2015): a fronteira entre staging e
produção foi apagada.

O modelo Champion (metadata salvo em `direct_cqr_metadata.json`) não era
consultado antes da promoção, tornando impossível detectar regressão de
performance entre retreinos.

## Decisão
Implementar `gate_promocao_direct_cqr()` em `src/tasks/retreino.py`, chamado
no `pipeline_prefect.py` após `treinar_direto_cqr()` e antes de
`publicar_previsao_bairros()`.

O gate aplica o padrão Champion-Challenger (Databricks MLOps Workflow, 2024;
DataRobot, 2025): o modelo recém-treinado compete com o Champion atual antes
de qualquer promoção a produção.

### Três critérios independentes — todos obrigatórios

**Critério 1 — MAE por horizonte (modelos q50)**
Referência: García Crespi et al. (2025) — rolling-origin validation para
séries ambientais demonstra que MAE é a métrica primária operacional para
comparação de versões. R² flutua com a variância do período de teste e não
é robusto para comparação entre retreinos em séries epidemiológicas curtas.
Threshold: MAE_novo[h] ≤ MAE_champion[h] × 1.10 para todo h ∈ {1,2,4,8}.
Tolerância de 10% acomoda variação estatística natural entre janelas de treino.

**Critério 2 — Cobertura calibrada CQR**
Referência: Romano et al. (NeurIPS 2019) — o CQR garante cobertura marginal
finita sobre o intervalo calibrado, não sobre os quantis brutos. Angelopoulos
& Bates (2023) reforçam que validação de cobertura deve ser feita sobre o
intervalo pós-calibração conformal.
Threshold: cobertura_calibrada[h] ≥ 0.85 para todo h ∈ {1,2,4,8}.
Tolerância de 5% abaixo do alvo nominal de 90%.

**Critério 3 — pytest 21 testes**
Referência: Sculley et al. (2015, NeurIPS) — monitoramento abrangente com
resposta automatizada é crítico para confiabilidade de longo prazo. Testes
unitários e de integração devem ser gate obrigatório antes de qualquer
promoção.
Threshold: todos os 21 testes passando (returncode == 0).

### Comportamento de rollback
Reprovação em qualquer critério:
- Arquivos `lgbm_h{h}_q{q}_latest.pkl` permanecem inalterados (Champion mantido)
- `direct_cqr_metadata.json` não é sobrescrito
- `publicar_previsao_bairros()` não é chamado
- Alerta Telegram enviado com critério específico que falhou

### Primeira execução
Se `direct_cqr_metadata.json` não existir (bootstrap), o gate aprova
automaticamente — não há Champion para comparar.

## Consequências
- Pipeline nunca promove modelos com regressão de MAE > 10% em qualquer horizonte
- Pipeline nunca promove modelos com cobertura CQR calibrada < 85%
- Pipeline nunca promove modelos que quebram os 21 testes pytest
- O dashboard só é atualizado com previsões de modelos aprovados pelo gate
- Rastreabilidade: resultado do gate registrado no resumo do pipeline e MLflow

## Referências
- Sculley et al. (2015). Hidden Technical Debt in Machine Learning Systems. NeurIPS.
- Romano, Y., Patterson, E., & Candès, E. (2019). Conformalized Quantile Regression. NeurIPS.
- Angelopoulos, A. & Bates, S. (2023). A Gentle Introduction to Conformal Prediction. Foundations and Trends in ML.
- García Crespi et al. (2025). Rolling-Origin Validation Reverses Model Rankings in Multi-Step Forecasting. arXiv:2603.20315.
- Databricks MLOps Workflow (2024). Champion-Challenger model deployment pattern.
- DataRobot (2025). Introducing MLOps Champion/Challenger Models.