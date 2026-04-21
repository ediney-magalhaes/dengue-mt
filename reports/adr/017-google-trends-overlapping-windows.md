# ADR-017 — Google Trends: Reconstrução Histórica via Overlapping Windows
 
**Status:** Aceito  
**Data:** 18/04/2026  
**Tema:** Ingestão de Dados / Feature Engineering
 
---
 
## Contexto
 
Google Trends é um sinal estabelecido na literatura de infodemiology para
vigilância de doenças infecciosas — buscas por "dengue" e "sintomas dengue"
antecipam surtos em 1-2 semanas em relação às notificações oficiais.
 
O problema: a API do Google Trends retorna apenas os **últimos 90 dias**
de histórico. Para o dataset de treino cobrindo 2018–2025, isso resultou
em **100% de valores NULL** na feature `trends_dengue` — a série histórica
estava completamente ausente.
 
A decisão inicial (documentada no ADR-016) foi aceitar o NULL temporariamente
e avançar, com LightGBM lidando nativamente com valores ausentes.
Esta ADR documenta a solução definitiva implementada na sessão seguinte.
 
## Decisão
 
Reconstruir a série histórica 2018–2025 via **overlapping windows com
normalização por fator de alinhamento**:
 
**Parâmetros adotados:**
- Janela: 270 dias
- Overlap entre janelas consecutivas: 180 dias
- Passo: 90 dias
- Total de janelas processadas: 33
- Período reconstruído: 2018-01-01 → 2025-12-31

**Técnica de normalização:**
O Google Trends retorna valores relativos (escala 0–100) dentro de cada
janela de extração — janelas diferentes têm escalas incomparáveis entre si.
O fator de normalização é calculado no período de sobreposição entre janelas
consecutivas, alinhando a escala e permitindo reconstrução de série contínua
e comparável.
 
```
janela_1: [2018-01-01 → 2018-10-27]  escala relativa própria
janela_2: [2018-04-01 → 2019-01-25]  escala relativa própria
overlap:  [2018-04-01 → 2018-10-27]  fator = media_j1 / media_j2
janela_2 normalizada = janela_2 × fator
```
 
**Implementação:**
- `scripts/reconstruir_trends_historico.py` — script operacional
- Bronze: `data/bronze/trends/trends_dengue_historico_2018_2025.parquet`
- Staging: `stg_trends_historico.sql` com lag de 7 dias anti-leakage
- Resultado: 457 semanas | 2018-01-07 → 2025-12-31

## Consequências
 
- `trends_dengue` passou de 0% para **100% de cobertura** no intermediate
- Feature disponível para o treinamento do LightGBM v5
- Análise SHAP confirmou Trends como sinal antecipado relevante
  (`trends_lag2` — 4º feature mais importante em Cuiabá)
- Para previsões em produção (2026+): Trends disponível diretamente
  via API sem necessidade de reconstrução

## Limitação conhecida
 
A normalização por fator de alinhamento introduz ruído nas junções entre
janelas — especialmente em períodos de baixo volume de buscas onde
pequenas variações absolutas geram grandes fatores de normalização.
Para o artigo, reportar esta limitação na seção de qualidade dos dados.
 
## Referências
 
- Althouse et al. (2011, PLoS NTD) — Google Trends para dengue:
  metodologia pioneira de overlapping windows
- Scientific Data / Nature (2026) — metodologia validada para reconstrução
  de séries históricas do Trends em vigilância epidemiológica digital no Brasil
 