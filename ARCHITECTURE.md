# Arquitetura — Dengue MT

> Documentação técnica da arquitetura de dados, modelos e infraestrutura do sistema preditivo de surtos de dengue em Cuiabá e Várzea Grande/MT.

---

## Visão Geral

```text
FONTES PÚBLICAS          INGESTÃO (src/ingestion/)    TRANSFORMAÇÃO        SAÍDA
─────────────────────────────────────────────────────────────────────────────────
InfoDengue API      →    infodengue.py            →   dbt staging     →   Silver
NASA POWER API      →    nasa_power.py            →   dbt intermediate →  Gold v5
NOAA ONI Index      →    oni.py                   →   dbt marts       →   HF Hub
Google Trends       →    trends.py                →
MODIS AppEEARS      →    modis.py                 →
                                                          ↓
                                              LightGBM v5 (Prefect)
                                                          ↓
                                    ┌─────────────────────┴──────────────────────┐
                                    ↓                                            ↓
                            Dashboard Streamlit                          API REST FastAPI
                         dengue-mt-ifmt.streamlit.app
```

---

## Fluxo Semanal (domingo 06h Cuiabá — GitHub Actions)

```text
1. INGESTÃO (src/ingestion/ — responsabilidade única Bronze)
   InfoDengue API  ──→  data/bronze/infodengue/
   NASA POWER API  ──→  data/bronze/nasa_power/
   NOAA ONI        ──→  data/bronze/oni/
   Google Trends   ──→  data/bronze/trends/
   MODIS AppEEARS  ──→  data/bronze/modis/

2. TRANSFORMAÇÃO (dbt-core + DuckDB)
   dbt run → staging → intermediate → marts
   PASS=9 modelos | PASS=62 testes declarativos

3. EXPORTAÇÃO
   scripts/exportar_gold.py
   Gold local ──→ HF Hub (snapshot datado + latest)

4. MONITORAMENTO (src/tasks/drift.py)
   Últimas 26 SE ──→ Wasserstein distance ──→ drift score
   MAE > 25.0 ou R² < 0.75 ──→ retreino

5. RETREINO (src/tasks/retreino.py) — quando necessário
   Gold v5 ──→ TimeSeriesSplit 5 folds ──→ novo modelo
   pytest testes ──→ promoção ou rollback

6. DASHBOARD
   app/dashboard.py lê Gold do HF Hub ──→ previsões atualizadas
```

---

## Arquitetura Medalhão

### Bronze — Dados Brutos (Local)

Cópia fiel e imutável dos dados exatamente como vieram da fonte. Nunca modificado após ingestão. Responsabilidade: `src/ingestion/`.

| Fonte | Arquivo Bronze | Período |
|---|---|---|
| InfoDengue API | `data/bronze/infodengue/infodengue_{municipio}_{ano}.parquet` | 2018→2026 |
| NASA POWER API | `data/bronze/nasa_power/nasa_power_{municipio}_{ano}.parquet` | 2018→2026 |
| NOAA ONI | `data/bronze/oni/oni_index_latest.parquet` | 1950→atual |
| Google Trends | `data/bronze/trends/trends_dengue_latest.parquet` | últimos 90d |
| Google Trends (hist.) | `data/bronze/trends/trends_dengue_historico_2018_2025.parquet` | 2018→2025 |
| MODIS MOD13A3 | `data/bronze/modis/modis_ndvi_evi_latest.parquet` | 2018→atual |

### Silver — Dados Padronizados (dbt staging)

Dados validados, renomeados e com testes declarativos. Responsabilidade: `dengue_mt_dbt/models/staging/`.

| Modelo dbt | Transformações principais | Testes |
|---|---|---|
| `stg_infodengue` | epoch_ms→date, normalização SE domingo, dedup por GROUP BY | 11 |
| `stg_nasa_power` | data_str→date, -999→NULL, agrega diário→SE | 12 |
| `stg_oni` | trimestral→semanal via generate_series | 5 |
| `stg_gee` | mensal→semanal via generate_series | 4 |
| `stg_trends` | lag 7d anti-leakage | 3 |
| `stg_trends_historico` | overlapping windows normalizadas | 4 |
| `stg_modis` | escala ÷10000, cross join SE × município | 8 |

Total staging: PASS=45 WARN=0 ERROR=0

### Intermediate — Joins entre Fontes (dbt intermediate)

Join central de todas as fontes por `(municipio_id, data_se)`. Responsabilidade: `dengue_mt_dbt/models/intermediate/`.

| Modelo | Âncora | Join | Cobertura |
|---|---|---|---|
| `int_dengue_mt` | InfoDengue | LEFT JOIN NASA, ONI, Trends histórico, MODIS | 100% todas as fontes |

Resultado: 416 SE × 2 municípios | 2018-01-07 → 2025-12-28

### Gold — Dataset de Features ML (dbt marts + HF Hub)

Dataset pronto para treino com lags epidemiológicos anti-leakage. Responsabilidade: `dengue_mt_dbt/models/marts/`.

Arquivo: `data/gold/dataset_features_v5_latest.parquet`
Publicado em: `edyestatistica/dengue-mt-medallion` (HF Hub)

| Grupo | Features | Lags aplicados |
|---|---|---|
| Target | `casos_confirmados`, `casos_estimados`, `incidencia_100k` | — |
| Epidemiológico | `rt_index`, `nivel_alerta`, `receptivo`, `transmissao`, `prob_rt_maior_1` | lag 1 SE |
| Temperatura ERA5 | `temp_media`, `temp_max`, `temp_min` | lag 1-4 SE |
| Umidade ERA5 | `umidade_media` | lag 1-2 SE |
| NASA POWER | `precipitacao_total`, `radiacao_mj`, `umidade_nasa` | lag 1-4 SE |
| Médias móveis | `temp_mm4`, `temp_mm8`, `precip_acum4`, `precip_acum8`, `casos_mm4` | — |
| ONI/ENSO | `oni_index`, `fase_enso_num` | lag 4-8 SE |
| MODIS | `ndvi`, `evi` | lag 2-4 SE |
| Trends | `trends_dengue` | lag 1-2 SE |
| Autoregressivo | `casos_confirmados` | lag 1-4 SE |

Total: 54 features × 824 registros (412 SE × 2 municípios)

---

## Pipeline dbt

```text
dengue_mt_dbt/
├── macros/
│   └── cast_date.sql          ← 4 macros: cast_date, cast_epoch_ms, inicio_se, primeiro_domingo
├── models/
│   ├── staging/               ← Bronze → Silver (7 modelos, materialized=view)
│   │   ├── infodengue/        stg_infodengue.sql + .yml
│   │   ├── nasa_power/        stg_nasa_power.sql + .yml
│   │   ├── oni/               stg_oni.sql + .yml
│   │   ├── trends/            stg_trends.sql + stg_trends_historico.sql + .yml
│   │   ├── gee/               stg_gee.sql + .yml
│   │   └── modis/             stg_modis.sql + .yml
│   ├── intermediate/          ← Joins entre fontes (1 modelo, materialized=table)
│   │   └── int_dengue_mt.sql + .yml
│   └── marts/                 ← Gold final para ML (1 modelo, materialized=table)
│       └── mart_dengue_features.sql + .yml
├── packages.yml               ← dbt_utils 1.3.3
└── dbt_project.yml            ← vars: bronze_path, data_inicio=2018-01-01, data_fim=2025-12-31
```

Comandos:

```bash
cd dengue_mt_dbt
dbt deps         # instala dbt_utils
dbt run          # executa todos os modelos — PASS=9
dbt test         # valida qualidade — PASS=62
```

---

## Stack Tecnológica

| Camada | Tecnologia | Justificativa |
|---|---|---|
| Ingestão | Python + Prefect 3.x | Pipelines dinâmicos, free tier |
| Transformação | dbt-core 1.11 + DuckDB 1.10 | SQL versionado, testes declarativos, custo zero |
| Formato | Parquet | Compressão eficiente, tipagem forte |
| Modelo | LightGBM v5 | Lida com NaN nativamente, retreino automático |
| Validação | TimeSeriesSplit 5 folds | Evita data leakage temporal |
| Drift monitoring | Wasserstein distance | Normalizada por feature, 3 níveis acionáveis |
| Storage | Hugging Face Hub | Gratuito, ilimitado público |
| Dashboard | Streamlit Community Cloud | Gratuito, online |
| MLflow | SQLite local | Versionamento formal de experimentos |
| CI/CD | GitHub Actions | Execução automática domingo 06h Cuiabá |

> **Custo total de infraestrutura: R$ 0,00**

---

## Fontes de Dados

| Fonte | Dados | Período | Granularidade original |
|---|---|---|---|
| InfoDengue API | Casos + nowcast + Rt + clima ERA5 | 2018→atual | Semanal (SE) |
| NASA POWER API | Temperatura, precipitação, radiação, umidade | 2018→atual | Diária → agrega SE |
| NOAA ONI | El Niño/La Niña | 1950→atual | Trimestral → expande SE |
| Google Trends | Interesse "dengue" BR-MT | 2018→atual | Semanal |
| MODIS MOD13A3 | NDVI e EVI 1km | 2018→atual | Mensal → expande SE |

---

## Métricas do Modelo

| Métrica | v5 (Gold v5, 2018-2025) |
|---|---|
| MAE | 9.7 ± 6.2 casos/semana |
| R² | 0.741 ± 0.081 (TimeSeriesSplit 5 folds) |
| Features | 54 |
| Período treino | 2018-2025 |

> **Nota acadêmica:** R²=0.741 ± 0.081 (TimeSeriesSplit 5 folds, Gold v5) é a métrica oficial para publicação. Ver [ADR-006](reports/adr/006-metrica-oficial-timeseriessplit.md) para justificativa da escolha metodológica.

---

## Monitoramento de Drift

Janela de avaliação: últimas 26 SE. Referência: 52 SE anteriores.

| Nível | Score Wasserstein | Ação |
|---|---|---|
| Normal | < 0.3 | Pipeline normal |
| Moderado | 0.3 – 0.6 | Retreino com params padrão |
| Crítico | >= 0.6 | Retreino conservador obrigatório |

---

## Reprodutibilidade

```bash
git clone https://github.com/ediney-magalhaes/dengue-mt.git
cd dengue-mt
conda create -n dengue-mt python=3.11 -y
conda activate dengue-mt
pip install -r requirements.txt

# Executar pipeline dbt completo
cd dengue_mt_dbt
dbt deps && dbt run && dbt test

# Exportar Gold para HF Hub
cd ..
python scripts/exportar_gold.py

# Rodar dashboard
streamlit run app/dashboard.py
```

---

## Roadmap

| Versão | Data | Status | Entregas |
|---|---|---|---|
| v1.0–v1.4 | Mar-Abr/2026 | Concluído | Pipeline completo, dashboard, CI/CD, MLflow |
| v2.0-dev | Abr/2026 | Em desenvolvimento | dbt + DuckDB, MODIS, Trends histórico, Gold v5 |
| v2.0 | Mai/2026 | Planejado | LightGBM v5, pipeline Prefect atualizado, merge main |
| v2.1 | Jul/2026 | Planejado | Relatório extensionista IFMT, artigo SENIC 2026 |

---

*IFMT — Projeto Extensionista 2026*
*Ediney Magalhães*
*Dashboard: https://dengue-mt-ifmt.streamlit.app*
*Dataset: https://huggingface.co/datasets/edyestatistica/dengue-mt-medallion*