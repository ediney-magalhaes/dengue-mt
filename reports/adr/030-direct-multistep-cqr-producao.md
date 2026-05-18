# ADR-030: Migração para Direct Multi-Step Forecasting com CQR em Produção

## Status
Aceito — 2026-05-17

## Contexto
O sistema de previsão em produção (dashboard + pipeline semanal) apresenta
três problemas estruturais interligados:

1. **Previsão estática** — `fazer_previsao_local()` e `gerar_previsao_municipal()`
   passam a mesma linha de features para todos os horizontes (SE+1 a SE+4),
   resultando no mesmo valor previsto para todas as semanas.

2. **Features exógenas indisponíveis** — Das 46 features do modelo v5,
   41 são lags de variáveis exógenas (clima, NDVI, ONI, Trends, Rt) que
   não existem para semanas futuras. Na abordagem recursiva, essas features
   seriam "congeladas" no último valor conhecido, violando o contrato de
   treino do modelo (treinado com features reais, não congeladas).

3. **Sem incerteza quantificada no dashboard** — O CQR foi implementado
   offline (ADR-029) mas nunca integrado ao produto. O gestor de saúde
   vê apenas previsão pontual, sem bandas de incerteza.

### Análise das features do modelo v5

| Grupo | Qtd | Atualizável em t+h? | Exemplos |
|---|---|---|---|
| Lags de casos | 5 | Sim (via previsão) | casos_lag1..4, casos_mm4 |
| Lags exógenas | 37 | Não | temp_media_lag1, precip_lag1, ndvi_lag2 |
| Estáticas | 1 | Sim | populacao |
| Médias/acumulados | 3 | Parcialmente | temp_media_mm4, precip_acum4/8 |

Para SE+1, todas as features estão disponíveis na última linha do Gold
(os lags olham para trás). Para SE+2 em diante, a estratégia recursiva
atualizaria apenas 5 de 46 features — as demais 41 ficariam congeladas.

### Estratégias avaliadas

| Estratégia | Propagação de erro | Features exógenas | Modelos | Produção |
|---|---|---|---|---|
| **Recursiva** | Sim — erro acumula | Congeladas (viola contrato) | 1 | Simples |
| **Direct** | Não | Desnecessárias (modelo aprende) | 4×3=12 | Mais modelos |
| Recursive+Direct | Parcial | Parcialmente congeladas | 4+ | Complexo |

## Decisão
Adotar **Direct Multi-Step Forecasting** com **CQR por horizonte**,
treinando 12 modelos independentes: 4 horizontes × 3 quantis (q05, q50, q95).

### Justificativa

1. **Elimina congelamento de features** — Cada modelo para horizonte h é
   treinado com target `y(t+h)` e features `X(t)`. O modelo aprende
   internamente que `precip_lag1` para h=4 representa precipitação de
   5 semanas antes do evento. Não há violação do contrato de treino.

2. **Sem propagação de erro** — Previsões para cada horizonte são
   independentes; erro de SE+1 não contamina SE+2.
   Referência: Taieb et al. (2012) — "each horizon is independently
   optimized, avoiding the accumulation of errors".

3. **CQR por horizonte** — Bandas de incerteza crescem naturalmente
   com o horizonte (SE+4 mais larga que SE+1), refletindo a degradação
   real de performance documentada no backtesting (sessão 10).
   Referência: Wang & Hyndman (arXiv 2026) — "coverage error admits
   an upper bound that increases with the forecasting horizon".

4. **Consistente com o artigo CBIS'26** — O backtesting já avaliou
   horizontes separados e mostrou degradação por horizonte. A migração
   para Direct formaliza isso em produção.

5. **Padrão de produção estabelecido** — skforecast (ForecasterAutoregDirect)
   implementa esta estratégia como classe nativa para LightGBM/XGBoost.
   Referência: Amat Rodrigo & Escobar Ortiz (2024) — skforecast docs.

6. **Custo zero** — Nenhuma dependência nova; LightGBM quantílico já
   utilizado no CQR offline. Dados são pequenos (856 registros) —
   treinar 12 modelos leva segundos.

### Impacto no sistema

| Componente | Mudança | Risco |
|---|---|---|
| `dbt / SQL` | Nenhuma | Zero |
| `src/features/build_features.py` | Adicionar `criar_targets_direct()` | Baixo |
| `src/tasks/treinar_direto_cqr.py` | Novo módulo (12 modelos) | Médio |
| `src/tasks/retreino.py` | Chamar treino Direct após retreino pontual | Baixo |
| `scripts/gerar_previsao_bairros.py` | Usar modelo correto por horizonte | Baixo |
| `app/components/dados.py` | Carregar 12 modelos do HF Hub | Baixo |
| `app/components/aba_previsao.py` | Bandas CQR no gráfico Plotly | Baixo |
| `src/pipeline_prefect.py` | Adicionar etapa de treino Direct | Baixo |
| HF Hub | 12 `.pkl` + `direct_cqr_metadata.json` | Baixo |
| Testes pytest | Validar 12 modelos (existência + R² mínimo) | Baixo |

### Nomenclatura dos modelos no HF Hub

```
models/lgbm_h1_q50_latest.pkl    # mediana, horizonte 1 (≈ modelo atual)
models/lgbm_h1_q05_latest.pkl    # lower 90%, horizonte 1
models/lgbm_h1_q95_latest.pkl    # upper 90%, horizonte 1
models/lgbm_h2_q50_latest.pkl    # mediana, horizonte 2
models/lgbm_h2_q05_latest.pkl    # lower 90%, horizonte 2
models/lgbm_h2_q95_latest.pkl    # upper 90%, horizonte 2
models/lgbm_h3_q50_latest.pkl    # mediana, horizonte 3
models/lgbm_h3_q05_latest.pkl    # lower 90%, horizonte 3
models/lgbm_h3_q95_latest.pkl    # upper 90%, horizonte 3
models/lgbm_h4_q50_latest.pkl    # mediana, horizonte 4
models/lgbm_h4_q05_latest.pkl    # lower 90%, horizonte 4
models/lgbm_h4_q95_latest.pkl    # upper 90%, horizonte 4
models/direct_cqr_metadata.json  # calibração conformal + métricas
```

### Criação dos targets Direct (em Python, não no dbt)

```python
# Target para horizonte h = shift negativo de h semanas
df['target_h1'] = df.groupby('municipio_id')['casos_confirmados'].shift(-1)
df['target_h2'] = df.groupby('municipio_id')['casos_confirmados'].shift(-2)
df['target_h3'] = df.groupby('municipio_id')['casos_confirmados'].shift(-3)
df['target_h4'] = df.groupby('municipio_id')['casos_confirmados'].shift(-4)
```

Features `X(t)` permanecem as mesmas 46 do schema v5. O Gold e o dbt
não são alterados — a criação dos targets Direct é responsabilidade
exclusiva do módulo de treino.

## Consequências

### Positivas
- Dashboard exibe previsões distintas por horizonte (resolve bug do valor repetido)
- Bandas de incerteza CQR 90% visíveis no gráfico (resolve ausência de incerteza)
- Incerteza cresce com horizonte (comportamento correto e esperado)
- Modelo h=1 é funcionalmente equivalente ao v5 atual (retrocompatibilidade)
- Sem violação de contrato de features entre treino e inferência
- Fundamentado na literatura (Direct forecasting + CQR + conformal multi-step)

### Negativas
- 12 modelos em vez de 1 (maior complexidade de gestão de artefatos)
- Treino ~12x mais longo (ainda < 1 min com dados atuais de 856 registros)
- Modelo v5 pontual atual será descontinuado (substituído por h1_q50)

### Invariantes preservados
- `log1p(target)` no treino + `expm1()` na inferência (ADR-024)
- TimeSeriesSplit 5-fold como validação oficial
- Promoção condicional via pytest + R² gate
- Pipeline dbt intacto (Bronze → Silver → Intermediate → Gold)
- Limiares adaptativos percentílicos no mapa IDW

## Referências
- Taieb, S., Hyndman, R. (2014). A gradient boosting approach to the
  Kaggle load forecasting competition. International Journal of
  Forecasting, 30(2), 382-394.
- Romano, Y., Patterson, E., Candès, E. (2019). Conformalized Quantile
  Regression. NeurIPS 32.
- Wang, X., Hyndman, R. (2026). Online conformal inference for multi-step
  time series forecasting. arXiv:2410.13115.
- PMC (2025). Dengue forecasting and outbreak detection in Brazil using
  LSTM — adaptive conformal prediction. PMC 12657288.
- Manna, S. et al. (2025). Distribution-free inference for LightGBM —
  residual-based conformal prediction intervals. arXiv:2507.06921.
- Amat Rodrigo, J., Escobar Ortiz, J. (2024). skforecast: time series
  forecasting with scikit-learn regressors. ForecasterAutoregDirect.

## Artefatos (planejados)
- `src/tasks/treinar_direto_cqr.py` — módulo de treino dos 12 modelos
- `src/features/build_features.py` — função `criar_targets_direct()`
- `models/lgbm_h{1-4}_q{05,50,95}_latest.pkl` — 12 modelos
- `models/direct_cqr_metadata.json` — calibração + métricas
- `app/components/aba_previsao.py` — gráfico com bandas CQR
- `reports/adr/030-direct-multistep-cqr-producao.md` — este documento