# Dicionário de Dados — Dengue MT

> Documento gerado automaticamente a partir do Feature Schema e metadados do pipeline.
> Dataset: `gold/dataset_features_v4.parquet` — 59 features no modelo

---

## INMET A901

| Feature | Descrição | Frequência | Lag (dias) | Unidade | Intervalo válido | Imputação | No modelo |
|---|---|---|---|---|---|---|---|
| `amplitude_termica` | Amplitude térmica diária (max-min) | diário | 0 | °C | [0, 30] | calculado | ✅ sim |
| `dias_sem_chuva` | Dias consecutivos sem precipitação | diário | 0 | dias | [0, 365] | calculado | ✅ sim |
| `precip_acum_14d` | Precipitação acumulada 14 dias | diário | 14 | mm | [0, 800] | zero | ✅ sim |
| `precip_acum_28d` | Precipitação acumulada 28 dias | diário | 28 | mm | [0, 1500] | zero | ✅ sim |
| `precip_acum_7d` | Precipitação acumulada 7 dias | diário | 7 | mm | [0, 500] | zero | ✅ sim |
| `precip_lag_28d` | Precipitação total lag 28 dias | diário | 28 | mm | [0, 200] | zero | ✅ sim |
| `precip_lag_35d` | Precipitação total lag 35 dias | diário | 35 | mm | [0, 200] | zero | ✅ sim |
| `precip_lag_42d` | Precipitação total lag 42 dias | diário | 42 | mm | [0, 200] | zero | ✅ sim |
| `precip_mm_14d` | Média móvel precipitação 14 dias | diário | 14 | mm | [0, 200] | zero | ✅ sim |
| `precip_mm_28d` | Média móvel precipitação 28 dias | diário | 28 | mm | [0, 200] | zero | ✅ sim |
| `precip_mm_7d` | Média móvel precipitação 7 dias | diário | 7 | mm | [0, 200] | zero | ✅ sim |
| `precipitacao_total` | Precipitação total diária | diário | 0 | mm | [0, 200] | zero (sem chuva) | ✅ sim |
| `temp_lag_28d` | Temperatura média lag 28 dias | diário | 28 | °C | [10, 45] | interpolação linear | ✅ sim |
| `temp_lag_35d` | Temperatura média lag 35 dias | diário | 35 | °C | [10, 45] | interpolação linear | ✅ sim |
| `temp_lag_42d` | Temperatura média lag 42 dias | diário | 42 | °C | [10, 45] | interpolação linear | ✅ sim |
| `temp_max` | Temperatura máxima diária | diário | 0 | °C | [15, 50] | interpolação linear | ✅ sim |
| `temp_media` | Temperatura média diária | diário | 0 | °C | [10, 45] | interpolação linear | ✅ sim |
| `temp_min` | Temperatura mínima diária | diário | 0 | °C | [5, 40] | interpolação linear | ✅ sim |
| `umidade_lag_28d` | Umidade relativa média lag 28 dias | diário | 28 | % | [10, 100] | interpolação linear | ✅ sim |
| `umidade_lag_35d` | Umidade relativa média lag 35 dias | diário | 35 | % | [10, 100] | interpolação linear | ✅ sim |
| `umidade_lag_42d` | Umidade relativa média lag 42 dias | diário | 42 | % | [10, 100] | interpolação linear | ✅ sim |
| `umidade_max` | Umidade relativa máxima diária | diário | 0 | % | [10, 100] | interpolação linear | ✅ sim |
| `umidade_media` | Umidade relativa média diária | diário | 0 | % | [10, 100] | interpolação linear | ✅ sim |
| `umidade_min` | Umidade relativa mínima diária | diário | 0 | % | [10, 100] | interpolação linear | ✅ sim |
| `umidade_mm_14d` | Média móvel umidade 14 dias | diário | 14 | % | [10, 100] | interpolação linear | ✅ sim |
| `umidade_mm_28d` | Média móvel umidade 28 dias | diário | 28 | % | [10, 100] | interpolação linear | ✅ sim |
| `umidade_mm_7d` | Média móvel umidade 7 dias | diário | 7 | % | [10, 100] | interpolação linear | ✅ sim |

## NASA POWER API

| Feature | Descrição | Frequência | Lag (dias) | Unidade | Intervalo válido | Imputação | No modelo |
|---|---|---|---|---|---|---|---|
| `radiacao_lag_28d` | Radiação solar lag 28 dias | diário | 28 | MJ/m² | [0, 35] | interpolação linear | ✅ sim |
| `radiacao_mj` | Radiação solar superficial diária | diário | 0 | MJ/m² | [0, 35] | interpolação linear | ✅ sim |
| `radiacao_mm_14d` | Média móvel radiação 14 dias | diário | 14 | MJ/m² | [0, 35] | interpolação linear | ✅ sim |

## GEE Sentinel-2/MODIS

| Feature | Descrição | Frequência | Lag (dias) | Unidade | Intervalo válido | Imputação | No modelo |
|---|---|---|---|---|---|---|---|
| `ndvi` | Índice de vegetação (Sentinel-2+MODIS blend) | mensal | 0 | [-1,1] | [-1, 1] | média sazonal | ✅ sim |
| `ndwi` | Índice de água (Sentinel-2+MODIS blend) | mensal | 0 | [-1,1] | [-1, 1] | média sazonal | ✅ sim |

## GEE Sentinel-2

| Feature | Descrição | Frequência | Lag (dias) | Unidade | Intervalo válido | Imputação | No modelo |
|---|---|---|---|---|---|---|---|
| `ndbi_gee` | Índice de urbanização (Sentinel-2) | mensal | 0 | [-1,1] | [-1, 1] | interpolação linear | ✅ sim |
| `ndbi_lag_30d` | Índice de urbanização lag 30 dias | mensal | 30 | [-1,1] | [-1, 1] | interpolação linear | ✅ sim |
| `ndbi_lag_60d` | Índice de urbanização lag 60 dias | mensal | 60 | [-1,1] | [-1, 1] | interpolação linear | ✅ sim |

## NOAA ONI

| Feature | Descrição | Frequência | Lag (dias) | Unidade | Intervalo válido | Imputação | No modelo |
|---|---|---|---|---|---|---|---|
| `fase_enso_num` | Fase ENSO codificada numericamente | mensal | 0 | {-1,0,1} | [-1, 1] | forward fill | ✅ sim |
| `oni_index` | Índice Oceânico El Niño (ENSO) | mensal | 0 | °C | [-3, 3] | forward fill | ✅ sim |

## Google Trends

| Feature | Descrição | Frequência | Lag (dias) | Unidade | Intervalo válido | Imputação | No modelo |
|---|---|---|---|---|---|---|---|
| `trends_lag_14d` | Interesse "dengue" Google Trends lag 14d | semanal | 14 | [0,100] | [0, 100] | forward fill | ✅ sim |
| `trends_lag_21d` | Interesse "dengue" Google Trends lag 21d | semanal | 21 | [0,100] | [0, 100] | forward fill | ✅ sim |
| `trends_lag_7d` | Interesse "dengue" Google Trends lag 7d | semanal | 7 | [0,100] | [0, 100] | forward fill | ✅ sim |

## SINAN/DATASUS

| Feature | Descrição | Frequência | Lag (dias) | Unidade | Intervalo válido | Imputação | No modelo |
|---|---|---|---|---|---|---|---|
| `anos_desde_pico` | Anos desde o último pico epidêmico | diário | 0 | anos | [0, 10] | calculado | ✅ sim |
| `casos` | Casos confirmados de dengue (TARGET) | diário | 0 | casos | [0, 1000] | N/A | ❌ não |
| `casos_acum_ano` | Casos acumulados no ano corrente | diário | 0 | casos | [0, 50000] | calculado | ✅ sim |
| `casos_lag_14d` | Casos confirmados lag 14 dias | diário | 14 | casos | [0, 1000] | zero | ✅ sim |
| `casos_lag_21d` | Casos confirmados lag 21 dias | diário | 21 | casos | [0, 1000] | zero | ✅ sim |
| `casos_lag_28d` | Casos confirmados lag 28 dias | diário | 28 | casos | [0, 1000] | zero | ✅ sim |
| `casos_lag_7d` | Casos confirmados lag 7 dias | diário | 7 | casos | [0, 1000] | zero | ✅ sim |
| `casos_mm_14d` | Média móvel casos 14 dias | diário | 14 | casos | [0, 1000] | zero | ✅ sim |
| `casos_mm_28d` | Média móvel casos 28 dias | diário | 28 | casos | [0, 1000] | zero | ✅ sim |
| `casos_mm_7d` | Média móvel casos 7 dias | diário | 7 | casos | [0, 1000] | zero | ✅ sim |
| `casos_nowcast` | Casos corrigidos pelo fator nowcasting | diário | 0 | casos | [0, 3000] | calculado | ❌ não |
| `ciclo_epidemico` | Indicador de ano de pico (0/1) | diário | 0 | {0,1} | [0, 1] | calculado | ✅ sim |
| `fator_nowcasting` | Fator de correção subnotificação SINAN | semanal | 0 | fator | [1, 3] | média histórica | ❌ não |

## calendário

| Feature | Descrição | Frequência | Lag (dias) | Unidade | Intervalo válido | Imputação | No modelo |
|---|---|---|---|---|---|---|---|
| `ano` | Ano calendário | diário | 0 | ano | [2018, 2030] | N/A | ✅ sim |
| `dia_ano` | Dia do ano (1-366) | diário | 0 | dia | [1, 366] | N/A | ✅ sim |
| `mes` | Mês calendário (1-12) | diário | 0 | mês | [1, 12] | N/A | ✅ sim |
| `mes_cosseno` | Codificação cíclica cosseno do mês | diário | 0 | [-1,1] | [-1, 1] | calculado | ✅ sim |
| `mes_seno` | Codificação cíclica seno do mês | diário | 0 | [-1,1] | [-1, 1] | calculado | ✅ sim |
| `semana_ano` | Semana epidemiológica (1-53) | diário | 0 | semana | [1, 53] | N/A | ✅ sim |
| `semana_cosseno` | Codificação cíclica cosseno da semana | diário | 0 | [-1,1] | [-1, 1] | calculado | ✅ sim |
| `semana_seno` | Codificação cíclica seno da semana | diário | 0 | [-1,1] | [-1, 1] | calculado | ✅ sim |
| `trimestre` | Trimestre do ano (1-4) | diário | 0 | trim | [1, 4] | N/A | ✅ sim |

## IBGE

| Feature | Descrição | Frequência | Lag (dias) | Unidade | Intervalo válido | Imputação | No modelo |
|---|---|---|---|---|---|---|---|
| `municipio_id` | Identificador do município | estático | 0 | código | N/A | N/A | ❌ não |

## SINAN/IBGE

| Feature | Descrição | Frequência | Lag (dias) | Unidade | Intervalo válido | Imputação | No modelo |
|---|---|---|---|---|---|---|---|
| `casos_nowcast_por_100k` | Incidência nowcast por 100k | diário | 0 | casos/100k | [0, 1500] | calculado | ❌ não |
| `casos_por_100k` | Incidência por 100k habitantes | diário | 0 | casos/100k | [0, 500] | calculado | ❌ não |

---

## Resumo

| Item | Valor |
|---|---|
| Total de variáveis documentadas | 65 |
| Features no modelo | 59 |
| Variáveis fora do modelo | 6 |
| Dataset version | v4 |
| Modelo | LightGBM v4 — R²=0.820 \| MAE=17.6 \| sMAPE=31.5% |
| Validação | TimeSeriesSplit 5 folds |

---
*Gerado automaticamente — Dengue MT — IFMT 2026*