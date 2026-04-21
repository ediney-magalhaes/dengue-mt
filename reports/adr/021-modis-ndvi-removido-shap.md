# ADR-021 — MODIS NDVI/EVI Removido do Modelo via Análise SHAP
 
**Status:** Aceito  
**Data:** 19/04/2026  
**Tema:** Modelagem / Seleção de Features
 
---
 
## Contexto
 
NDVI e EVI do MODIS MOD13A3 foram incluídos no Gold v5 como proxies de
vegetação e umidade do solo — variáveis associadas na literatura à
proliferação do *Aedes aegypti* em ambientes tropicais. A hipótese era que
cobertura vegetal densa e solo úmido favoreceriam a criação de criadouros
naturais do mosquito.
 
A inclusão foi fundamentada em Sebastianelli et al. (2024), que reportou
NDVI como feature relevante em modelos de dengue no Brasil.
 
## Decisão
 
Remover `ndvi` e `evi` do modelo de produção após análise SHAP demonstrar
importância < 1% em ambos os municípios:
 
| Feature | Importância SHAP — Cuiabá | Importância SHAP — Várzea Grande |
|---------|--------------------------|----------------------------------|
| ndvi_lag2 | < 0.5% | < 0.5% |
| ndvi_lag3 | < 0.5% | < 0.5% |
| evi_lag2 | < 0.5% | < 0.5% |
| evi_lag3 | < 0.5% | < 0.5% |
 
**Por que NDVI não contribuiu neste modelo:**
 
1. **Resolução temporal:** MOD13A3 é mensal — em uma série semanal,
   o mesmo valor de NDVI repete-se por 4–5 semanas consecutivas,
   reduzindo seu poder discriminativo
2. **Escala municipal:** Cuiabá e Várzea Grande são áreas urbanas densas —
   variação de NDVI intra-municipal é baixa; o sinal relevante seria
   em escala de bairro, não de município
3. **Redundância com variáveis climáticas:** precipitação e umidade
   (já incluídas com lags) capturam indiretamente o mesmo sinal
   de disponibilidade de água que o NDVI representaria
## Consequências
 
- Gold v5: 54 features → modelo de produção com **12 features** (Cuiabá)
  e **11 features** (Várzea Grande) após seleção SHAP
- Pipeline MODIS **mantido ativo** — fonte preservada por duas razões:
  1. MOD13Q1 (250m, quinzenal) pode fornecer sinal mais discriminativo
     em análise futura por bairro
  2. Remoção da fonte dificultaria reintrodução futura sem reprocessamento
- Para o artigo: reportar NDVI separadamente como feature testada e
  descartada por evidência empírica — fortalece a narrativa de seleção
  rigorosa de features
## Nota sobre a literatura
 
A divergência com Sebastianelli et al. (2024) é explicável:
o estudo usa dados em escala estadual/regional — em escala municipal
urbana, o sinal de NDVI é diluído pela homogeneidade da cobertura do solo.
Isso é um achado relevante para o artigo.
 
## Referências
 
- Lundberg & Lee (2017) — SHAP: Unified approach to interpreting model
  predictions (NeurIPS)
- Sebastianelli et al. (2024, Scientific Reports) — MODIS NDVI em
  modelos de dengue no Brasil (escala regional)
- Huete et al. (2002) — EVI vs NDVI em vegetação tropical densa
 