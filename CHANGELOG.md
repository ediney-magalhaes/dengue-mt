# Changelog — Dengue MT

Todas as mudanças notáveis do projeto são documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

## Template para releases futuras
```markdown
## [X.Y.Z] — YYYY-MM-DD

### Modelo
- Arquivo: `lgbm_v4_producao.pkl`
- Dataset: `gold/dataset_features_v4_YYYY-MM-DD.parquet`
- Commit SHA: `xxxxxxxx`
- MAE: X.X casos/dia | R²: X.XXX | sMAPE: XX.X%
- Retreino: [sim/não] | Motivo: [drift/manual/agendado]

### Features
- N features — [sem mudanças / mudanças descritas abaixo]
- Adicionadas: [lista ou "nenhuma"]
- Removidas: [lista ou "nenhuma"]
- Contratos: [validados/alterados]

### Infraestrutura
- Pipeline version: X.X.X
- Drift score: X.XXX | Nível: [normal/moderado/crítico]
- Fontes com fallback: [lista ou "nenhuma"]
```

---

## [2.5.0] — 2026-06-01

### Adicionado
- **Análise SHAP para Direct CQR** — `notebooks/backtesting/04_shap_direct_cqr.py`
  - TreeSHAP (Lundberg et al., Nature MI 2020) sobre modelos q50 dos 4 horizontes
  - Análise global (ambos municípios) + por município (Cuiabá e Várzea Grande)
  - 33 figuras: beeswarm, bar top20, dependence, temporal por horizonte + comparativo
  - 13 CSVs de importância: por horizonte, por município, consolidado (184 linhas)
  - Imputação de mediana para NaN no dependence plot (compatibilidade shap.dependence_plot)
- **Aba Explicabilidade no dashboard** — `app/components/aba_shap.py`
  - 6ª aba: "🔍 Explicabilidade" — integrada ao sidebar (horizonte + município)
  - 4 seções: importância global, beeswarm, temporal por fase epidêmica, comparativo horizontes
  - Textos explicativos para público não-técnico em cada seção
  - Detalhes técnicos e referências bibliográficas em expander
- `app/assets/shap/` — assets estáticos PNG servidos pelo Streamlit Cloud

### Resultado principal (SHAP)
- h=1,2: `casos_mm4` domina (|SHAP|=0.69, 0.67) — modelo reativo ao momentum epidêmico
- h=4: transição estrutural — `casos_mm4` cede espaço para `notif_acum_ano_lag1`
- h=8: `notif_acum_ano_lag1` (0.39) + `precip_acum8` (0.33) assumem o topo — modelo prospectivo
- Padrão consistente com ciclo biológico do *Aedes aegypti* (~2-3 semanas) e com
  Taieb & Hyndman (2014) — resultado publicável direto para o CBIS'26

### Documentação
- ADR-034 — SHAP para Direct CQR (decisões: q50 apenas, PNG estático, script offline,
  análise por município, ciclo de atualização pós-retreino)

### Commits
- (98) `be8acd4` — script SHAP + artefatos (33 figuras + 13 CSVs)
- (99) `85750a5` — aba Explicabilidade no dashboard + assets

### Referências
- Lundberg & Lee (NeurIPS 2017) — SHAP original
- Lundberg et al. (Nature MI 2020) — TreeSHAP
- Taieb & Hyndman (2014) — Direct multi-step forecasting
- Molnar, C. (2023) — *Interpretable Machine Learning*, cap. 8-9

---

## [2.4.3] — 2026-05-25

### Corrigido
- **Keep-alive Playwright** — `curl` retornava HTTP 303 (shell estático) sem iniciar o processo Python do app; substituído por Chromium headless via Playwright que renderiza a página de fato e clica no botão de wake-up quando necessário (commits 92–94)
- Seletor `networkidle` incompatível com WebSocket do Streamlit — substituído por `domcontentloaded` + verificação por conteúdo (>10KB = app real vs ~4KB = shell estático)
- Seletor `data-testid="stAppViewContainer"` removido — não existe na versão atual do Streamlit; verificação agora usa título do dashboard + fallback por tamanho
- Upload de screenshot debug em caso de falha (`actions/upload-artifact@v4`)

### Referências
- [Streamlit Keepalive with Playwright](https://zenn.dev/shogaku/articles/streamlit-keepalive-playwright) — problema documentado: HTTP 200/303 não acorda SPAs
- [Streamlit-App-KeepAlive](https://github.com/ToroData/Streamlit-App-KeepAlive) — abordagem alternativa com curl (insuficiente para SPAs)

### Adicionado
- **Workflow MODIS mensal** — `modis_mensal.yml` com cron dia 5/mês às 06h Cuiabá; ingere NDVI/EVI via AppEEARS e publica Bronze no HF Hub, isolado do pipeline semanal (commit 96)
- `scripts/atualizar_modis.py` — script standalone de re-ingestão e publicação
- Timeout `aguardar_tarefa()` aumentado de 30 para 60 min por município

---

## [2.4.2] — 2026-05-21

### Infraestrutura
- **Keep Dashboard Alive** — workflow `keepalive.yml` com cron a cada 4h para evitar hibernação do Streamlit Community Cloud (commit 90)
- **Node.js 24 migration** — `actions/checkout@v4` → `@v5`, `actions/cache@v4` → `@v5` (deadline GitHub: 16/06/2026) (commit 90)

---

## [2.4.1] — 2026-05-20

### Corrigido
- **Filtro de horizonte** — `select_slider` com opções [1, 2, 4, 8] substituindo slider linear 1–4; filtro `horizonte_se <= semanas` na aba Previsão (commit 86)
- Texto metodológico do mapa atualizado para "LightGBM Direct Multi-Step (CQR 90%)"

### Adicionado
- **Treino Direct CQR no pipeline** — `treinar_direto_cqr` integrado na Etapa 3 do `pipeline_prefect.py`, entre Gold e previsão por bairros (commit 87)
- **11 testes pytest Direct CQR** — cobertura: artefatos, metadata, targets log1p, expm1 (ADR-024), bandas ordenadas, features consistentes, R² mínimo por horizonte (commit 88)
- Suíte completa: 21/21 passed (10 pipeline + 11 Direct CQR)
- Tolerância quantile crossing h=8 documentada (Koenker 2005)

### Documentação
- ADR-033 — Testes automatizados Direct CQR

### Pendente (próximas sessões)
- Validar CI de domingo 25/05 — Gold deve avançar além de 12/04
- Relatório extensionista IFMT
- Artigo SENIC 2026

---

## [2.4.0] — 2026-05-19

### Implementado — Direct Multi-Step Forecasting + CQR
- **Migração para Direct Multi-Step Forecasting** (ADR-030)
  - 12 modelos independentes: 4 horizontes (SE+1, +2, +4, +8) × 3 quantis (q05, q50, q95)
  - Elimina bug de previsão estática (mesmo valor para todos os horizontes)
  - Elimina congelamento de features exógenas na inferência multi-horizonte
  - Referências: Taieb & Hyndman (2014), skforecast ForecasterAutoregDirect
- **Bandas CQR no dashboard** — aba Previsão com intervalo de 90%
  - Incerteza cresce com horizonte (comportamento correto)
  - Referências: Romano et al. (NeurIPS 2019), Wang & Hyndman (arXiv 2026)
- **Novo módulo**: `src/tasks/treinar_direto_cqr.py`
- **Novo artefato HF Hub**: 12 `.pkl` + `direct_cqr_metadata.json`

### Corrigido
- `aba_sobre.py` v2.1 — período atualizado 2018→2026, capacidades CQR/SHAP/backtesting, menção CBIS'26 (commit 80)
- Bug `shift(-h)` sem `groupby('municipio_id')` contaminava targets entre municípios
- **Fix crítico Gold HF Hub** — `publicacao.py` publicava parquet restaurado em vez de exportar do DuckDB; Gold parado em 12/04 por 5 semanas (ADR-032)
- Quantis CQR migrados de q01/q99 para q05/q95 — bandas 34% mais estreitas mantendo 90% de cobertura

### Métricas (expanding window)
| Horizonte | R² | MAE | Cobertura calibrada |
|---|---|---|---|
| h=1 | 0.589 | 13.8 | 90.1% |
| h=2 | 0.525 | 14.9 | 90.1% |
| h=4 | 0.509 | 15.9 | 90.0% |
| h=8 | 0.435 | 16.7 | 89.9% |

### Documentação
- ADR-030 atualizado — status Implementado, métricas reais, artefatos
- ADR-031 — Calibração conformal das bandas (Romano et al., NeurIPS 2019)

### Entregues nesta versão
- `scripts/gerar_previsao_bairros.py` — reescrito para 12 modelos Direct CQR + bandas IDW
- `app/components/dados.py` — `carregar_modelos_direct_hf()` + `fazer_previsao_local()` com bandas
- `app/components/aba_previsao.py` v4.0 — banda sombreada Plotly + tabela com limites
- `src/tasks/publicacao.py` — exportação DuckDB → parquet antes de publicar

### Pendente (próximas sessões)
- Filtro de horizonte na aba Previsão (slider não respeitado) - FEITO
- `src/pipeline_prefect.py` — integrar `treinar_direto_cqr` no fluxo semanal - FEITO
- Testes pytest para modelos Direct CQR - FEITO
- Merge dev→main validado com CI/CD - FEITO

---

## [2.3.0] — 2026-05-13

### Adicionado
- **Intervalos de predição CQR** (Conformalized Quantile Regression)
  - Romano, Patterson & Candès (NeurIPS 2019) implementado sobre LightGBM v5
  - CQR 90%: cobertura empírica 91.5%, largura média adaptativa 129 casos
  - CQR 80%: cobertura empírica 69.8%, largura média 63.7 casos
  - Comparação com baseline fixo (bootstrap resíduos) — CQR superior
  - 6 figuras: série com bandas, cobertura por trimestre, largura adaptativa
  - Dependência: `mapie==1.4.0`
- **Análise SHAP atualizada** (Lundberg & Lee, NeurIPS 2017)
  - TreeExplainer sobre 428 semanas × 46 features
  - Top 2: Casos MM4 (|SHAP|=0.671) e Casos lag1 (|SHAP|=0.222)
  - Dependence plots revelam threshold ~100 casos e faixa térmica 24-28°C
  - SHAP temporal por fase epidêmica (original — pré-surto, surto, entressafra)
  - 4 figuras + CSV de importâncias
- `.gitignore` limpo — duplicatas e artefatos removidos

### Referências adicionadas
- Romano et al. (NeurIPS 2019) — Conformalized Quantile Regression
- Cordier et al. (COPA/PMLR 2023) — MAPIE library
- Rahman et al. (Health Sci Rep 2025) — SHAP + LightGBM dengue Bangladesh
- PMC 2025 — Conformal prediction para dengue no Brasil

---

## [2.2.1] — 2026-05-11

### Adicionado
- **EDA completa Gold v5** — 7 scripts em `notebooks/eda/`, 17 figuras em `reports/eda/`
  - Estatísticas descritivas, Shapiro-Wilk, missing values
  - Séries temporais + decomposição STL (sazonalidade Cuiabá 52.9% vs VG 10.2%)
  - Perfil sazonal, distribuição, boxplot anual
  - Correlações, CCF, multicolinearidade (22 pares |r|>0.90)
  - Análise multivariada — séries temporais clima × casos
  - PCA — 4 componentes = 70.1% variância (água, temperatura, ENSO, inércia)
  - Vigilância — Rt, nowcasting, incidência 100k, sincronicidade municípios
- **Backtesting expanding window** — `notebooks/backtesting/`, 3 figuras + 2 CSVs
  - Estratégia recursiva vs direta, horizontes h=1,2,3,4
  - Baselines: naïve e média móvel 4 SE
  - Métricas: MAE, RMSE, R², MASE por horizonte e período
  - ADR-028: decisão documentada
- **Dicionário de dados atualizado** — Gold v5, 54 colunas, movido para `docs/`

### Corrigido
- Bug no gráfico de incidência 100k (eixo X com datas erradas por `sharex=True`)
- `__pycache__` removido do tracking e adicionado ao `.gitignore`

### Descobertas (EDA)
- Incidência VG 2025: 1.222/100k (4x Cuiabá) — surto real confirmado
- Sincronicidade lag=0 (r=0.79) — surtos simultâneos entre municípios
- Google Trends é contemporâneo (r=0.71 lag 0), não preditivo
- Backtesting MASE=0.59 em h=4 — modelo erra 41% menos que baseline naïve
- Estratégia recursiva supera direta em todos os horizontes

---

## [2.0.0-dev] — 2026-04-26 (continuação)

### Contexto
Conclusão da refatoração v2.0 — 17 passos completos, teste end-to-end
validado, bug crítico de escala (expm1) detectado e corrigido.

### Modelo
- Arquivo: `models/lgbm_producao_latest.pkl` (v5, baixado do HF Hub)
- Dataset: `gold/dataset_features_v5_2026-04-26.parquet`
- Commit SHA: `c8aa647`
- Métricas oficiais (TimeSeriesSplit 5-fold): R²=0.741 ± 0.081 | MAE=9.7 ± 6.2
- Métricas operacionais (drift 26 SE): R²=0.866 | MAE=1.82
- Drift score: 0.116 | Nível: normal
- Retreino: não necessário

### Corrigido
- **Bug crítico: expm1 faltando na inferência** — modelo treinado com `log1p(target)`
  mas 3 módulos não aplicavam `expm1` na predição, causando R² negativo em todas
  as avaliações. Corrigido em `drift.py` e `test_pipeline.py` (ADR-024)
- `ci.yml` — path do DuckDB corrigido para absoluto via `${{ github.workspace }}`
- `test_pipeline.py` — `test_gold_periodo` agora usa `anos.max() >= 2025` (dinâmico)

### Refatorado (passos 1-17 completos)
- Passos 1-7 (commit 47): config, build_features, drift, validacao→dbt,
  publicacao, retreino, relatorio — todos atualizados para v2.0 latest
- Passos 8-13 (commit 48): mlflow_tracking, cache, alertas, dados,
  aba_previsao, aba_sobre — referências v4 removidas
- Passos 14-15 (commit 49): test_pipeline.py (10/10 PASS) + ci.yml v2.0
- Passos 16-17 (commits 45-46): gee e feature_engineering arquivados

### Validado — teste end-to-end 26/04/2026
```
Ingestão: 5/5 fontes OK (InfoDengue, NASA POWER, ONI, Trends, MODIS)
dbt run:  PASS=8 (6 views + 2 tables) em 1.17s
dbt test: PASS=59 em 2.11s
pytest:   10/10 PASS
Drift:    MAE=1.82 | R²=0.866 | normal
HF Hub:   Gold snapshot + latest publicados
Telegram: alerta recebido
MLflow:   run d225279f registrado
Relatório: publicado no HF Hub
```
### Documentação
- ADR-023: Integração dbt no pipeline Prefect
- ADR-024: Transformação log1p/expm1 — par obrigatório

---

## [2.1.0] — 2026-05-04

### Contexto
Pipeline autônomo validado na nuvem. Dashboard v5 completo com mapa
IDW dinâmico, UX unificada e deploy em produção.

### Pipeline autônomo (commits 57-58)
- Bronze completo no HF Hub — 40 arquivos, publicação incremental SHA256
- `restore_artifacts_hf.py` — script centralizado de restauração
- `publicacao.py` — manifesto `bronze_manifest_latest.json` rastreável
- CI/CD validado na nuvem — pipeline semanal completo sem dependência local
- MODIS timeout resolvido — skip em 0.02s quando Bronze existe
- Bug parser dbt test PASS/FAIL corrigido via regex

### IDW dinâmico (commits 59-62)
- `scripts/calibrar_pesos_idw.py` — calibração anual 143 bairros × 191 UBS
- `scripts/gerar_previsao_bairros.py` — distribuição semanal mass-preserving
- Scores IDW brutos armazenados (ratio max/min = 1315x)
- Frações normalizadas por município em runtime
- Limiares adaptativos percentílicos (P60/P75/P85/P95) por município
- Limiares embutidos no GeoJSON como metadados (fonte única de verdade)
- Bug corrigido: codigo_municipio 6 vs 7 dígitos no join UBS/shapefile
- Bug corrigido: normalização no nível errado (bairro vs município)
- Bug corrigido: thresholds hardcoded calibrados para pico sazonal
- `data_fim` dinâmico no dbt — default 2099-12-31, data atual via --vars

### Dashboard v5 (commits 63-65)
- Mapa choropleth IDW — polígonos 143 bairros com previsão SE+1→SE+4
- Legenda dinâmica — limiares separados por município quando "Todos"
- Sidebar unificada — município único controla todas as abas
- Caption "Aplica-se ao Mapa e Previsão" no slider de horizonte
- Série temporal filtrada pelo sidebar (seletor interno removido)
- Previsão filtrada pelo sidebar — mostra 2 gráficos quando "Todos"
- Tooltip e popup detalhados por bairro (4 horizontes no popup)
- Top 10 bairros por concentração prevista
- Nota metodológica com referências (Shepard 1968, Opasnet 2014)
- Deploy atualizado em dengue-mt-ifmt.streamlit.app

### Documentação
- ADR-025: Publicação incremental Bronze HF Hub
- ADR-026: data_fim dinâmico no dbt
- ADR-027: IDW dinâmico (revisado — bugs commit 62 + limiares adaptativos)

### Infraestrutura
- Gold atualizado até 2026-04-12 (856 registros)
- Pipeline semanal CI/CD: domingo 06h Cuiabá
- Drift operacional: score=0.119 | MAE=6.67 | R²=0.861 | normal

### Pendências
- Node.js 20 deprecation — atualizar actions no ci.yml antes de junho/2026
- aba_sobre.py — atualizar métricas e período
- Google Trends histórico — reconstrução via overlapping windows
- Relatório extensionista IFMT
- Artigo SENIC 2026

---

## [2.0.0-dev] — 2026-04-21

### Contexto
Refatoração do pipeline Prefect para arquitetura v2.0 completa —
integração do dbt run como etapa central de transformação,
substituindo o build_gold_dataset ad-hoc. Organização do repositório
com archive de notebooks, scripts e figuras do dataset v1.

### Adicionado
- `src/tasks/dbt_runner.py` — task Prefect para executar `dbt run` + `dbt test`
- `src/tasks/ingestao.py` — refatorado: 5 fontes Bronze, sem transformações Silver
- `src/tasks/ingestao.py` — `ingerir_modis()` adicionado como quinta fonte

### Alterado
- `src/pipeline_prefect.py` — `build_gold_dataset` substituído por `dbt run`
- `src/pipeline_prefect.py` — encerramento antecipado se `dbt run` falhar
  (Gold e modelo anteriores preservados em produção)
- `src/pipeline_prefect.py` — `ingerir_inmet` → `ingerir_infodengue` + `ingerir_modis`
- `src/config.py` — versões atualizadas para v5 (pipeline 2.0.0-dev, dataset v5, lgbm_v5)
- `src/config.py` — `ATRASOS_FONTES` atualizado: removidos `gee_ndvi` e `inmet`,
  adicionado `modis`
- `src/config.py` — `MODIS_USUARIO` e `MODIS_SENHA` via variáveis de ambiente

### Arquivado
- `src/tasks/build_gold.py` → `src/tasks/archive/`
- `src/tasks/gold_update.py` → `src/tasks/archive/`
- `notebooks/` — 14 notebooks do dataset v1 → `notebooks/archive/`
- `scripts/` — 3 scripts obsoletos → `scripts/historico/`
- `reports/` — 24 figuras, métricas e mapas do dataset v1 → `reports/archive/`

### Documentação
- 22 ADRs criados em `reports/adr/` — histórico completo de decisões
- `reports/archive/` — diário de bordo e decisoes_modelagem arquivados
- `README.md` e `ARCHITECTURE.md` — métricas atualizadas para v5

### Status
Pipeline v2.0 refatorado e validado (imports OK).

---


## [2.0.0-dev] — 2026-04-18

### Contexto
Conclusão da refatoração v2.0 — pipeline dbt completo com cobertura 100%
em todas as fontes. Gold v5 gerado e publicado no HF Hub.

### Adicionado
- `scripts/reconstruir_trends_historico.py` — reconstrução série histórica
  Google Trends 2018→2025 via overlapping windows (Scientific Data Nature 2026)
- `src/ingestion/modis.py` — MODIS NDVI/EVI via AppEEARS NASA Earthdata
- `dengue_mt_dbt/models/staging/modis/` — stg_modis.sql + yml
- `dengue_mt_dbt/models/staging/trends/stg_trends_historico.sql` + yml
- `dengue_mt_dbt/models/intermediate/int_dengue_mt.sql` — joins completos
- `dengue_mt_dbt/models/marts/mart_dengue_features.sql` + yml — Gold final ML
- `dengue_mt_dbt/macros/cast_date.sql` — 4 macros de padronização de datas
- `scripts/exportar_gold.py` — exporta DuckDB → Parquet + publica HF Hub
- `scripts/auditoria_intermediate.py` — auditoria de cobertura por fonte

### Cobertura final intermediate
```
NASA POWER:  100% ✅
ONI Index:   100% ✅
MODIS NDVI:  100% ✅ (substituiu GEE)
Trends:      100% ✅ (série histórica reconstruída)
```
### Gold v5
- 824 registros (412 SE × 2 municípios)
- 54 features com lags epidemiológicos anti-leakage
- Período: 2018-02-04 → 2025-12-28
- HF Hub: `edyestatistica/dengue-mt-medallion`

### Pipeline dbt completo
```
dbt run  → PASS=9  WARN=0 ERROR=0
dbt test → PASS=62 WARN=0 ERROR=0
```

### Status
Em desenvolvimento — próximo: treinamento LightGBM v5

---

## [2.0.0-dev] — 2026-04-19

### LightGBM v5 — Treinamento e Avaliação

**Modelo:** `models/lgbm_v5_producao.pkl`
**Dataset:** `gold/dataset_features_v5_2026-04-19.parquet`
**Schema:** `models/lgbm_v5_feature_schema_2026-04-19.json`

### Métricas
- R²=0.741 ± 0.081 | MAE=9.7 ± 6.2 casos/semana
- Validação: TimeSeriesSplit 5 folds | 2018→2025
- Transformação: log1p(y) — reduz impacto de surtos atípicos
- Nota: R² competitivo com IMDC24 (PNAS 2026) — nenhuma equipe
  internacional excelu no surto histórico de 2024/2025

### SHAP — Importância de Features
- casos_mm4: 46.5% (Cuiabá) / 45.4% (Várzea Grande)
- Top 5 features: 70.6% da importância total
- Google Trends confirmado como sinal antecipado relevante
- MODIS NDVI removido pelo SHAP — sinal redundante com lags climáticos

### Adicionado
- `scripts/treinar_lgbm_v5.py` — treinamento base
- `scripts/otimizar_lgbm_v5.py` — Optuna + SHAP feature selection
- `scripts/analisar_shap.py` — análise SHAP completa
- `scripts/avaliar_rolling_window.py` — avaliação múltiplos horizontes
- `scripts/registrar_modelo_v5.py` — registro formal + HF Hub
- `reports/shap/` — gráficos beeswarm e barras por município
- `models/lgbm_v5_feature_schema.json` — schema com métricas e hashes

---

## [2.0.0-dev] — 2026-04-08 (continuação)

### Refatoração src/ingestion — responsabilidade única Bronze

**Problema identificado:** módulos de ingestão misturavam responsabilidades —
Bronze, Silver, fallback e transformações no mesmo script.

**Decisão:** cada módulo `src/ingestion/` tem responsabilidade única —
apenas buscar API e salvar Bronze. Transformação Bronze→Silver é
exclusividade do dbt.

### Adicionado
- `scripts/backfill_bronze.py` — backfill histórico 2018→2026 (uso único)
- Bronze completo: 18 InfoDengue + 18 NASA POWER + 1 ONI + 1 Trends
- `dengue_mt_dbt/package-lock.yml` — trava versão dbt_utils 1.3.3

### Modificado
- `src/ingestion/infodengue.py` — responsabilidade única Bronze
- `src/ingestion/nasa_power.py` — responsabilidade única Bronze + coordenadas por município
- `src/ingestion/oni.py` — responsabilidade única Bronze
- `src/ingestion/trends.py` — responsabilidade única Bronze
- `dengue_mt_dbt/models/staging/sources.yml` — fontes externas Parquet via `meta.external_location`
- `dengue_mt_dbt/models/staging/nasa_power/stg_nasa_power.sql` — Cuiabá + VG separados
- `dengue_mt_dbt/models/staging/infodengue/stg_infodengue.sql` — `epoch_ms()` para timestamp
- `dengue_mt_dbt/models/staging/nasa_power/stg_nasa_power.yml` — chave composta municipio+data_se
- `.gitignore` — excluindo dev.duckdb e artefatos dbt

### Validado
```
dbt run  --select staging → PASS=5  WARN=0 ERROR=0
dbt test --select staging → PASS=37 WARN=0 ERROR=0
```

---

## [2.0.0-dev] — 2026-04-06

### Contexto
Auditoria completa das camadas Bronze e Silver revelou inconsistências críticas
na base de dados que comprometem a validade acadêmica do modelo. Início da
refatoração com rigor metodológico e boas práticas de engenharia de dados.

### Problemas identificados
- InfoDengue Bronze: coluna `data_iniSE` não padronizada
- NASA POWER Bronze: arquivo duplicado, coluna `data_str` não convertida
- ONI Silver: sem coluna datetime — merge incorreto no Gold
- SINAN Silver: coluna `DT_NOTIFIC` não renomeada
- GEE Bronze: 50% nulos por concatenação incorreta
- Gold 2025/2026: `municipio_id = NaN` — CWB + VG somados

### Decisões arquiteturais
- Adoção de dbt-core + DuckDB para transformações
- Cuiabá + Várzea Grande separados em todas as camadas
- Período definitivo: 2018→2025
- Fonte única por tipo: InfoDengue (casos) + NASA POWER (clima)
- Regras de agregação temporal embasadas em literatura
- Testes obrigatórios por camada dbt

### Adicionado
- `dengue_mt_dbt/` — projeto dbt inicializado
- `models/staging/` — 5 modelos staging com testes declarativos
- `models/staging/sources.yml` — fontes Bronze documentadas
- `packages.yml` — dbt_utils
- `scripts/auditoria_bronze.py` — auditoria camada Bronze
- `scripts/auditoria_silver.py` — auditoria camada Silver
- `reports/decisoes_modelagem.md` — seção Refatoração v2.0

### Status
Em desenvolvimento — pipeline v1.4.0 mantido em produção até v2.0 estável

---

## [1.4.0] — 2026-04-04

### Modelo
- Arquivo: `lgbm_v4_producao.pkl`
- Dataset: `gold/dataset_features_v4_2026-04-04.parquet`
- Commit SHA: `e22fb68`
- MAE: 57.3 casos/semana | R²: 0.063 (dados 2025/2026)
- Retreino: sim | Motivo: drift detectado — MAE=44.4 > limiar 25.0 | R²=-0.69 < 0.75

### Features
- 59 features — sem mudanças no contrato
- Adicionadas: nenhuma
- Removidas: nenhuma
- Contratos: validados — 13/13 testes pytest + Pandera

### Adicionado
- Arquitetura Medalhão completa — Bronze → Silver → Gold respeitando todas as camadas
- `src/ingestion/` — 4 módulos independentes por fonte (infodengue, nasa_power, oni, trends)
- `src/tasks/ingestao.py` — orquestração delegando lógica aos módulos (214 linhas)
- `src/tasks/build_gold.py` — atualização incremental Gold preservando histórico completo
- `src/features/feature_engineering.py` — `calcular_features_novas()` com contexto histórico
- Fallback automático HF Hub quando Gold local não encontrado
- Alinhamento temporal NASA POWER → InfoDengue (domingo = início SE brasileira)

### Corrigido
- `dropna()` no drift e retreino substituído por filtro `casos.notna()` — LightGBM lida com NaN nativamente
- Colunas duplicadas no merge GEE (`ndvi_x`, `ndwi_x`) resolvidas
- `UnboundLocalError: resumo` no pipeline quando retreino falha
- Erro `could not convert string to float: 'N/A'` no CHANGELOG automático
- `.gitignore` corrigido — dados, mlruns, modelos binários excluídos do git

### Infraestrutura
- Pipeline version: 1.0.1-dev
- Drift score: 0.290 | Nível: normal (13 registros — janela 90d)
- Fontes com fallback: nenhuma
- Nota: R² baixo (0.063) esperado — modelo retreinado com 1º ciclo completo 2025/2026. Meta: R²≥0.50 após 3+ ciclos.

### Baseado em literatura
- Rabanser et al. 2019 — Wasserstein distance requer mínimo 50 amostras (26 SE para dados semanais)
- Portaria SVS/MS nº 5/2010 — Semana Epidemiológica brasileira começa no domingo
- Codeco et al. 2018 — agregação climática por SE defensável para dengue

---

## [1.3.0] — 2026-04-03

### Modelo
- Arquivo: `lgbm_v4_producao.pkl`
- Dataset: `gold/dataset_features_v4_2026-03-31.parquet` (último snapshot automático)
- Commit SHA: `ccffb776`
- MAE: 2.41 casos/dia | R²: 0.987 (90d recente) | R²: 0.820 (TimeSeriesSplit oficial)
- Retreino: não | Motivo: modelo estável — drift score 0.205 (normal)

### Features
- 59 features — sem mudanças no contrato
- Adicionadas: nenhuma
- Removidas: nenhuma
- Contratos: validados — 13/13 testes pytest + Pandera

### Adicionado
- MLflow tracking — tags, params, metrics, artifacts, run_id no relatório
- Métricas por fold TimeSeriesSplit registradas no MLflow (retreino)
- Relatórios publicados no HF Hub — snapshot datado + `execucao_latest.md`
- Histórico de runs acumulado em `reports/historico_runs.parquet`
- Aba Monitoramento no dashboard — gráficos históricos de drift, MAE, R²
- CHANGELOG automático gerado a cada retreino promovido
- Dicionário de dados — `reports/data_dictionary.md` + `data_dictionary.csv`
- 65 variáveis documentadas (59 no modelo + 6 fora)
- Módulo canônico `src/features/build_features.py` — elimina feature drift treino/serving
- `build_features_serving()` integrado na API — mesma lógica do treino
- `atualizar_schema()` centralizado no módulo de features
- MLflow run_id na seção 6 do relatório de execução

### Infraestrutura
- Pipeline version: 1.0.1-dev
- MLflow backend: SQLite local (`mlflow.db`)
- Drift score: 0.205 | Nível: normal
- Fontes com fallback: nenhuma

---

## [1.2.0] — 2026-03-30

### Adicionado
- Relatório de execução automático — `src/tasks/relatorio.py` gera `reports/execucao_YYYY-MM-DD.md`
- Drift acionável com Wasserstein distance por feature — níveis Normal/Moderado/Crítico
- Parâmetros conservadores automáticos em drift crítico (n_estimators=1000, lr=0.01)
- Drift score por feature gravado no log e run_metadata.json
- Banner visual 🟢🟡🔴 no dashboard — status do modelo em tempo real
- Fallback ativo sinalizado no banner do dashboard
- Dashboard modularizado em `app/components/` — 6 arquivos de componentes
- Silver INMET disponibilizado no HF Hub para CI/CD
- Primeiro run automático do robô validado — 31/03/2026 00:48 UTC

### Corrigido
- CI/CD: `python src/pipeline_prefect.py` → `python -m src.pipeline_prefect`
- NASA POWER: atraso operacional 7d → 14d (verificação empírica 27/03/2026)
- Polars adicionado nas dependências do job de retreino no CI
- Banner do dashboard: leitura do run_metadata.json corrigida (campo `resultados`)

### Organização
- Scripts históricos de ingestão movidos para `scripts/historico/`
- `.gitignore` atualizado — lightning_logs, checkpoints, modelos obsoletos
- `src/` limpo — apenas pipeline e tasks em produção
- `__pycache__` adicionado ao `.gitignore`

### Baseado em literatura
- BMC Medical Research Methodology 2022 — critérios de promoção de modelos preditivos clínicos
- Wasserstein distance como métrica de drift — MLOps best practices (ScienceDirect 2025)


---

## [1.1.0] — 2026-03-27

### Adicionado
- Pipeline versioning — PIPELINE_VERSION, DATASET_VERSION, MODEL_VERSION
- Commit SHA amarrado ao schema e resumo do pipeline
- Feature Schema como fonte de verdade — contrato formal de features
- run_metadata.json — artefato de rastreabilidade por execução
- Snapshot datado Gold HF Hub — `dataset_features_v4_YYYY-MM-DD.parquet`
- Metadata JSON por snapshot — hash MD5, período, libs, commit_sha
- Logs estruturados — duração por etapa, nulos, métricas (observabilidade real)
- Modularização — pipeline de 726 → 130 linhas (src/tasks/)
- calcular_data_corte() — função única anti-leakage com fallback documentado
- DATA_CORTE propagado para todas as tasks de ingestão e retreino
- Cache local por fonte em data/cache/ — validade diferenciada por fonte
- Fallback automático quando API falha — pipeline não quebra
- scripts/verificar_atrasos.py — verificação empírica de atrasos por fonte

### Corrigido
- Feature Schema desatualizado — adicionados pipeline_version, commit_sha, dataset_version
- Data leakage operacional Google Trends — lag=7d obrigatório via DATA_CORTE
- Pipeline monolítico 726 linhas — modularizado em src/tasks/

### Baseado em literatura
- Codeco et al. 2018 (InfoDengue) — atraso SINAN Brasil
- PLOS Neglected Tropical Diseases 2024 — corte 15 semanas captura 95% notificações
- NASA POWER empirical test 27/03/2026 — dado < 7d retorna -999

---

## [1.0.0] — 2026-03-26

### Adicionado
- Dashboard online: https://dengue-mt-ifmt.streamlit.app
- Pipeline MLOps automático — GitHub Actions (domingo 06h Cuiabá)
- 13 testes automatizados pytest + Pandera
- Feature Schema Contract — `lgbm_v4_feature_schema.json`
- Retreino automático com promoção/rollback condicional
- Evidently drift monitoring — 13/13 features com drift 2023-2024
- FastAPI — 4 endpoints REST
- Nowcasting SINAN — fator de correção por semana epidemiológica
- Google Trends MT — r=0.922 com casos confirmados
- NDBI via GEE — índice de urbanização dinâmico
- Arquitetura Medalhão Bronze/Silver/Gold
- Hugging Face Hub — storage custo zero

### Modelo
- LightGBM v4 — MAE=17.6 | R²=0.820 | sMAPE=31.5%
- 59 features: clima + lags + NDVI/NDWI/NDBI + ENSO + Trends + Nowcasting
- Validação: TimeSeriesSplit 5 folds

### Infraestrutura
- Custo total: R$ 0,00
- Stack: Python 3.11 + Polars + LightGBM + Streamlit + FastAPI + Prefect

---

## [0.3.0] — 2026-03-22

### Adicionado
- Arquitetura Medalhão implementada com Polars
- Silver SINAN — 390.048 registros (2007-2024)
- Hugging Face Hub configurado como storage remoto
- Score de risco v2 — percentil rank por unidade de saúde
- Mapa Folium — 191 unidades de saúde mapeadas

---

## [0.2.0] — 2026-03-16

### Adicionado
- Rolling Window LightGBM — R²=0.892
- Ensemble LightGBM + CNN/BiLSTM — R²=0.873
- LSTM v1 e v2 testados
- Dashboard Streamlit v1 — 4 abas

---

## [0.1.0] — 2026-03-11

### Adicionado
- Configuração do ambiente Python 3.11 + Conda
- Pipeline ETL: SINAN, INMET, NASA POWER, GEE, NOAA ONI
- Feature Engineering — 55 features × 2.242 registros
- EDA completa com 10 visualizações
- XGBoost baseline — R²=0.805