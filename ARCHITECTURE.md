# Arquitetura — Dengue MT

> Documentação técnica completa da arquitetura de dados, modelos e infraestrutura do sistema preditivo de surtos de dengue em Cuiabá e Várzea Grande/MT.

---

## Visão Geral

```
FONTES PÚBLICAS          INGESTÃO              ARMAZENAMENTO
─────────────────────────────────────────────────────────────
SINAN/DATASUS       →   Scripts Python    →   🥉 Bronze (local)
INMET / NASA POWER  →   (src/ + Prefect)  →   🥈 Silver (HF Hub)
GEE Sentinel-2      →   agendamento       →   🥇 Gold  (HF Hub)
NOAA ONI Index      →   semanal           →
                              ↓
                    medallion_migration.py
                    (Polars — validação e limpeza)
                              ↓
                    Rolling Window LightGBM
                    (R²=0.892 | retreino 90 dias)
                              ↓
              ┌───────────────┴───────────────┐
              ↓                               ↓
    Dashboard Streamlit              API REST FastAPI
    (mapa de risco por bairro)       (integração sistemas)
              ↓
         Usuário final
```

---

## Arquitetura Medalhão

A organização dos dados segue o padrão **Medalhão (Bronze → Silver → Gold)**, implementado com **Polars** para processamento eficiente.

### 🥉 Bronze — Dados Brutos (Local / OneDrive)
Cópia fiel e imutável dos dados originais. Nunca modificado.

```
data/bronze/
├── sinan/          ← 18 arquivos Parquet (2007–2024)
├── inmet/          ← INMET A901 Cuiabá (2018–2024)
└── gee/            ← NDVI/NDWI Sentinel-2 + MODIS
```

> Bronze permanece local — os dados originais estão disponíveis publicamente nas fontes (DATASUS, INMET, GEE). Qualquer pessoa pode recriar rodando `python src/medallion_migration.py`.

### 🥈 Silver — Dados Limpos (Hugging Face Hub)
Dados validados, tipados e sem inconsistências. Processado com Polars.

```
silver/
├── sinan/          ← 390.048 registros confirmados (2007–2024)
│   ├── dengue_mt_2007.parquet
│   └── ... dengue_mt_2024.parquet
├── inmet/          ← 2.478 dias climáticos validados
└── gee/            ← 84 meses NDVI/NDWI sem nulos
```

**Transformações aplicadas:**
- SINAN: filtro por `CLASSI_FIN` com mapeamento por período histórico
- INMET: clipping de outliers (temp 10–45°C, precip 0–500mm, umidade 0–100%)
- GEE: remoção de registros com NDVI/NDWI nulos

### 🥇 Gold — Features para ML (Hugging Face Hub)
Dataset final pronto para treinamento de modelos.

```
gold/
├── dataset_features_v2.parquet    ← 2.242 dias × 55 features (2018–2024)
└── serie_historica_2007_2024.parquet ← 888 semanas MT
```

**Transformações aplicadas:**
- Merge de todas as fontes por data
- 55 features de 6 fontes: epidemiológicas, climáticas, satélite, sazonais, ENSO, ciclo epidêmico
- Lags temporais: 7, 14, 21, 28 dias
- Sazonalidade cíclica: seno/cosseno (evita descontinuidade Jan/Dez)

---

## Stack Tecnológica

### Processamento de Dados
| Camada | Tecnologia | Justificativa |
|---|---|---|
| Ingestão | Python + Prefect | Pipelines dinâmicos, free tier generoso |
| Transformação | **Polars** | Execução paralela nativa, 5-10x mais rápido que Pandas |
| Formato | Parquet | Compressão eficiente, tipagem forte |
| Orquestração | Prefect Cloud (free) | Agendamento semanal automático |

### Machine Learning
| Componente | Tecnologia | Justificativa |
|---|---|---|
| Modelo de produção | **Rolling Window LightGBM** | R²=0.892, retreino automático |
| Validação | TimeSeriesSplit | Evita data leakage temporal |
| Otimização | Optuna | Bayesian search, 50 trials |
| Interpretabilidade | SHAP | Features ambientais confirmadas |
| Tracking | MLflow (planejado) | Versionamento de experimentos |

### Armazenamento
| Camada | Tecnologia | Custo |
|---|---|---|
| Código | GitHub | Gratuito |
| Bronze | OneDrive local | Gratuito |
| Silver + Gold | **Hugging Face Hub** | Gratuito (ilimitado público) |
| Modelos | Hugging Face Hub | Gratuito |

### Serving
| Componente | Tecnologia | Custo |
|---|---|---|
| Dashboard | Streamlit Community Cloud | Gratuito |
| API REST | FastAPI + Render.com | Gratuito |
| Alertas | GitHub Actions + SMTP | Gratuito |

> **Custo total de infraestrutura: R$ 0,00**

---

## Modelo Preditivo

### Rolling Window LightGBM — Modelo de Produção

```
Histórico 90 dias → LightGBM → Previsão 28 dias → Score de Risco
      ↑                                                    ↓
  Retreino                                         Mapa por Bairro
  automático
  (semanal)
```

**Parâmetros otimizados (Optuna 50 trials):**
```python
n_estimators      = 220
learning_rate     = 0.02481
max_depth         = 5
subsample         = 0.687
colsample_bytree  = 0.755
min_child_samples = 49
num_leaves        = 58
```

**Top features (SHAP):**
1. `casos_lag_7d` — lag de casos 7 dias (±34 casos)
2. `casos_lag_14d` — lag de casos 14 dias (±18 casos)
3. `casos_mm_7d` — média móvel 7 dias (±12 casos)
4. `umidade_lag_42d` — umidade com defasagem 6 semanas
5. `oni_index` — El Niño/La Niña
6. `ndvi` — cobertura vegetal (criadouros)

### Ranking Completo de Modelos Testados

| Modelo | R² | MAE | Status |
|---|---|---|---|
| **Rolling Window LightGBM** | **0.892** | 17.69 | PRODUÇÃO |
| LightGBM otimizado | 0.871 | 21.83 | baseline |
| N-HiTS recursivo | 0.805 | 27.36 | deep learning |
| N-BEATS recursivo | 0.787 | 30.10 | deep learning |
| CNN + BiLSTM | 0.756 | 33.34 | deep learning |
| LSTM v2 | 0.664 | 38.75 | deep learning |
| TFT (5 configs, GPU T4) | 0.459 → -0.169 | — | experimental |

> TFT testado em 5 configurações com GPU Tesla T4 (Kaggle). Requer normalização hierárquica por porte de município e série histórica mais longa para atingir performance adequada. Referência: Pillay et al. (2026) IJERPH — R²=0.90 com 102 semanas encoder + múltiplos distritos.

---

## Fontes de Dados

| Fonte | Dados | Período | Registros |
|---|---|---|---|
| SINAN/DATASUS | Notificações confirmadas de dengue | 2007–2024 | 390.048 |
| INMET A901 | Temperatura, precipitação, umidade | 2018–2024 | 2.557 dias |
| NASA POWER API | Radiação solar (substitui INMET defeituoso) | 2007–2024 | 6.574 dias |
| GEE Sentinel-2 + MODIS | NDVI, NDWI (blend 100% cobertura) | 2018–2024 | 84 meses |
| NOAA ONI Index | El Niño/La Niña (ENSO) | 2007–2024 | 216 meses |
| IBGE Censo 2022 | População, densidade por setor censitário | 2022 | estático |
| Google Trends | Interesse por "dengue" em MT | 2018–2024 | 84 meses |

---

## Pipeline de Reprodutibilidade

```bash
# 1. Clonar repositório
git clone https://github.com/ediney-magalhaes/dengue-mt.git
cd dengue-mt

# 2. Criar ambiente
conda create -n dengue-mt python=3.11 -y
conda activate dengue-mt
pip install -r requirements.txt

# 3. Baixar dados Silver + Gold do Hugging Face
python -c "
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id='edyestatistica/dengue-mt-medallion',
    repo_type='dataset',
    local_dir='data/'
)
"

# 4. Executar notebooks em ordem
jupyter notebook notebooks/01_eda_exploratoria.ipynb
```

---

## Roadmap de Evolução

```
v1.0 (atual)
├── Rolling Window LightGBM — R²=0.892
├── Dashboard Streamlit (4 abas)
└── Arquitetura Medalhão + Hugging Face

v1.1 (próximas semanas)
├── Score de risco por bairro (shapefile + Folium)
├── API REST FastAPI
└── Deploy Streamlit Community Cloud

v2.0 (futuro)
├── TFT com série 1993-presente (série histórica completa)
├── PatchTST e TimesNet (quando dataset > 5.000 semanas)
├── Pipeline Prefect (ingestão automática semanal)
└── Alertas automáticos (GitHub Actions + SMTP)
```

---

*Instituto Federal de Mato Grosso (IFMT) — Projeto Extensionista 2026*
*Ediney Magalhães — Analytics Engineer / Data Engineer / Estatístico*