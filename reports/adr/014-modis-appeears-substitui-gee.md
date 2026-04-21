# ADR-014 — GEE Substituído por MODIS MOD13A3 via AppEEARS NASA Earthdata
 
**Status:** Aceito (substitui ADR-005)  
**Data:** 15/04/2026  
**Tema:** Ingestão de Dados / Geoespacial
 
---
 
## Contexto
 
A abordagem anterior com Google Earth Engine (ADR-005) foi abandonada por
ser incompatível com automação total — coleta manual, sem API programática
aprovada, cobertura de 2025 ausente.
 
A necessidade de dados de vegetação permanecia: NDVI é variável estabelecida
na literatura como proxy de umidade do solo e cobertura vegetal — ambientes
favoráveis à proliferação do *Aedes aegypti*.
 
## Decisão
 
Substituir GEE por **MODIS MOD13A3.061 via NASA AppEEARS API**:
 
**Produto:** MOD13A3.061 — NDVI e EVI mensais, resolução 1km  
**API:** AppEEARS (Application for Extracting and Exploring Analysis Ready Samples)  
**Conta:** NASA Earthdata — gratuita, aprovação imediata (`ediney_dengue`)  
**Cobertura:** 2000 → hoje (atualização automática mensal)  
**Custo:** zero
 
**Por que MODIS MOD13A3 em vez de Sentinel-2:**
- Resolução 1km suficiente para análise em escala municipal
- Série histórica desde 2000 — cobre todo o período do projeto com margem
- `pixel_reliability` permite filtrar pixels de baixa qualidade
  (nuvens, neve, aerossóis) automaticamente
- EVI disponível além do NDVI — mais robusto em vegetação densa
  (Huete et al. 2002)
- API totalmente automática — compatível com pipeline GitHub Actions

**Implementação:**
- `src/ingestion/modis.py` — módulo Bronze via AppEEARS
- `dengue_mt_dbt/models/staging/stg_modis.sql` — Silver com lags 2-4 SE
- Bronze: `data/bronze/modis/modis_ndvi_evi_latest.parquet`
- 198 registros (99 meses × 2 municípios) | 2018-01-01 → 2026-03-01
- Cobertura no intermediate: **100%**

## Nota sobre o NDVI no modelo v5
 
Após análise SHAP no treinamento do LightGBM v5, NDVI e EVI apresentaram
importância < 1% em ambos os municípios — foram removidos do modelo final
(ver ADR-021). A fonte MODIS permanece ativa no pipeline pois o sinal pode
ser relevante em horizontes temporais diferentes ou com dados de resolução
maior (MOD13Q1 — 250m, quinzenal).
 
## Consequências
 
- Dados de vegetação 100% automatizados e atualizados mensalmente
- Elimina dependência de interface web manual (GEE)
- Cobertura histórica completa 2018–2025 disponível imediatamente
- Compatível com premissa de custo zero
## Referências
 
- Huete et al. (2002) — EVI vs NDVI em vegetação tropical densa
- Sebastianelli et al. (2024, Scientific Reports) — MODIS MOD13A3
  para modelos preditivos de dengue no Brasil
 