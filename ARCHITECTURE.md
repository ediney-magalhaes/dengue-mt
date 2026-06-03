# Arquitetura — Dengue MT

> Documentação técnica da arquitetura de dados, modelos e infraestrutura do sistema preditivo de surtos de dengue em Cuiabá e Várzea Grande/MT.

---

## Decisões Arquiteturais

| Decisão | Justificativa |
|---|---|
| dbt Core + DuckDB | ELT local sem custo — SQL versionado com testes declarativos e rastreabilidade por camada |
| Hugging Face Hub | Armazenamento gratuito, versionado e acessível pelo dashboard sem infraestrutura própria |
| LightGBM | Melhor desempenho com dados tabulares esparsos, lida com NaN nativamente, retreino rápido |
| Direct Multi-Step | Evita propagação de erro do forecasting recursivo — cada horizonte treina independentemente (Taieb & Hyndman 2014) |
| CQR (Conformal Quantile Regression) | Intervalos de predição calibrados com garantia de cobertura marginal finita (Romano et al. 2019) |
| SHAP (TreeExplainer) | Interpretabilidade fiel ao modelo — valores aditivos por feature, auditável por gestores de saúde |
| Champion-Challenger gate | Nenhum modelo vai a produção sem superar MAE+cobertura+pytest do modelo atual (Sculley et al. 2015) |
| GitHub Actions schedule | Orquestração semanal autônoma sem Prefect Cloud — custo zero, auditável via logs públicos |
---

## Visão Geral

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryTextColor': '#333', 'lineColor': '#666', 'fontSize': '14px'}}}%%
flowchart TB
    subgraph FONTES["🌐 Fontes Públicas"]
        ID[InfoDengue API]
        NP[NASA POWER API]
        ONI[NOAA ONI Index]
        GT[Google Trends]
        MD[MODIS AppEEARS]
    end

    subgraph BRONZE["🥉 Bronze — Ingestão"]
        B1[infodengue.py]
        B2[nasa_power.py]
        B3[oni.py]
        B4[trends.py]
        B5[modis.py]
    end

    subgraph DBT["⚙️ dbt + DuckDB"]
        STG[Staging — 7 modelos Silver]
        INT[Intermediate — joins validados]
        MART[Marts — Gold v5 · 54 features]
    end

    subgraph ML["🤖 Machine Learning"]
        LGB[Direct CQR — 12 modelos<br>4 horizontes × 3 quantis]
        DRIFT[Drift Monitor — Wasserstein]
    end

    subgraph IDW["🗺️ Distribuição Espacial"]
        PREV[Previsão Municipal SE+1→SE+4]
        DIST[IDW Mass-Preserving · 143 bairros × 191 UBS]
        LIM[Limiares Adaptativos P60/P75/P85/P95]
    end

    subgraph SAIDA["📊 Saída"]
        DASH[Dashboard Streamlit<br>dengue-mt-ifmt.streamlit.app]
        TEL[Alerta Telegram]
        HF[HF Hub — Artefatos]
    end

    ID --> B1
    NP --> B2
    ONI --> B3
    GT --> B4
    MD --> B5

    B1 --> STG
    B2 --> STG
    B3 --> STG
    B4 --> STG
    B5 --> STG

    STG --> INT --> MART

    MART --> LGB
    LGB --> DRIFT
    LGB --> PREV
    PREV --> DIST --> LIM --> DASH

    DRIFT --> TEL
    MART --> HF
    LGB --> HF

    style FONTES fill:#e8f4f8,stroke:#2196F3
    style BRONZE fill:#fff3e0,stroke:#FF9800
    style DBT fill:#f3e5f5,stroke:#9C27B0
    style ML fill:#e8f5e9,stroke:#4CAF50
    style IDW fill:#fce4ec,stroke:#E91E63
    style SAIDA fill:#e0f2f1,stroke:#009688
```

---

## Fluxo Semanal (domingo 06h Cuiabá — GitHub Actions)

```text
1. RESTAURAÇÃO (scripts/restore_artifacts_hf.py)
   HF Hub ──→ Bronze local (40 arquivos, SHA256 verificado)
   HF Hub ──→ Gold latest + modelo latest

2. INGESTÃO (src/ingestion/ — responsabilidade única Bronze)
   InfoDengue API  ──→  data/bronze/infodengue/
   NASA POWER API  ──→  data/bronze/nasa_power/
   NOAA ONI        ──→  data/bronze/oni/
   Google Trends   ──→  data/bronze/trends/
   MODIS AppEEARS  ──→  data/bronze/modis/ (skip se já existe)

3. PUBLICAÇÃO BRONZE (src/tasks/publicacao.py)
   Bronze local ──→ HF Hub (incremental SHA256, manifesto rastreável)

4. TRANSFORMAÇÃO (dbt-core + DuckDB)
   dbt run → staging → intermediate → marts
   dbt test → PASS=59 testes declarativos
   data_fim passado dinamicamente via --vars (ADR-026)

5. EXPORTAÇÃO (ADR-032)
   DuckDB (mart_dengue_features) ──→ data/gold/*.parquet
   Gold local ──→ HF Hub (snapshot datado + latest)

5b. TREINO DIRECT CQR (src/tasks/treinar_direto_cqr.py)
    Gold v5 ──→ 12 modelos (4 horizontes × 3 quantis q05/q50/q95)
    Calibração conformal ──→ cobertura ~90% garantida
    Modelos salvos em models/ + metadata JSON (Challenger)

5c. GATE CHAMPION-CHALLENGER (src/tasks/retreino.py — ADR-035)
    Challenger vs Champion (direct_cqr_metadata.json atual)
    Critério 1: MAE[h] novo ≤ MAE[h] atual × 1.10 — para h ∈ {1,2,4,8}
    Critério 2: cobertura_calibrada[h] ≥ 0.85 — para h ∈ {1,2,4,8}
    Critério 3: pytest 21 testes passando
    ✅ Aprovado  ──→ Etapa 6 (publicação ativada)
    ❌ Reprovado ──→ Champion mantido + alerta Telegram (publicação bloqueada)
    Referências: Sculley et al. 2015; Romano et al. 2019; García Crespi et al. 2025

6. DISTRIBUIÇÃO ESPACIAL (scripts/gerar_previsao_bairros.py)
    ⚠️  Só executa se gate aprovado
   Previsão municipal ──→ IDW mass-preserving ──→ 143 bairros
   Limiares adaptativos P60/P75/P85/P95 por município
   GeoJSON ──→ HF Hub (previsao_bairros_latest.geojson)

7. MONITORAMENTO (src/tasks/drift.py)
   Últimas 26 SE ──→ Wasserstein distance ──→ drift score
   MAE > 25.0 ou R² < 0.75 ──→ retreino

8. RETREINO (src/tasks/retreino.py) — quando necessário
   Gold v5 ──→ TimeSeriesSplit 5 folds ──→ novo modelo
   pytest 21 testes (10 pipeline + 11 Direct CQR) ──→ promoção ou rollback

9. ALERTA + RELATÓRIO
   Telegram ──→ status do pipeline
   Relatório ──→ HF Hub (execucao_latest.md)

10. DASHBOARD
    dengue-mt-ifmt.streamlit.app lê artefatos do HF Hub
```

---

## Arquitetura Medalhão

### Bronze — Dados Brutos (Local + HF Hub)

Cópia fiel e imutável dos dados exatamente como vieram da fonte. Nunca modificado após ingestão. Publicado incrementalmente no HF Hub com SHA256. Responsabilidade: `src/ingestion/`.

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

### Intermediate — Joins entre Fontes (dbt intermediate)

Join central de todas as fontes por `(municipio_id, data_se)`. Responsabilidade: `dengue_mt_dbt/models/intermediate/`.

| Modelo | Âncora | Join | Cobertura |
|---|---|---|---|
| `int_dengue_mt` | InfoDengue | LEFT JOIN NASA, ONI, Trends histórico, MODIS | 100% todas as fontes |

Resultado: 428 SE × 2 municípios | 2018-01-07 → 2026-04-12

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

Total: 54 features × 856 registros (428 SE × 2 municípios)

---

## Distribuição Espacial — IDW Dinâmico

Camada de pós-processamento exclusiva do dashboard. Não afeta o modelo.

```text
LightGBM v5 (previsão municipal)
       ↓
IDW Mass-Preserving (Shepard 1968)
  scores brutos: Σ(casos_historicos / distancia_km²) por bairro
  frações normalizadas por município em runtime
       ↓
143 bairros × 4 horizontes (SE+1→SE+4)
  Cuiabá: 119 bairros | Várzea Grande: 24 bairros
       ↓
Limiares adaptativos (CDC/OPAS 2024)
  P60 / P75 / P85 / P95 por município
  recalculados a cada execução semanal
       ↓
previsao_bairros_latest.geojson → HF Hub → Dashboard
```

Propriedade pycnophylactic: Σ casos_bairro = previsão_municipal (conservação de massa).

Scripts: `calibrar_pesos_idw.py` (anual) + `gerar_previsao_bairros.py` (semanal).
ADRs: [022](reports/adr/022-idw-mapa-risco-bairro-dashboard.md), [027](reports/adr/027-idw-dinamico-previsao-bairros.md).

---

## Pipeline dbt

```text
dengue_mt_dbt/
├── macros/
│   └── cast_date.sql          ← 4 macros: cast_date, cast_epoch_ms, inicio_se, primeiro_domingo
├── models/
│   ├── staging/               ← Bronze → Silver (7 modelos, materialized=view)
│   ├── intermediate/          ← Joins entre fontes (1 modelo, materialized=table)
│   └── marts/                 ← Gold final para ML (1 modelo, materialized=table)
├── packages.yml               ← dbt_utils 1.3.3
└── dbt_project.yml            ← vars: bronze_path, data_inicio=2018-01-01, data_fim=2099-12-31
```

```bash
dbt run  → PASS=8  WARN=0 ERROR=0
dbt test → PASS=59 WARN=0 ERROR=0
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
| Dashboard | Streamlit Community Cloud | Gratuito, online, 6 abas |
| Assets estáticos | `app/assets/shap/` | PNGs SHAP servidos localmente — sem recálculo em runtime |
| MLflow | SQLite local | Versionamento formal de experimentos |
| CI/CD | GitHub Actions | Execução automática domingo 06h Cuiabá |
| MODIS mensal | GitHub Actions cron dia 5/mês | AppEEARS isolado — não impacta pipeline semanal |
| Keep-alive | GitHub Actions cron 4h + Playwright | Chromium headless renderiza página de fato (curl insuficiente para SPAs) |
| Intervalos | MAPIE 1.4 (CQR) | Conformal prediction, distribution-free |
| Interpretabilidade | SHAP 0.51 (TreeExplainer) | Importância por feature, dependence plots |

> **Custo total de infraestrutura: R$ 0,00**

---

## Métricas do Modelo

### Previsão pontual (LightGBM v5)

| Métrica | Valor |
|---|---|
| MAE | 9.7 ± 6.2 casos/semana (TimeSeriesSplit 5-fold) |
| R² | 0.741 ± 0.081 (TimeSeriesSplit 5-fold) |
| R² operacional | 0.861 (drift 26 SE) |
| MAE operacional | 6.67 casos/semana |
| Features | 54 |
| Período treino | 2018–2026 |

### Intervalos de predição (CQR — Romano et al., NeurIPS 2019)

| Método | Cobertura | Largura média |
|---|---|---|
| CQR 90% | 91.5% ✅ | 129.0 casos |
| CQR 80% | 69.8% | 63.7 casos |
| Baseline fixo 90% | 71.3% | 88.2 casos |

### Interpretabilidade (SHAP — Lundberg & Lee, 2017)

TreeSHAP (Lundberg et al., Nature MI 2020) calculado sobre modelos q50
de cada horizonte Direct CQR. Script: `notebooks/backtesting/04_shap_direct_cqr.py`.
Atualizar após cada retreino do pipeline semanal.

| Horizonte | Feature dominante    | \|SHAP\| | Interpretação          |
|-----------|----------------------|----------|------------------------|
| h=1 SE    | casos_mm4            | 0.6923   | Modelo reativo         |
| h=2 SE    | casos_mm4            | 0.6681   | Momentum ainda domina  |
| h=4 SE    | casos_mm4            | 0.4129   | Transição estrutural   |
| h=8 SE    | notif_acum_ano_lag1  | 0.3885   | Modelo prospectivo     |

Padrão: momentum autoregressivo domina horizontes curtos; sazonalidade
histórica e precipitação acumulada (`precip_acum8`) dominam h=8.
Consistente com ciclo biológico do *Aedes aegypti* (~2-3 semanas)
e com Taieb & Hyndman (2014).

Artefatos: `reports/shap/direct_cqr/` (33 figuras + 13 CSVs)
Dashboard: aba "🔍 Explicabilidade" — interativa com sidebar (horizonte + município)

---

## Monitoramento de Drift

Janela de avaliação: últimas 26 SE. Referência: 52 SE anteriores.

| Nível | Score Wasserstein | Ação |
|---|---|---|
| Normal | < 0.3 | Pipeline normal |
| Moderado | 0.3 – 0.6 | Retreino com params padrão |
| Crítico | >= 0.6 | Retreino conservador obrigatório |

---

## Roadmap

| Versão | Data | Status | Entregas |
|---|---|---|---|
| v0.1–v1.4 | Mar-Abr/2026 | ✅ | Pipeline completo, dashboard, CI/CD, MLflow |
| v2.0 | Abr/2026 | ✅ | dbt + DuckDB, MODIS, Gold v5, LightGBM v5 |
| v2.1 | Mai/2026 | ✅ | IDW dinâmico, dashboard v5, deploy produção |
| v2.2 | Mai/2026 | ✅ | EDA Gold v5 (17 figuras), backtesting expanding window, baselines |
| v2.3 | Mai/2026 | ✅ | Intervalos CQR (Romano et al. 2019), SHAP atualizado (4 figuras) |
| v2.4 | Mai/2026 | ✅ | Direct CQR 12 modelos, bandas 90%, fix Gold DuckDB (ADR-032) |
| v2.4.2 | Mai/2026 | ✅ | Keep-alive dashboard, Node.js 24 migration (checkout@v5, cache@v5) |
| v2.4.3 | Mai/2026 | ✅ | Keep-alive Playwright (curl não acordava SPA), seletor resiliente |
| v2.5 | Jun/2026 | ✅ | SHAP Direct CQR (4 horizontes × 2 municípios), aba Explicabilidade dashboard, ADR-034 |
| v2.6 | Jun/2026 | ✅ | Gate Champion-Challenger Direct CQR (ADR-035) — MAE + cobertura CQR + pytest por horizonte |

---

*IFMT — Projeto Extensionista 2026*
*Ediney Magalhães*
*Dashboard: https://dengue-mt-ifmt.streamlit.app*
*Dataset: https://huggingface.co/datasets/edyestatistica/dengue-mt-medallion*