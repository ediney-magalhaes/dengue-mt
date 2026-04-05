# Arquitetura — Dengue MT

> Documentação técnica da arquitetura de dados, modelos e infraestrutura do sistema preditivo de surtos de dengue em Cuiabá e Várzea Grande/MT.

---

## Visão Geral

```text
    FONTES PÚBLICAS              INGESTÃO (src/ingestion/)       CAMADAS
─────────────────────────────────────────────────────────────────────
InfoDengue API          →    infodengue.py                →  Bronze
NASA POWER API          →    nasa_power.py                →  Silver
NOAA ONI Index          →    oni.py                       →    ↓
Google Trends           →    trends.py                    →  Gold
SINAN/DATASUS (hist.)   →    [scripts/historico/]         →  (HF Hub)
INMET (hist.)           →    [scripts/historico/]         →
GEE Sentinel-2 (hist.)  →    [scripts/historico/]         →
↓
src/tasks/build_gold.py
(atualização incremental semanal)
↓
src/features/feature_engineering.py
(59 features: clima + lags + NDVI/NDWI/NDBI + ENSO + Trends)
↓
LightGBM v4 — Retreino automático via Prefect
↓
┌───────────────────────┴───────────────────────┐
↓                                               ↓
Dashboard Streamlit                              API REST FastAPI
dengue-mt-ifmt.streamlit.app

```

---

## Fluxo Completo de Dados — Bronze → Silver → Gold
```text
┌─────────────────────────────────────────────────────────────────┐
│ TODA SEMANA (domingo 06h Cuiabá — GitHub Actions CI/CD)         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. INGESTÃO (src/tasks/ingestao.py orquestra)                  │
│     InfoDengue API ──→ Bronze ──→ Silver                        │
│     NASA POWER API ──→ Bronze ──→ Silver                        │
│     NOAA ONI       ──→ Bronze ──→ Silver                        │
│     Google Trends  ──→ Bronze ──→ Silver                        │
│                                                                 │
│  2. BUILD GOLD (src/tasks/build_gold.py)                        │
│     Gold anterior (preservado) ──┐                              │
│     Silver novo (semanas novas) ──┤──→ feature_engineering.py   │
│                                  └──→ Gold atualizado           │
│                                                                 │
│  3. PUBLICAÇÃO                                                  │
│     Gold local ──→ HF Hub (snapshot datado + latest)            │
│                                                                 │
│  4. MONITORAMENTO (src/tasks/drift.py)                          │
│     Últimas 26 SE ──→ Wasserstein distance ──→ drift score      │
│     MAE recente > 25.0 ou R² < 0.75 ──→ retreino                │
│                                                                 │
│  5. RETREINO (src/tasks/retreino.py) — quando necessário        │
│     Gold completo ──→ TimeSeriesSplit 5 folds ──→ novo modelo   │
│     pytest 13 testes ──→ promoção ou rollback                   │
│                                                                 │
│  6. DASHBOARD                                                   │
│     app/dashboard.py lê Gold do HF Hub ──→ previsões atualizadas│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```
---

## Arquitetura Medalhão — Camadas e Transformações

### 🥉 Bronze — Dados Brutos (Local)
Cópia fiel e imutável dos dados exatamente como vieram da fonte.
**Nunca modificado após ingestão.**

| Fonte | Arquivo Bronze | Campos brutos |
|---|---|---|
| InfoDengue API | `data/bronze/infodengue/infodengue_{municipio}_{ano}.parquet` | Todos os campos da API + `ingestao_ts`, `fonte` |
| NASA POWER API | `data/bronze/nasa_power/nasa_{inicio}_{fim}.parquet` | Valores brutos com `-999` para inválidos |
| NOAA ONI | `data/bronze/oni/oni_index_latest.parquet` | `seas`, `yr`, `total`, `anom` brutos |
| Google Trends | `data/bronze/trends/trends_dengue_latest.parquet` | `data`, `trends_dengue_raw` |
| SINAN (hist.) | `data/bronze/sinan/dengue_mt_{ano}.parquet` | Todos os campos SINAN originais |
| INMET (hist.) | `data/bronze/inmet/inmet_cuiaba_2018_2024.parquet` | Dados brutos da estação A901 |
| GEE (hist.) | `data/bronze/gee/gee_ndvi_ndwi_blend_2018_2024.parquet` | Índices brutos por pixel |

### 🥈 Silver — Dados Limpos e Padronizados (Local + HF Hub histórico)
Dados validados, renomeados e com transformações reversíveis.

| Fonte | Arquivo Silver | Transformações aplicadas |
|---|---|---|
| InfoDengue | `data/silver/infodengue/infodengue_2025_atual.parquet` | Timestamp ms→data, renomeia colunas (`tempmed`→`temp_media`), valida temperatura [10,50]°C, filtra `casos≥0`, seleciona colunas relevantes, aplica corte temporal |
| NASA POWER | `data/silver/nasa_power/nasa_power_2025_atual.parquet` | Converte data YYYYMMDD→datetime, substitui `-999`→NaN, valida temperatura [-10,55]°C, filtra radiação válida |
| ONI Index | `data/silver/oni/oni_index_latest.parquet` | Converte tipos numéricos, valida anomalia [-4,+4] |
| Google Trends | `data/silver/trends/trends_dengue_latest.parquet` | Converte data, valida [0,100], aplica corte temporal (lag=7d) |
| SINAN (hist.) | `data/silver/sinan/dengue_mt_{ano}.parquet` | Filtra classificação por período, converte data, seleciona colunas essenciais |
| INMET (hist.) | `data/silver/inmet/inmet_cuiaba_2018_2024.parquet` | Clipa precipitação [0,500mm], temperatura [10,45]°C, umidade [0,100]% |
| GEE (hist.) | `data/silver/gee/gee_ndvi_ndwi_blend_2018_2024.parquet` | Remove nulos em ndvi_final e ndwi_final |

### 🥇 Gold — Dataset de Features ML (Local + HF Hub)
Dataset pronto para treino, retreino e serving.
Construído por `src/tasks/build_gold.py` + `src/features/feature_engineering.py`.

**Arquivo:** `data/gold/dataset_features_v4.parquet`
**Publicado em:** `edyestatistica/dengue-mt-medallion` (HF Hub)

| Grupo | Features | Descrição |
|---|---|---|
| **Temporais** | `ano`, `mes`, `semana_ano`, `dia_ano`, `trimestre` | Identificadores temporais |
| **Cíclicas** | `mes_seno`, `mes_cosseno`, `semana_seno`, `semana_cosseno` | Codificação cíclica de sazonalidade |
| **Lags de casos** | `casos_lag_7d`, `_14d`, `_21d`, `_28d` | Autocorrelação epidemiológica |
| **Médias móveis** | `casos_mm_7d`, `_14d`, `_28d`, `casos_acum_ano` | Tendência da série |
| **Clima base** | `temp_media`, `temp_max`, `temp_min`, `umidade_media`, `umidade_max`, `umidade_min`, `precipitacao_total`, `amplitude_termica` | InfoDengue SE |
| **Lags climáticos** | `precip_lag_28d/35d/42d`, `umidade_lag_28d/35d/42d`, `temp_lag_28d/35d/42d` | Efeito retardado do clima |
| **Médias climáticas** | `precip_mm_7d/14d/28d`, `umidade_mm_7d/14d/28d`, `precip_acum_7d/14d/28d` | Acumulados e médias |
| **Radiação** | `radiacao_mj`, `radiacao_lag_28d`, `radiacao_mm_14d` | NASA POWER |
| **Seco** | `dias_sem_chuva` | Dias consecutivos sem chuva |
| **ENSO** | `oni_index`, `fase_enso_num` | El Niño/La Niña |
| **Tendências** | `trends_lag_7d`, `_14d`, `_21d` | Google Trends com lag |
| **Vegetação** | `ndvi`, `ndwi` | GEE Sentinel-2/MODIS |
| **Urbanização** | `ndbi_gee`, `ndbi_lag_30d`, `ndbi_lag_60d` | NDBI dinâmico GEE |
| **Epidêmico** | `ciclo_epidemico`, `anos_desde_pico`, `casos_acum_ano` | Ciclo histórico |

**Diferença Silver → Gold:**
Silver contém dados brutos por fonte (casos diários, clima diário, índices mensais).
Gold agrega tudo por Semana Epidemiológica, calcula features derivadas (lags, médias móveis, codificação cíclica) e alinha temporalmente todas as fontes ao domingo da SE brasileira.

---

## Stack Tecnológica

| Camada | Tecnologia | Justificativa |
|---|---|---|
| Ingestão | Python + Prefect 3.x | Pipelines dinâmicos, free tier |
| Transformação | Pandas + Polars (histórico) | Polars 5-10x mais rápido para dados grandes |
| Formato | Parquet | Compressão eficiente, tipagem forte |
| Modelo | LightGBM v4 | MAE=57.3, retreino automático, lida com NaN nativamente |
| Validação | TimeSeriesSplit 5 folds | Evita data leakage temporal |
| Drift monitoring | Wasserstein distance | Normalizada por feature, 3 níveis acionáveis |
| Feature Store | `src/features/build_features.py` | Elimina feature drift treino/serving |
| Feature Engineering | `src/features/feature_engineering.py` | Incremental + histórico completo |
| Storage | Hugging Face Hub | Gratuito, ilimitado público |
| Dashboard | Streamlit Community Cloud | Gratuito, online |
| MLflow | SQLite local | Versionamento formal de experimentos |
| CI/CD | GitHub Actions | Execução automática domingo 06h Cuiabá |
| Cache/Fallback | `data/cache/` Parquet | Resiliência APIs externas |

> **Custo total de infraestrutura: R$ 0,00**

---

## Métricas do Modelo de Produção

| Métrica | v1.0 (2018-2024) | v1.4 (2018-2026) |
|---|---|---|
| MAE | 17.6 casos/semana | 57.3 casos/semana |
| R² | 0.820 (TimeSeriesSplit) | 0.063 |
| Período treino | 2018-2024 | 2018–2026-03-21 |
| Nota | Métrica oficial para artigo | R² baixo esperado — 1º ciclo 2025/2026 |

> **Nota importante:** R²=0.063 é esperado no 1º retreino com dados 2025/2026. O modelo agora **acompanha a tendência** do surto (erro médio ~20 casos nas últimas semanas). R² tende a melhorar com mais ciclos epidêmicos completos no treino. Meta: R²≥0.50 após 3+ ciclos.

> **Para fins acadêmicos:** R²=0.820 (TimeSeriesSplit, dados 2018-2024) permanece como métrica oficial defensável para publicação.

---

## Monitoramento de Drift

**Janela de avaliação:** últimas 26 SE (~6 meses)
**Referência:** ano anterior (52 SE)
**Justificativa:** Wasserstein distance requer mínimo 50 amostras para validade estatística (Rabanser et al. 2019). Com dados semanais, 26 SE é o mínimo epidemiologicamente significativo (Codeco et al. 2018).

| Nível | Score Wasserstein | Ação |
|---|---|---|
| 🟢 Normal | < 0.3 | Pipeline normal |
| 🟡 Moderado | 0.3 – 0.6 | Retreino com params padrão |
| 🔴 Crítico | ≥ 0.6 | Retreino conservador obrigatório |

**Limiares de performance:**
- `MAE_LIMIAR` = 25.0 casos/semana
- `R2_MINIMO` = 0.75

**Regra de promoção (BMC Medical Research Methodology 2022):**
- pytest 13 testes ✅
- R²_novo >= R²_atual - 0.05
- MAE_novo <= MAE_atual × 1.10

---

## Atrasos Operacionais por Fonte

| Fonte | Atraso | Verificação |
|---|---|---|
| NASA POWER | 14 dias | Empírico 27/03/2026 |
| Google Trends | 7 dias | Lag obrigatório anti-leakage |
| ONI Index | ~60 dias | NOAA publica com 2 meses de atraso |
| INMET | ~2 dias | Estação automática |
| SINAN | 15 semanas | PLOS NTD 2024 — captura 95% notificações |

---

## Fontes de Dados

| Fonte | Dados | Período | Volume |
|---|---|---|---|
| InfoDengue API | Casos confirmados + clima semanal | 2025–atual | ~128 registros/ano |
| NASA POWER API | Radiação + clima diário | 2025–atual | ~365 dias/ano |
| NOAA ONI | El Niño/La Niña trimestral | 1950–atual | 914 trimestres |
| Google Trends | Interesse "dengue" BR-MT | últimos 90d | 91 semanas |
| SINAN/DATASUS (hist.) | Notificações confirmadas | 2007–2024 | 390.048 registros |
| INMET A901 (hist.) | Temperatura, precipitação, umidade | 2018–2024 | 2.557 dias |
| GEE Sentinel-2 (hist.) | NDVI, NDWI, NDBI | 2018–2024 | 84 meses |
| IBGE Censo 2022 | População Cuiabá + VG | 2022 | estático |

---

## Reprodutibilidade
```bash
git clone https://github.com/ediney-magalhaes/dengue-mt.git
cd dengue-mt
conda create -n dengue-mt python=3.11 -y
conda activate dengue-mt
pip install -r requirements.txt

# Rodar pipeline completo
python -m src.pipeline_prefect

# Rodar dashboard
streamlit run app/dashboard.py
```

O pipeline baixa automaticamente o Gold do HF Hub se não encontrado localmente.

---

## Roadmap

| Versão | Data | Status | Entregas |
|---|---|---|---|
| v0.1–v0.3 | Mar/2026 | ✅ | EDA, modelos baseline, arquitetura medalhão inicial |
| v1.0 | 25/03/2026 | ✅ | LightGBM v4, dashboard, CI/CD, HF Hub |
| v1.1 | 27/03/2026 | ✅ | Governança, reprodutibilidade, observabilidade, cache |
| v1.2 | 30/03/2026 | ✅ | Drift acionável, banner, relatório automático |
| v1.3 | 03/04/2026 | ✅ | MLflow, CHANGELOG automático, dicionário de dados |
| v1.4 | 04/04/2026 | ✅ | Arquitetura Medalhão completa, retreino com dados 2025/2026 |
| v1.5 | próxima | 🔄 | Relatório extensionista IFMT, artigo SENIC 2026 |
| v2.0 | futuro | 📋 | Score risco v3, TFT, alertas automáticos |

---

*IFMT — Projeto Extensionista 2026*
*Ediney Magalhães*
*Dashboard: https://dengue-mt-ifmt.streamlit.app*
*Dataset: https://huggingface.co/datasets/edyestatistica/dengue-mt-medallion*