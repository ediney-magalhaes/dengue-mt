# ADR-027: IDW Dinâmico — Distribuição Espacial de Previsões por Bairro

**Data:** 2026-04-30

**Status:** Aceito — implementação do ADR-022

---

## Contexto

O ADR-022 definiu a arquitetura IDW dinâmica. Este ADR documenta
a implementação concreta realizada em 30/04/2026.

## Decisão

### Cadeia de dados implementada
```
LightGBM v5 (granularidade municipal)
→ previsão SE+1→SE+4 com expm1() — ADR-024
↓
IDW distribuidor espacial (mass-preserving)
→ pesos calibrados: casos_historicos / distancia_km²
→ SIRGAS 2000 UTM zona 21S (EPSG:31981) para centroides
↓
143 bairros × 4 horizontes
→ Cuiabá: 119 bairros | Várzea Grande: 24 bairros
↓
external/previsao_bairros_latest.geojson → HF Hub
↓
Dashboard — choropleth Folium com slider SE+1→SE+4
```

### Propriedade pycnophylactic (conservação de massa)
```
Σ casos_bairro_i (município X, horizonte H) = previsao_municipal_X_H
```

Garantida pela normalização dos pesos IDW na calibração:
Σ peso_bairro_i = 1.0 por município.

Referência: Opasnet (2014) — Spatial disaggregation mass-preserving.

### Scripts implementados

**`scripts/calibrar_pesos_idw.py`** — execução anual
- Baixa shapefile IBGE CD2022 (143 bairros)
- Carrega 191 UBS do `score_risco_v2.parquet`
- Calcula centroides em EPSG:31981 (métrico) → EPSG:4326
- Peso = `casos_historicos / distancia_km²`
- Publica `pesos_idw_ubs.json` + `bairros_cuiaba_vg.geojson` no HF Hub

**`scripts/gerar_previsao_bairros.py`** — execução semanal
- Carrega pesos e bairros do HF Hub
- Gera previsão municipal via LightGBM com `expm1()`
- Distribui pelos bairros via IDW mass-preserving
- Publica `previsao_bairros_latest.geojson` no HF Hub

### Dados publicados no HF Hub

| Arquivo | Frequência | Conteúdo |
|---|---|---|
| `external/pesos_idw_ubs.json` | Anual | Pesos calibrados por UBS |
| `external/bairros_cuiaba_vg.geojson` | Anual | Polígonos 143 bairros |
| `external/previsao_bairros_latest.geojson` | Semanal | Previsão × 4 horizontes |

### Resultado verificado (30/04/2026)

Com Gold atualizado até 2026-04-12:
- Cuiabá SE+1: 15 casos/semana
- Várzea Grande SE+1: 57 casos/semana
- Coerente com pico sazonal março/abril observado nos dados reais

## O que NÃO muda

- Bronze, Staging, Intermediate, Marts — inalterados
- Modelo LightGBM v5 — inalterado
- IDW é camada exclusiva de pós-processamento para serving/dashboard

## Referências

- Shepard (1968) — método IDW original
- Cromley & McLafferty (2011) — GIS and Public Health
- Opasnet (2014) — Spatial disaggregation mass-preserving
- ADR-022 (decisão arquitetural IDW — proposta original)
- ADR-024 (log1p/expm1 transformação target)
