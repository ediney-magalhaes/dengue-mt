# Dicionário de Dados — Dengue MT

> Dataset: `gold/dataset_features_latest.parquet`
> Granularidade: **semanal por município** (semana epidemiológica)
> Período: 2018-02-04 → 2026-06-14 | ~880 registros (428+ por município)
> Versão: Gold v5 (refatorado com dbt-core + DuckDB)

---

## Identificação

| Coluna | Descrição | Tipo | Valores |
|---|---|---|---|
| `municipio_id` | Código IBGE do município (7 dígitos) | int | 5103403 (Cuiabá), 5108402 (Várzea Grande) |
| `municipio_nome` | Nome do município | string | cuiaba, varzea_grande |
| `data_se` | Data de início da semana epidemiológica (domingo) | date | 2018-02-04 → 2026-04-12 |
| `semana_epidemiologica` | Semana epidemiológica no formato AAAASS | int | ex: 201806, 202615 |
| `populacao` | População estimada do município (Censo 2022) | int | ~620k (Cuiabá), ~290k (VG) |
| `dbt_updated_at` | Timestamp de atualização pelo dbt | datetime | automático |

## Variável-alvo (Target)

| Coluna | Descrição | Tipo | Intervalo | Observação |
|---|---|---|---|---|
| `casos_confirmados` | Casos de dengue confirmados na SE | int | [0, ~500] | Target do modelo. Transformado com log1p no treino (ADR-024) |

## Indicadores InfoDengue (não entram no modelo como features)

| Coluna | Descrição | Tipo | Intervalo | No modelo |
|---|---|---|---|---|
| `casos_estimados` | Casos estimados pelo nowcasting InfoDengue | float | [0, ~600] | ❌ não |
| `incidencia_100k` | Incidência por 100 mil habitantes | float | [0, ~150] | ❌ não |

## Features Epidemiológicas — InfoDengue (lag 1 SE)

| Coluna | Descrição | Lag | Intervalo | Importância EDA |
|---|---|---|---|---|
| `rt_index_lag1` | Número reprodutivo efetivo (Rt) | 1 SE | [0, ~20] | Indicador de expansão epidêmica |
| `nivel_alerta_lag1` | Nível de alerta InfoDengue (1-4) | 1 SE | {1, 2, 3, 4} | Verde/Amarelo/Laranja/Vermelho |
| `receptivo_lag1` | Condições de receptividade do mosquito | 1 SE | {0, 1, 2, 3} | Baseado em clima |
| `transmissao_lag1` | Evidência de transmissão sustentada | 1 SE | {0, 1, 2, 3} | Baseado em Rt e incidência |
| `prob_rt_maior_1_lag1` | Probabilidade de Rt > 1 | 1 SE | [0, 1] | Proxy de risco epidêmico |
| `notif_acum_ano_lag1` | Notificações acumuladas no ano (lag 1 SE) | 1 SE | [0, ~4000] | Proxy de pressão epidêmica |

## Features Autoregressivas — Casos (lag 1-4 SE)

| Coluna | Descrição | Lag | Correlação com target | Observação |
|---|---|---|---|---|
| `casos_lag1` | Casos confirmados lag 1 SE | 1 SE | r = 0.927 | Feature mais importante (inércia epidêmica) |
| `casos_lag2` | Casos confirmados lag 2 SE | 2 SE | r = 0.870 | |
| `casos_lag3` | Casos confirmados lag 3 SE | 3 SE | r = 0.808 | |
| `casos_lag4` | Casos confirmados lag 4 SE | 4 SE | r = 0.745 | |
| `casos_mm4` | Média móvel de casos 4 SE | 4 SE | r = 0.933 | Suaviza flutuações semanais |

## Features Climáticas — Temperatura (NASA POWER, lag 1-4 SE)

| Coluna | Descrição | Lag | Unidade | Intervalo |
|---|---|---|---|---|
| `temp_media_lag1` | Temperatura média lag 1 SE | 1 SE | °C | [15, 35] |
| `temp_media_lag2` | Temperatura média lag 2 SE | 2 SE | °C | [15, 35] |
| `temp_media_lag3` | Temperatura média lag 3 SE | 3 SE | °C | [15, 35] |
| `temp_media_lag4` | Temperatura média lag 4 SE | 4 SE | °C | [15, 35] |
| `temp_max_lag1` | Temperatura máxima lag 1 SE | 1 SE | °C | [20, 45] |
| `temp_max_lag2` | Temperatura máxima lag 2 SE | 2 SE | °C | [20, 45] |
| `temp_min_lag1` | Temperatura mínima lag 1 SE | 1 SE | °C | [10, 30] |
| `temp_min_lag2` | Temperatura mínima lag 2 SE | 2 SE | °C | [10, 30] |
| `temp_media_mm4` | Média móvel temperatura 4 SE | 4 SE | °C | [15, 35] |
| `temp_media_mm8` | Média móvel temperatura 8 SE | 8 SE | °C | [15, 35] |

## Features Climáticas — Precipitação e Umidade (NASA POWER)

| Coluna | Descrição | Lag | Unidade | Intervalo |
|---|---|---|---|---|
| `precip_lag1` | Precipitação semanal lag 1 SE | 1 SE | mm | [0, ~120] |
| `precip_lag2` | Precipitação semanal lag 2 SE | 2 SE | mm | [0, ~120] |
| `precip_lag3` | Precipitação semanal lag 3 SE | 3 SE | mm | [0, ~120] |
| `precip_lag4` | Precipitação semanal lag 4 SE | 4 SE | mm | [0, ~120] |
| `precip_acum4` | Precipitação acumulada 4 SE | 4 SE | mm | [0, ~500] |
| `precip_acum8` | Precipitação acumulada 8 SE | 8 SE | mm | [0, ~500] |
| `umidade_lag1` | Umidade relativa lag 1 SE | 1 SE | % | [30, 100] |
| `umidade_lag2` | Umidade relativa lag 2 SE | 2 SE | % | [30, 100] |
| `umidade_nasa_lag1` | Umidade específica NASA lag 1 SE | 1 SE | g/kg | [5, 25] |
| `umidade_nasa_lag2` | Umidade específica NASA lag 2 SE | 2 SE | g/kg | [5, 25] |
| `radiacao_lag1` | Radiação solar lag 1 SE | 1 SE | MJ/m² | [5, 30] |
| `radiacao_lag2` | Radiação solar lag 2 SE | 2 SE | MJ/m² | [5, 30] |

## Features Macroclimáticas — ENSO/ONI (NOAA)

| Coluna | Descrição | Lag | Intervalo | Observação |
|---|---|---|---|---|
| `oni_lag4` | Oceanic Niño Index lag 4 SE | 4 SE | [-3, 3] | El Niño > +0.5, La Niña < -0.5 |
| `oni_lag6` | Oceanic Niño Index lag 6 SE | 6 SE | [-3, 3] | |
| `oni_lag8` | Oceanic Niño Index lag 8 SE | 8 SE | [-3, 3] | Domina PC3 no PCA (14.9% variância) |
| `fase_enso_num_lag4` | Fase ENSO numérica lag 4 SE | 4 SE | {-1, 0, 1} | -1=La Niña, 0=Neutro, 1=El Niño |
| `fase_enso_num_lag6` | Fase ENSO numérica lag 6 SE | 6 SE | {-1, 0, 1} | |

## Features de Vegetação — MODIS MOD13A3.061 (NASA AppEEARS)

| Coluna | Descrição | Lag | Intervalo | Observação |
|---|---|---|---|---|
| `ndvi_lag2` | NDVI lag 2 SE | 2 SE | [-1, 1] | Índice de vegetação |
| `ndvi_lag3` | NDVI lag 3 SE | 3 SE | [-1, 1] | |
| `ndvi_lag4` | NDVI lag 4 SE | 4 SE | [-1, 1] | |
| `evi_lag2` | EVI lag 2 SE | 2 SE | [-1, 1] | Enhanced Vegetation Index |
| `evi_lag3` | EVI lag 3 SE | 3 SE | [-1, 1] | |

## Features de Busca — Google Trends (pytrends)

| Coluna | Descrição | Lag | Intervalo | Observação |
|---|---|---|---|---|
| `trends_lag1` | Interesse de busca "dengue" lag 1 SE | 1 SE | [0, 100] | Contemporâneo, não preditivo (r=0.71 lag 0) |
| `trends_lag2` | Interesse de busca "dengue" lag 2 SE | 2 SE | [0, 100] | |

---

## Resumo

| Item | Valor |
|---|---|
| Total de colunas | 54 |
| Features para treino (excluindo ID, target, não-preditoras) | 46 |
| Colunas de identificação | 6 (municipio_id, municipio_nome, data_se, semana_epidemiologica, populacao, dbt_updated_at) |
| Colunas excluídas do treino | 2 (casos_estimados, incidencia_100k) |
| Dataset version | Gold v5 |
| Última atualização | 2026-06-14 |
| Modelo | LightGBM v5 — R²=0.741 ± 0.081 \| MAE=9.7 (TimeSeriesSplit 5-fold) |
| Backtesting | MASE=0.59 (h=4) \| MAE=17.9 (expanding window 2023→2026) |

## Análise de Componentes Principais (EDA)

Os 46 features de treino se organizam em 4 fatores principais (70.1% da variância):

| Componente | Variância | Interpretação | Features dominantes |
|---|---|---|---|
| PC1 | 24.2% | Fator Hídrico | precip_acum8, precip_acum4, umidade_nasa_lag1 |
| PC2 | 20.0% | Fator Térmico | temp_media_mm4, temp_media_mm8, temp_media_lag1 |
| PC3 | 14.9% | Fator Macroclimático (ENSO) | oni_lag8, oni_lag6, fase_enso_num_lag6 |
| PC4 | 11.0% | Fator Autoregressivo | casos_lag1, casos_mm4, casos_lag2 |

## Multicolinearidade

22 pares de features com |r| > 0.90, concentrados nos grupos ONI/ENSO e temperatura.
O LightGBM lida naturalmente com redundância sem degradação de performance (confirmado no backtesting).

---

*Atualizado em 17/06/2026 — período Gold estendido até 2026-06-14*