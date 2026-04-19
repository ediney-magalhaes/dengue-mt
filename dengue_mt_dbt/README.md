# dengue_mt_dbt — Pipeline dbt + DuckDB

> Projeto dbt responsável pelas transformações Bronze → Silver → Gold
> do sistema preditivo de surtos de dengue em Cuiabá e Várzea Grande/MT.
> Parte do projeto extensionista IFMT — Dengue MT.

---

## Visão Geral

Este projeto dbt implementa a camada de transformação da arquitetura medalhão:

```text
Bronze (Parquet local)
    ↓
staging (Silver — views)
    ↓
intermediate (joins — table)
    ↓
marts (Gold ML — table)
    ↓
data/gold/dataset_features_v5_latest.parquet
```

---

## Estrutura

```text
dengue_mt_dbt/
├── macros/
│   └── cast_date.sql              ← 4 macros de padronização de datas
├── models/
│   ├── staging/                   ← Bronze → Silver (7 modelos, views)
│   │   ├── sources.yml            ← fontes Bronze via read_parquet()
│   │   ├── infodengue/
│   │   │   ├── stg_infodengue.sql
│   │   │   └── stg_infodengue.yml
│   │   ├── nasa_power/
│   │   │   ├── stg_nasa_power.sql
│   │   │   └── stg_nasa_power.yml
│   │   ├── oni/
│   │   │   ├── stg_oni.sql
│   │   │   └── stg_oni.yml
│   │   ├── trends/
│   │   │   ├── stg_trends.sql
│   │   │   ├── stg_trends_historico.sql
│   │   │   └── stg_trends.yml
│   │   ├── gee/
│   │   │   ├── stg_gee.sql
│   │   │   └── stg_gee.yml
│   │   └── modis/
│   │       ├── stg_modis.sql
│   │       └── stg_modis.yml
│   ├── intermediate/              ← Joins entre fontes (1 modelo, table)
│   │   ├── int_dengue_mt.sql
│   │   └── int_dengue_mt.yml
│   └── marts/                     ← Gold final para ML (1 modelo, table)
│       ├── mart_dengue_features.sql
│       └── mart_dengue_features.yml
├── packages.yml                   ← dbt_utils 1.3.3
└── dbt_project.yml                ← variáveis: bronze_path, data_inicio, data_fim
```

---

## Macros

Arquivo `macros/cast_date.sql` — padronização de tipos DATE em todo o pipeline:

| Macro | Uso |
|---|---|
| `cast_date(column)` | Converte qualquer campo para DATE |
| `cast_epoch_ms(column)` | Timestamp milissegundos (BIGINT) → DATE — InfoDengue |
| `inicio_se(column)` | Calcula domingo da SE (Portaria SVS/MS nº 5/2010) |
| `primeiro_domingo(date_str)` | Primeiro domingo após uma data |

---

## Modelos

### Staging (Silver)

| Modelo | Fonte Bronze | Transformações principais | Testes |
|---|---|---|---|
| `stg_infodengue` | InfoDengue API | epoch_ms→date, normaliza SE domingo, dedup GROUP BY | 11 |
| `stg_nasa_power` | NASA POWER API | data_str→date, -999→NULL, agrega diário→SE | 12 |
| `stg_oni` | NOAA ONI | trimestral→semanal via generate_series | 5 |
| `stg_gee` | GEE Sentinel-2 | mensal→semanal via generate_series | 4 |
| `stg_trends` | Google Trends | lag 7d anti-leakage | 3 |
| `stg_trends_historico` | Trends overlapping windows | série histórica 2018→2025 normalizada | 4 |
| `stg_modis` | MODIS AppEEARS | escala ÷10000, cross join SE × município | 8 |

### Intermediate

| Modelo | Descrição |
|---|---|
| `int_dengue_mt` | Join central InfoDengue (âncora) LEFT JOIN todas as fontes por (municipio_id, data_se) |

Cobertura: 100% em todas as fontes | 416 SE × 2 municípios | 2018-01-07 → 2025-12-28

### Marts (Gold)

| Modelo | Descrição |
|---|---|
| `mart_dengue_features` | Dataset final para ML — 54 features com lags epidemiológicos anti-leakage |

Gold v5: 824 registros (412 SE × 2 municípios) | 2018-02-04 → 2025-12-28

---

## Variáveis do Projeto

Definidas em `dbt_project.yml`:

| Variável | Valor padrão | Descrição |
|---|---|---|
| `bronze_path` | `profiles.yml` | Caminho absoluto para `data/bronze/` |
| `data_inicio` | `2018-01-01` | Início do período de treino |
| `data_fim` | `2025-12-31` | Fim do período de treino |
| `municipios` | `[5103403, 5108402]` | Códigos IBGE Cuiabá + Várzea Grande |

---

## Como Usar

```bash
# Instalar dependências
dbt deps

# Executar todos os modelos
dbt run

# Executar com full-refresh (recria tabelas)
dbt run --full-refresh

# Executar camada específica
dbt run --select staging
dbt run --select intermediate
dbt run --select marts

# Rodar testes de qualidade
dbt test

# Rodar testes de uma camada
dbt test --select staging

# Compilar sem executar
dbt compile
```

---

## Resultados dos Testes
```
dbt run  → PASS=9  WARN=0 ERROR=0
dbt test → PASS=62 WARN=0 ERROR=0
```

---

## Decisões de Projeto

| Decisão | Justificativa |
|---|---|
| Filtro de período apenas no marts | Staging padroniza — não filtra. Marts define recorte temporal para ML |
| LEFT JOIN com âncora InfoDengue | Garante que o período é definido pelos casos — fontes climáticas completam |
| Trends histórico via overlapping windows | Scientific Data (Nature) 2026 — metodologia validada para Brasil |
| MODIS em vez de GEE | GEE sem automação — MODIS AppEEARS gratuito e automático |
| Lags no marts, não no intermediate | Intermediate preserva dados brutos — marts aplica feature engineering |

---

## Referências

- Codeco et al. 2018 — InfoDengue, SE brasileira
- Hii et al. 2012 — temperatura semanal + precipitação acumulada
- Sebastianelli et al. 2024 (Scientific Reports) — MODIS dengue Brasil
- Scientific Data (Nature) 2026 — overlapping windows Trends Brasil
- Portaria SVS/MS nº 5/2010 — Semana Epidemiológica brasileira

---

*IFMT — Projeto Extensionista 2026 | Ediney Magalhães*