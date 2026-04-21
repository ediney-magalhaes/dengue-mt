# ADR-019 — LightGBM + Optuna como Algoritmo Principal
 
**Status:** Aceito  
**Data:** 19/04/2026  
**Tema:** Modelagem / Seleção de Algoritmo
 
---
 
## Contexto
 
O projeto passou por três algoritmos ao longo do desenvolvimento:
 
1. **XGBoost** — baseline inicial, resultados preliminares com dataset v1
2. **Prophet** — testado para captura de sazonalidade e tendência
3. **LightGBM** — adotado como principal a partir da refatoração v2.0
Com o Gold v5 disponível (dataset correto, 54 features, 824 registros),
era necessário definir formalmente o algoritmo e a estratégia de otimização
para o modelo de produção.
 
## Decisão
 
Adotar **LightGBM** com otimização de hiperparâmetros via **Optuna**
e modelos separados por município:
 
**Por que LightGBM em vez de XGBoost:**
- Treinamento mais rápido em datasets tabulares de médio porte
- Melhor desempenho nativo com valores NULL (sem imputação forçada)
- `dart` boosting disponível — reduz overfitting em séries com surtos atípicos
- API mais simples para integração com SHAP

**Por que modelos separados por município:**
Cuiabá e Várzea Grande têm dinâmicas epidemiológicas distintas:
- Várzea Grande: 33 semanas com zero casos (alta esparsidade)
- Surto 2023–2025 com intensidade e timing diferentes entre municípios
- Modelo único penalizava o município com dinâmica mais atípica

**Otimização via Optuna:**
- 100 trials por município com `TPESampler`
- Espaço de busca: `num_leaves`, `learning_rate`, `min_data_in_leaf`,
  `feature_fraction`, `bagging_fraction`, `lambda_l1`, `lambda_l2`
- Objetivo: minimizar MAE médio no TimeSeriesSplit 5 folds

### Resultados (Gold v5)
 
**Modelo unificado (baseline):**
- R²=0.741 ± 0.081 | MAE=9.7 ± 6.2 casos/semana

**Modelos otimizados por município:**
 
| Município | Baseline R² | Optuna R² | + SHAP sel. | Features finais |
|-----------|------------|-----------|-------------|-----------------|
| Cuiabá | 0.626 | 0.702 | 0.726 | 12 |
| Várzea Grande | 0.415 | 0.525 | 0.554 | 11 |
 
**Por que Várzea Grande tem R² menor:**
Alta esparsidade (33 semanas zeradas) e surto explosivo 2023–2025
com magnitude sem precedente no histórico — o modelo não tem exemplos
suficientes de surtos dessa intensidade para generalizar.
Documentado como limitação, não como falha do algoritmo.
 
## Consequências
 
- Dois modelos em produção: `lgbm_v5_cuiaba_otimizado.pkl` e
  `lgbm_v5_varzea_grande_otimizado.pkl`
- Previsões geradas separadamente e exibidas no dashboard por município
- Optuna reproduzível via seed fixo registrado no feature schema

## Alternativas consideradas
 
- **LSTM / CNN-BiLSTM** — testados em sessões anteriores, descartados por
  requererem muito mais dados para superar tree-based models em séries
  epidemiológicas semanais de 7 anos
- **Prophet** — captura sazonalidade bem mas não incorpora features
  exógenas (clima, ENSO, Trends) de forma natural
- **Ensemble LightGBM + Prophet** — descartado por complexidade de
  manutenção e sem ganho significativo de métrica nos testes preliminares

## Referências
 
- Nobre et al. (2024) — LightGBM para predição de dengue no Brasil:
  superioridade sobre modelos estatísticos clássicos
- Ke et al. (2017) — LightGBM: A Highly Efficient Gradient Boosting
  Decision Tree (NeurIPS)
 