# ADR-006 — Métrica oficial: TimeSeriesSplit vs Rolling Window 90 dias
 
**Status:** Aceito  
**Data:** 26/03/2026  
**Tema:** Modelagem / Avaliação
 
---
 
## Contexto
 
Ao longo do desenvolvimento inicial do modelo, dois valores de R² distintos
apareceram na documentação e causaram inconsistência:
 
- **R²=0.892** — obtido com Rolling Window de 90 dias (sessão 16/03/2026),
  dataset v1 com problemas estruturais
- **R²=0.820** — obtido com TimeSeriesSplit 5 folds (sessão 25/03/2026),
  dataset v1 ainda com problemas estruturais
- **R²=0.741 ± 0.081** — obtido com TimeSeriesSplit 5 folds (sessão 19/04/2026),
  dataset Gold v5 completo e correto (2018–2025, 54 features, 824 registros)
Era necessário definir qual métrica e qual dataset seriam adotados oficialmente
em toda a documentação acadêmica do projeto.
 
## Decisão
 
Adotar **R²=0.741 ± 0.081 | MAE=9.7 ± 6.2 (TimeSeriesSplit 5 folds, Gold v5)**
como métrica oficial.
 
**Por que o R²=0.892 é enganoso:**
- Avalia o modelo treinado nos últimos 90 dias e testado nos próximos 28
- Janela pequena e dados recentes — o modelo memoriza padrões sazonais
  recentes sem ser testado em períodos históricos distintos
- Métrica otimista que não representa desempenho real em produção

**Por que o R²=0.820 também é inválido:**
- Obtido sobre dataset v1 com problemas estruturais de cobertura e leakage
- Dataset foi completamente refeito na refatoração v2.0 (ver ADR-008)
- Não é comparável ao R²=0.741 — datasets diferentes

**Por que o TimeSeriesSplit é correto:**
- Avalia o modelo em 5 janelas temporais distintas cobrindo 2018–2025
- Cada fold treina no passado e testa no futuro imediato — simula produção real
- Expõe o modelo a diferentes regimes: anos normais, COVID (2020–2021),
  surto histórico 2024/2025
- Métrica conservadora, honesta e academicamente defensável

**Resultados por fold (Gold v5):**
| Fold | R² | MAE | Período de teste |
|------|----|-----|-----------------|
| 1 | 0.722 | 8.3 | ~2020 |
| 2 | 0.621 | 16.4 | ~2021 (COVID) |
| 3 | 0.779 | 3.7 | ~2022 |
| 4 | 0.868 | 2.7 | ~2023 |
| 5 | 0.716 | 17.6 | ~2024/2025 (surto) |
 
## Consequências
 
- Todos os documentos acadêmicos (resumo SENIC, artigo) usam R²=0.741 ± 0.081
- Comparações com literatura devem usar TimeSeriesSplit como base
- R²=0.892 e R²=0.820 permanecem documentados aqui como referência histórica —
  não devem ser citados em publicações
## Referências
 
- Hyndman & Athanasopoulos (2021) — *Forecasting: Principles and Practice*:
  recomendam validação temporal com múltiplas janelas para séries temporais
- Oliveira et al. (2023) — TimeSeriesSplit como padrão na literatura de
  predição de dengue
 