# ADR-027: IDW Dinâmico — Distribuição Espacial de Previsões por Bairro

**Data:** 2026-04-30

**Status:** Aceito — implementação do ADR-022

**Revisado:** 2026-05-01 — correção de 3 bugs críticos (commit 62)

---

## Contexto

O ADR-022 definiu a arquitetura IDW dinâmica para distribuir previsões
municipais por bairro. Este ADR documenta a implementação concreta e
as correções aplicadas após a primeira versão apresentar resultados
incorretos no dashboard.

## Decisão

### Cadeia de dados implementada
```
LightGBM v5 (granularidade municipal)
→ previsão SE+1→SE+4 com expm1() — ADR-024
↓
IDW distribuidor espacial (mass-preserving)
→ pesos brutos: Σ(casos_historicos / distancia_km²) por bairro
→ frações normalizadas por município em runtime
→ SIRGAS 2000 UTM zona 21S (EPSG:31981) para centroides
↓
143 bairros × 4 horizontes
→ Cuiabá: 119 bairros | Várzea Grande: 24 bairros
↓
Limiares adaptativos percentílicos (P60/P75/P85/P95)
→ calculados por município sobre valores IDW distribuídos
→ embutidos no GeoJSON como metadados (fonte única de verdade)
↓
external/previsao_bairros_latest.geojson → HF Hub
↓
Dashboard — choropleth Folium dinâmico
→ limiares lidos do GeoJSON, nunca hardcoded no dashboard
```
### Propriedade pycnophylactic (conservação de massa)
```
Σ casos_bairro_i (município X, horizonte H) = previsao_municipal_X_H
```

Garantida pela normalização das frações IDW por município:
`fracao_bairro = score_bruto_bairro / Σ scores_brutos_municipio`
Referência: Opasnet (2014) — Spatial disaggregation mass-preserving.

### Limiares adaptativos percentílicos

Classificação de risco por bairro usa limiares calculados sobre a
distribuição real de valores IDW de cada município, recalculados
a cada execução semanal:

| Nível       | Condição       |
|-------------|----------------|
| Muito Alto  | > P95          |
| Alto        | P85 – P95      |
| Moderado    | P75 – P85      |
| Baixo       | P60 – P75      |
| Muito Baixo | ≤ P60          |

**Por que percentis e não thresholds fixos:** thresholds fixos
(ex: >10 casos = Alto) calibrados para picos sazonais produzem
mapas monocromáticos ("tudo Muito Baixo") fora da estação chuvosa,
tornando o produto inútil para vigilância continuada. Percentis
adaptativos garantem distribuição visual informativa em qualquer
período do ano.

Referência: CDC/OPAS (2024) — epidemic alert thresholds via
negative binomial percentiles.

### Scripts implementados

**`scripts/calibrar_pesos_idw.py`** — execução anual
- Baixa shapefile IBGE CD2022 (143 bairros)
- Carrega 191 UBS do `score_risco_v2.parquet`
- Calcula centroides em EPSG:31981 (métrico) → EPSG:4326
- Score bruto = `Σ(casos_historicos / distancia_km²)` por bairro
- **NÃO normaliza** — armazena scores brutos (ratio max/min = 1315x)
- Publica `pesos_idw_ubs.json` + `bairros_cuiaba_vg.geojson` no HF Hub

**`scripts/gerar_previsao_bairros.py`** — execução semanal
- Carrega pesos brutos e bairros do HF Hub
- Normaliza frações por município em runtime (`calcular_fracoes_idw`)
- Gera previsão municipal via LightGBM com `expm1()`
- Distribui pelos bairros via IDW mass-preserving
- Calcula limiares adaptativos P60/P75/P85/P95 por município
- Classifica risco por bairro
- Embute limiares no GeoJSON como metadados
- Publica `previsao_bairros_latest.geojson` no HF Hub

### Dados publicados no HF Hub

| Arquivo | Frequência | Conteúdo |
|---|---|---|
| `external/pesos_idw_ubs.json` | Anual | Scores IDW brutos por bairro |
| `external/bairros_cuiaba_vg.geojson` | Anual | Polígonos 143 bairros |
| `external/previsao_bairros_latest.geojson` | Semanal | Previsão × 4 horizontes + limiares |

## Bugs corrigidos no commit 62

Três problemas detectados na primeira versão (commit 61) que
produziam resultados incorretos no mapa:

### Bug 1: codigo_municipio 6 vs 7 dígitos

`score_risco_v2.parquet` usa código IBGE com 6 dígitos (510340),
enquanto o shapefile IBGE CD2022 usa 7 dígitos (5103403). O join
entre UBS e bairros retornava zero matches silenciosamente.

**Correção:** mapeamento explícito em `calibrar_pesos_idw.py`:
```python
MAP_MUNICIPIO = {'510340': '5103403', '510840': '5108402'}
```

### Bug 2: normalização no nível errado

A versão original normalizava pesos IDW dentro de cada bairro
(dividindo pelo total de contribuições daquele bairro). Isso
eliminava a diferenciação entre bairros — todos recebiam
frações semelhantes independente da proximidade a UBS de alto volume.

**Correção:** scores brutos armazenados em `pesos_idw_ubs.json`.
Normalização acontece por município em `calcular_fracoes_idw()`:
`fracao = score_bairro / Σ scores_municipio`. Preserva a
diferenciação: bairros próximos a UBS com alto volume histórico
recebem fração proporcionalmente maior.

### Bug 3: limiares hardcoded para pico sazonal

Limiares fixos (>5 casos = Alto, >10 = Muito Alto) calibrados
para períodos de surto classificavam todos os bairros como
"Muito Baixo" em baixa temporada, tornando o mapa inútil.

**Correção:** limiares adaptativos percentílicos (P60/P75/P85/P95)
calculados dinamicamente sobre os valores distribuídos de cada
município. Recalculados a cada execução semanal.

## Resultado verificado (01/05/2026)

Com Gold atualizado até 2026-04-12:
- Cuiabá SE+1: 15 casos/semana
- Várzea Grande SE+1: 57 casos/semana
- Mapa título: "Distribuição Espacial de Casos Previstos"
- Limiares embutidos no GeoJSON, lidos dinamicamente pelo dashboard
- Dashboard sem nenhum threshold hardcoded

## O que NÃO muda

- Bronze, Staging, Intermediate, Marts — inalterados
- Modelo LightGBM v5 — inalterado
- IDW é camada exclusiva de pós-processamento para serving/dashboard

## Referências

- Shepard (1968) — método IDW original
- Cromley & McLafferty (2011) — GIS and Public Health
- Opasnet (2014) — Spatial disaggregation mass-preserving
- CDC/OPAS (2024) — Epidemic alert thresholds via negative binomial percentiles
- ADR-022 (decisão arquitetural IDW — proposta original)
- ADR-024 (log1p/expm1 transformação target)
