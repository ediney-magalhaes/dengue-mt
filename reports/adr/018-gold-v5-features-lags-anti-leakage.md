# ADR-018 — Gold v5: Features, Lags Epidemiológicos e Anti-Leakage
 
**Status:** Aceito  
**Data:** 18/04/2026  
**Tema:** Feature Engineering / Modelagem
 
---
 
## Contexto
 
Versões anteriores do Gold incluíam indicadores epidemiológicos calculados
com base nos casos da própria semana epidemiológica — `rt_index`,
`nivel_alerta`, `receptivo`, `transmissao` sem lag. Isso causava
**data leakage silencioso**: o modelo aprendia com informações que não
estariam disponíveis no momento real da previsão, gerando métricas
artificialmente otimistas.
 
Adicionalmente, os lags climáticos não seguiam a literatura — eram
aplicados de forma ad-hoc sem fundamentação nos tempos de resposta
biológicos do vetor.
 
## Decisão
 
Construir `mart_dengue_features.sql` com lags fundamentados na literatura
e todos os indicadores epidemiológicos aplicados com mínimo de 1 SE de lag:
 
### Features do Gold v5 por grupo
 
| Grupo | Features | Lags aplicados | Referência |
|-------|----------|---------------|------------|
| Target | `casos_confirmados`, `casos_estimados`, `incidencia_100k` | — | — |
| Epidemiológico | `rt_index`, `nivel_alerta`, `receptivo`, `transmissao` | lag 1 SE | Codeco et al. 2018 |
| Temperatura ERA5 | `temp_media`, `temp_max`, `temp_min` | lag 1–4 SE | Hii et al. 2012 |
| Umidade ERA5 | `umidade_media` | lag 1–2 SE | Hii et al. 2012 |
| NASA POWER | `precipitacao_total`, `radiacao_mj`, `umidade_nasa` | lag 1–4 SE | Hii et al. 2012 |
| Médias móveis | `temp_media_mm4/mm8`, `precip_acum4/acum8` | — | — |
| ONI/ENSO | `oni_index`, `fase_enso_num` | lag 4–8 SE | McPhaden et al. 2006 |
| MODIS | `ndvi`, `evi` | lag 2–4 SE | Sebastianelli et al. 2024 |
| Trends | `trends_dengue` | lag 1–2 SE | Althouse et al. 2011 |
| Autoregressivo | `casos_confirmados`, `casos_mm4` | lag 1–4 SE | — |
 
**Justificativa dos lags climáticos (Hii et al. 2012):**
- Temperatura lag 2–4 SE: tempo de desenvolvimento larval do *Aedes aegypti*
  é de 7–14 dias; adultos emergem 1–2 semanas após — total ~3–4 SE
- Precipitação lag 1–3 SE: chuva cria criadouros imediatamente,
  mas mosquitos adultos levam 1–2 semanas para emergir e transmitir

**Justificativa do ONI lag 4–8 SE:**
- El Niño/La Niña afeta padrões de chuva regionais com defasagem de
  1–2 meses — efeito indireto via precipitação acumulada
## Resultado do Gold v5
 
- **54 features** × 412 SE × 2 municípios = **824 registros**
- Período: 2018-02-04 → 2025-12-28
- Primeiras 4 SE removidas (lag4 insuficiente para features autoregressivas)
- HF Hub: `edyestatistica/dengue-mt-medallion/gold/dataset_features_v5_latest.parquet`
- Testes dbt: `PASS=7 WARN=0 ERROR=0`

## Consequências
 
- Leakage operacional eliminado — todas as features disponíveis no momento
  real de uma previsão
- Lags fundamentados em literatura defensáveis em revisão acadêmica
- 4 semanas iniciais sacrificadas pelo lag4 — trade-off documentado e aceito

## Referências
 
- Hii et al. (2012) — temperatura lag 2–4 SE, precipitação lag 1–3 SE
- Codeco et al. (2018) — nowcasting InfoDengue, lags epidemiológicos
- McPhaden et al. (2006) — ENSO e doenças tropicais, lag 4–8 SE
- Sebastianelli et al. (2024) — MODIS NDVI lag 2–4 SE
- Althouse et al. (2011) — Google Trends lag 1–2 SE
 