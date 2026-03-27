# 📓 Diário de Bordo — Dengue MT

> Registro pessoal de progresso, decisões técnicas e aprendizados do projeto.

---

## 📅 Semana 1 — Configuração do Ambiente

### 09/03/2026

**✅ O que foi feito hoje:**
- Instalação e configuração do Miniconda (conda 26.1.1)
- Criação do ambiente isolado `dengue-mt` com Python 3.11
- Criação da estrutura de pastas do projeto no OneDrive
- Instalação das bibliotecas da Semana 1 (Pandas, NumPy, Matplotlib, Seaborn, Jupyter)
- Registro do kernel "Dengue MT" no Jupyter
- Teste do ambiente com notebook `00_teste_ambiente.ipynb` — todas as libs OK
- Configuração do repositório GitHub com branches `main` e `dev`
- Registro no Google Earth Engine (plano Comunidade — IFMT)
- Criação do README completo com contexto, arquitetura, escolhas técnicas e roadmap

**Decisões técnicas tomadas:**
- Pasta do projeto no OneDrive para backup automático — ambiente Conda fora do OneDrive para evitar conflitos de sincronização
- Adotada convenção **Conventional Commits** para versionamento (`feat:`, `docs:`, `fix:`, etc.)
- Estratégia de branches: `dev` para desenvolvimento, `main` para entregas estáveis

**Aprendizados:**
- Conda requer aceitação de Terms of Service nos canais antes do primeiro uso (`conda tos accept`)
- `conda init powershell` é necessário para integração com o terminal do VSCode no Windows
- Primeira execução do Jupyter demora mais — kernel inicializa na primeira célula

**Dificuldades encontradas:**
- Terminal do VSCode não mostrava `(dengue-mt)` após ativação — resolvido com `conda init powershell` + reinício do VSCode

**Próximos passos (Semana 1 — continuação):**
- [x] Baixar dados SINAN/MT (2018–2024) no DATASUS
- [x] Baixar dados climáticos do INMET para MT

---

## 📅 Semana 1 — Engenharia de Dados I

### 11/03/2026

**✅ O que foi feito hoje:**
- Retorno ao ambiente — verificação de que conda, git e branch `dev` estavam ativos e corretos
- Tentativa de instalação do `pySUS` para download dos dados SINAN — falhou por incompatibilidade do `pyreaddbc` com Windows (ausência do `unistd.h`)
- Instalação do `Microsoft C++ Build Tools` para resolver dependência de compilação
- Descoberta e instalação do `datasus-fetcher` como solução alternativa ao pySUS
- Download bem-sucedido dos dados SINAN/Dengue 2018–2024 (~624 MB) via `datasus-fetcher`
- Criação do script `src/download_sinan.py` para reprodutibilidade do pipeline
- Download bem-sucedido dos dados climáticos INMET 2018–2024 (todas estações automáticas) via script Python com header customizado
- Criação do script `src/download_inmet.py` para reprodutibilidade do pipeline
- Preenchimento completo do questionário de planejamento do projeto para o orientador

**Decisões técnicas tomadas:**
- Abandonado o `pySUS` no Windows — substituído pelo `datasus-fetcher` que não requer compilação
- Dados SINAN baixados em escala nacional (BR) — filtro por MT será aplicado no Python durante a limpeza
- Dados INMET baixados como pacote anual completo — filtro por estações do MT na Semana 2
- Scripts de download salvos em `src/` para garantir reprodutibilidade do pipeline de coleta

**Aprendizados:**
- Portais do governo (DATASUS, INMET) bloqueiam downloads diretos via navegadores modernos e requisições sem `User-Agent`
- O `datasus-fetcher` é a forma mais confiável de acessar dados do DATASUS via Python no Windows
- Adicionar `User-Agent: Mozilla/5.0` nas requisições HTTP resolve bloqueios 403 em portais públicos
- Arquivos `.dbc` são o formato nativo do DATASUS — precisarão de conversão para CSV/Parquet na Semana 2

**Dificuldades encontradas:**
- `pySUS` incompatível com Windows — requer `unistd.h` que não existe no sistema
- FTP do DATASUS e URLs do S3 bloqueados para acesso direto — resolvido com `datasus-fetcher`
- Portal INMET retornava erro 403 sem header `User-Agent` — resolvido com requisição customizada

**Próximos passos (Semana 2):**
- [x] Converter arquivos `.dbc` do SINAN para CSV/Parquet
- [x] Filtrar dados por estado MT e municípios Cuiabá e Várzea Grande
- [x] Descompactar e explorar os ZIPs do INMET — filtrar estações do MT
- [x] Fazer merge das bases epidemiológica e climática por data
- [x] Criar notebook `01_eda_exploratoria.ipynb` com primeiras visualizações

---

## 📅 Semana 2 — Engenharia de Dados II
### 11/03/2026 — Sessão noturna

**✅ O que foi feito:**
- Início da Semana 2 — Engenharia de Dados
- Tentativa de instalação do `pyreaddbc` no Windows — falhou novamente (unistd.h)
- Estratégia alternativa: uso do Google Colab para conversão dos .dbc para Parquet
- Instalação do `pySUS` no Colab (Linux) — funcionou perfeitamente
- Conversão e filtro por MT bem-sucedidos para 2018–2023:
  - 2018: 10.131 registros
  - 2019: 17.855 registros
  - 2020: 47.631 registros
  - 2021: 34.174 registros
  - 2022: 35.341 registros
  - 2023: 28.605 registros
  - **Total parcial: 173.737 registros do MT**
- 2024 falhou por limite de RAM do Colab gratuito (arquivo de 274MB)

**Decisões técnicas:**
- Conversão .dbc → Parquet será feita via Google Colab (Linux)
- Dados nacionais são baixados e filtrados por `SG_UF_NOT == '51'` (código MT)
- 2024 será processado separadamente com leitura em chunks para economizar RAM

**Dificuldades:**
- Colab gratuito tem limite de RAM (~12GB) — arquivo de 2024 com 274MB excedeu ao ser carregado em memória
- Solução: processar 2024 em chunks e salvar incrementalmente

**Próximos passos:**
- [x] Processar 2024 em chunks no Colab
- [x] Salvar dataset consolidado MT em Parquet
- [x] Baixar arquivo para o OneDrive
- [x] Explorar colunas e qualidade dos dados


### 12/03/2026

**✅ O que foi feito:**
- Processamento do ano 2022 com tratamento especial de colunas object
- Processamento do ano 2024 em chunks (219 arquivos parquet) para economizar RAM
- Download e organização de todos os arquivos em `data/processed/sinan/`
- Criação do script `src/converter_sinan_dbc.py` — reproduz todo o processo de conversão
- Dataset SINAN MT 2018–2024 completo: **216.479 registros**

**Decisões técnicas:**
- Colunas com dtype `object` convertidas para `str` antes de salvar em Parquet
- 2024 processado arquivo por arquivo (219 partições) para evitar estouro de RAM
- Script de conversão documentado com instruções para rodar no Google Colab

**Próximos passos:**
- [x] Explorar colunas do dataset SINAN — dicionário de variáveis
- [x] Descompactar e filtrar dados climáticos INMET por estações do MT
- [x] Fazer merge das bases epidemiológica e climática por data
- [x] Criar notebook `01_eda_exploratoria.ipynb`


## 📅 Semana 2 —  EDA e Feature Engineering
### 13/03/2026

**✅ O que foi feito:**
- Instalação do `pyarrow` e `fastparquet` no ambiente `dengue-mt` (necessário para leitura de Parquet no Windows)
- Carregamento do dataset SINAN MT completo (216.479 registros, 123 colunas) no Jupyter
- Análise exploratória completa dos dados epidemiológicos:
  - Identificação dos municípios: Cuiabá (510340) e Várzea Grande (510790)
  - Casos confirmados: 166.525 (76,9% do total)
  - Classificação: Dengue simples (163.534), c/ Alarme (2.711), Grave (280)
- Criação de 4 visualizações epidemiológicas salvas em `reports/`:
  - `fig01_casos_por_ano.png` — tendência crescente 2018–2024
  - `fig02_sazonalidade.png` — heatmap mensal + padrão sazonal
  - `fig03_perfil_epidemiologico.png` — sexo, faixa etária, hospitalização
  - `fig04_serie_temporal.png` — série semanal completa com pico Mai/2024
- Processamento dos ZIPs do INMET — extração da estação A901 (Cuiabá)
- Geração do dataset climático diário `data/processed/inmet/inmet_cuiaba_2018_2024.parquet` (2.557 dias)
- Merge dos dados epidemiológicos e climáticos por data — `data/processed/dengue_clima_merged.parquet` (2.538 dias)
- Análise de correlação com lag temporal — descoberta do efeito de defasagem
- Criação dos scripts `src/processar_inmet.py` e `src/criar_dataset_merged.py`

**Descobertas analíticas:**
- Sazonalidade clara: pico de casos em Fevereiro–Maio (estação chuvosa)
- Pós-2020 os surtos ficaram maiores — hipóteses: novo sorotipo, El Niño, imunidade esgotada
- Correlação simples clima × dengue é fraca (r ≈ 0.09–0.25) — efeito de lag explica isso
- Com defasagem de 5–6 semanas: umidade chega a r = 0.34, precipitação r = 0.26
- **Conclusão:** o modelo deve usar variáveis climáticas com 4–6 semanas de antecedência

**Decisões técnicas:**
- Estação A901 (Cuiabá) usada como proxy climático para Cuiabá e Várzea Grande (~10km de distância)
- Notebooks para análise exploratória e narrativa; scripts `src/` para pipelines reproduzíveis
- Lag de 4–6 semanas será incorporado como feature no modelo preditivo

**Dificuldades:**
- OneDrive interfere com salvamento do Jupyter (`File Save Error: Failed to fetch`) — contornado reiniciando o servidor Jupyter
- Kernel perde variáveis após reinício — resolvido mantendo célula de imports no topo do notebook

**Próximos passos (Semana 2 — conclusão):**
- [x] Merge dev → main (entrega Semana 2)
- [x] Atualizar README com descobertas da EDA
- [x] Iniciar Semana 3 — dados geoespaciais (Google Earth Engine)

---

## 📅 Semana 3 — Dados goespaciais (Google Earth Engine)
### 14/03/2026

**O que foi feito:**
- Extração de NDVI e NDWI via Google Earth Engine (Sentinel-2 + MODIS blend)
  - 3 scripts GEE criados em `src/gee/`
  - Cobertura 100% com blend S2 (71 meses) + MODIS (13 meses)
  - NDWI dos meses MODIS imputado com média sazonal
- Radiação solar via NASA POWER API — 2.557 dias sem falhas
  - Substituiu sensor INMET A901 defeituoso a partir de 2020
- ONI Index (El Niño/La Niña) via NOAA — 84 meses 2018–2024
  - 27 meses El Niño / 28 Neutro / 29 La Niña
- Feature Engineering completo — dataset final com 55 features × 2.242 registros

**Descobertas:**
- Sensor de radiação INMET A901 sem dados de 2020 a 2024 — NASA POWER como solução
- Features de lags de casos são as mais preditivas (r > 0.80)
- Sazonalidade cíclica (seno/cosseno) superior à representação linear de mês/semana
- NDVI correlacionado positivamente com casos (r = 0.40) — vegetação = criadouros
- ONI 2023/24 = El Niño intenso — confirma hipótese do pico de 2024

**Decisões técnicas:**
- Blend Sentinel-2 + MODIS preferido ao Sentinel-2 puro (cobertura 100% vs 84%)
- Imputação sazonal do NDWI justificada pela literatura (climatological mean imputation)
- Anos de pico definidos como 2020 e 2024 — base para feature ciclo_epidemico
- fase_enso codificada numericamente: La Niña=-1, Neutro=0, El Niño=+1

**Próximos passos:**
- [x] Dados IBGE — Censo 2022 Cuiabá/VG salvo em `data/external/`
- [x] Merge dev → main (entrega Semana 3)
- [x] Semana 4 — modelo baseline XGBoost

---


## 📅 Semana 4 — Modelo Baseline
### 15/03/2026

**O que foi feito:**
- Criação do `requirements.txt` com dependências do projeto
- Instalação das bibliotecas de ML: xgboost, lightgbm, scikit-learn, optuna, shap
- Notebook `03_modelo_baseline.ipynb` criado
- Modelo baseline XGBoost treinado com TimeSeriesSplit (5 folds)
- Modelo LightGBM treinado para comparação
- Otimização de hiperparâmetros com Optuna (50 trials cada)
- Análise de importância de features (XGBoost gain + SHAP values)

**Resultados (Folds 2-5):**

| Modelo | MAE | RMSE | R² |
|---|---|---|---|
| XGBoost baseline | 18.5 ± 5.7 | 29.7 ± 10.8 | 0.805 ± 0.059 |
| LightGBM baseline | 18.1 ± 5.7 | 29.6 ± 9.8 | 0.804 ± 0.059 |
| XGBoost otimizado | 17.3 ± 5.5 | 28.2 ± 9.7 | 0.823 ± 0.047 |
| LightGBM otimizado | 17.4 ± 5.4 | 27.8 ± 9.8 | **0.830 ± 0.040** |

**Meta atingida: R² ≥ 0.80**

**Descobertas:**
- XGBoost e LightGBM têm performance equivalente — LightGBM 6x mais rápido
- Feature mais importante: `casos_lag_7d` (40% da importância)
- SHAP confirma presença de `umidade_lag_42d` e `oni_index` — features ambientais contribuem
- Picos extremos (>300 casos/dia) ainda subestimados — limitação a endereçar no LSTM
- Fold 1 problemático (R²=-0.44) por pouco dado histórico — excluído das métricas finais

**Decisões técnicas:**
- NaNs de radiação (41 registros) removidos por ser mais defensável academicamente
- TimeSeriesSplit com 5 folds — evita data leakage temporal
- Optuna com 50 trials — balanço entre qualidade e tempo de execução
- LightGBM otimizado selecionado como modelo principal por R² e estabilidade

**Próximos passos:**
- [x] LSTM para séries temporais de casos semanais
- [ ] CNN para imagens de satélite
- [x] Ensemble final XGBoost/LightGBM + LSTM
- [x] Atualizar resumo expandido com resultados da modelagem

### 16/03/2026

**O que foi feito:**
- Instalação do TensorFlow 2.21.0
- Notebook `04_modelo_lstm.ipynb` criado
- LSTM v1 (janela=14, 64 neurônios): R²=0.653
- LSTM v2 (janela=28, 128 neurônios): R²=0.664
- CNN + BiLSTM (janela=28): R²=0.756 — melhor rede neural
- Otimização de pesos do ensemble — LightGBM (90%) + CNN+BiLSTM (10%): R²=0.8725
- Rolling Window Training — retreino a cada 90 dias: **R²=0.892** 🏆
- Discussão estratégica sobre crescimento do dataset e retreinamento contínuo
- Instalação do Streamlit, Folium, Plotly
- Dashboard v1 criado em `app/dashboard.py`
- 4 abas funcionando: Série Temporal, Clima & Dengue, Previsão, Sobre o Modelo
- Sistema de alertas (Alto/Moderado/Baixo) baseado na previsão
- Sidebar com modelo ativo, R², MAE e última atualização

**Ranking final de modelos:**

| Modelo | R² | MAE |
|---|---|---|
| Rolling Window LightGBM | **0.892** | 17.69 |
| Ensemble LightGBM+CNN/BiLSTM | 0.873 | 21.91 |
| LightGBM otimizado | 0.871 | 21.83 |
| XGBoost otimizado | 0.823 | 17.31 |
| CNN + BiLSTM | 0.756 | 33.34 |
| LSTM v2 | 0.664 | 38.75 |
| LSTM v1 | 0.653 | 41.77 |

**Meta R² ≥ 0.80: SUPERADA**

**Descobertas:**
- LightGBM supera redes neurais no dataset atual (2.242 registros) — alinhado com literatura [3,4]
- CNN+BiLSTM superior ao LSTM simples (R²=0.756 vs 0.664) — literatura [15] confirmada
- Ensemble 90/10 melhora marginalmente (+0.0015) — CNN+BiLSTM contribui informação complementar
- Rolling window é a melhor estratégia — simula produção real com retreinamento contínuo
- MAE dos retreinos: baixo na estação seca (4-11), alto no pico do surto (34-42) — esperado

**Decisões técnicas:**
- Modelo final: Rolling Window LightGBM (retreino a cada 90 dias, horizonte 28 dias)
- LSTM e CNN+BiLSTM documentados como experimentos — perspectiva de melhoria com dataset maior
- GPU não disponível no Windows nativo — CPU suficiente para o tamanho atual do dataset
- Retreinamento contínuo via Airflow planejado para Semana 9+

**Decisão estratégica:**
- Dataset crescerá semana a semana em produção — favorecerá as redes neurais no futuro
- Transformer/FWin e STGCN identificados na literatura como próximas evoluções do modelo
- LSTM com janela deslizante semanal (retreino contínuo) é referência para Brasil [8]

**⏭️ Próximos passos:**
- [ ] Dashboard Streamlit com mapa interativo de risco por bairro (Folium)
- [ ] Conectar previsão real ao modelo LightGBM treinado
- [ ] Mapa interativo Cuiabá/VG com shapefile IBGE
- [ ] API REST FastAPI
- [ ] Pipeline de retreinamento automático semanal
- [ ] CNN sobre imagens Sentinel-2 — agendada para v2.0 do produto


## 📅 Semana 5 — Ajuste de modelos (Comparação com LightGBM)
### 18/03/2026

**O que foi feito:**
- Revisão estratégica completa do projeto — 3 pontos críticos redefinidos
- Planejamento de arquitetura de produção custo zero (DagsHub, Prefect, Dagster, Polars)
- TFT série única diária: R²=0.459 — underfitting confirmado
- TFT multi-município semanal (79 municípios × 175 semanas): R²=0.230
- Google Trends coletado (84 meses, r=0.782) — reservado para TFT futuro
- N-HiTS recursivo: R²=0.805 — supera meta
- N-BEATS recursivo: R²=0.787

**Ranking final de modelos:**

| Modelo | R² | MAE | Categoria |
|---|---|---|---|
| Rolling Window LightGBM | **0.892** | 17.69 | produção |
| LightGBM otimizado | 0.871 | 21.83 | baseline |
| N-HiTS recursivo | 0.805 | 27.36 | deep learning |
| N-BEATS recursivo | 0.787 | 30.10 | deep learning |
| CNN + BiLSTM | 0.756 | 33.34 | deep learning |
| LSTM v2 | 0.664 | 38.75 | deep learning |
| TFT série única | 0.459 | 43.97 | deep learning |
| TFT multi-município | 0.230 | 9.27 | deep learning |

**Descobertas:**
- TFT requer série histórica longa (102+ semanas encoder) — Pillay et al. (2026) IJERPH
- N-HiTS é o melhor modelo de deep learning puro para o dataset atual
- Google Trends (r=0.782) é poderoso mas mensal — melhor integrado ao TFT semanal
- Série SINAN disponível desde 1993 — expansão futura resolverá limitações do TFT

**Decisões estratégicas:**
- Modelo de produção: Rolling Window LightGBM (R²=0.892)
- Arquitetura custo zero: DagsHub + Prefect + Dagster + Polars
- TFT revisitado após expansão série para 1993-presente
- PatchTST e TimesNet agendados para versão 2.0

**⏭️ Próximos passos — Semana 5 (continuação):**
- [x] PatchTST — estado da arte forecasting 2023-2024
- [ ] TimesNet — converte séries 1D em 2D para padrões sazonais
- [x] TFT revisitado com série histórica 1993-presente (SINAN)
- [ ] Após esgotar modelos → Semana 6: Score de risco por bairro


### 21/03/2026

**O que foi feito:**
- Expansão da série histórica SINAN: 2007–2024 (18 anos, 440.002 registros)
- Identificação do esquema de classificação por período:
  - 2000-2006: sem dados MT no SINAN federal
  - 2007-2013: `CLASSI_FIN` = '1','2','3'
  - 2014-2016: período de transição (ambos os esquemas)
  - 2017-2024: `CLASSI_FIN` = '10','11','12'
- Série semanal histórica consolidada: 888 semanas | 142 municípios
- Configuração do Kaggle Notebooks com GPU Tesla T4
- TFT testado em 5 configurações diferentes no Kaggle com GPU
- Ranking completo final: 11 modelos avaliados

**Ranking completo final:**

| Modelo | R² | MAE | Status |
|---|---|---|---|
| Rolling Window LightGBM | **0.892** | 17.69 | ✅ PRODUÇÃO |
| LightGBM otimizado | 0.871 | 21.83 | baseline |
| N-HiTS recursivo | 0.805 | 27.36 | deep learning |
| N-BEATS recursivo | 0.787 | 30.10 | deep learning |
| CNN + BiLSTM | 0.756 | 33.34 | deep learning |
| LSTM v2 | 0.664 | 38.75 | deep learning |
| TFT diário 2018-2024 | 0.459 | 43.97 | experimental |
| TFT série histórica 2007-2024 | 0.290 | 245.12 | experimental |
| TFT multi-município 2018-2024 | 0.230 | 9.27 | experimental |
| TFT série histórica com clima | 0.174 | 257.02 | experimental |
| TFT multi-município histórico | -0.169 | 13.74 | experimental |

**Decisão técnica definitiva:**
- **Modelo de produção: Rolling Window LightGBM (R²=0.892)**
- TFT documentado como experimento — requer normalização hierárquica por porte de município e dados de sorotipo quando disponíveis
- Fase 2 — Modelagem oficialmente concluída

**Descobertas:**
- TFT com múltiplos municípios piora com alta variabilidade entre séries (50k vs 200 casos)
- GPU T4 Kaggle: treinamento 10x mais rápido que CPU local
- Série histórica 2007-2024 não melhora TFT sem normalização adequada
- LightGBM supera todos os modelos de deep learning testados — alinhado com literatura [3,4,9]

**Próximos passos — Semana 6:**
- [ ] Score de risco por bairro (shapefile + Folium)
- [x] Migrar scripts para Polars
- [ ] Configurar DagsHub + MLflow

---

## 📅 Semana 6: Score de risco por bairro + Polars + Hugging Face

### 22/03/2026

**O que foi feito:**
- Instalação do Polars 1.39.3
- Implementação da Arquitetura Medalhão com Polars (`src/medallion_migration.py`)
- Criação das camadas Bronze/Silver/Gold em `data/`
- Silver SINAN consolidado: 390.048 registros (2007–2024) com filtro robusto por período
- Silver INMET: 2.478 registros validados e clipados
- Silver GEE: 84 registros sem nulos
- Gold: dataset_features_v2 (2.242×55) + série histórica (888 semanas)
- Avaliação e descarte do DagsHub — problema de autenticação S3 no Windows
- Configuração do Hugging Face Hub como storage remoto (gratuito, ilimitado para dados públicos)
- Upload completo Silver + Gold para `edyestatistica/dengue-mt-medallion`
- Decisão estratégica: Bronze permanece local (dados públicos reproduzíveis pelas fontes originais)

**Decisões técnicas:**
- Polars substitui Pandas nos pipelines de ingestão — execução paralela nativa, menor consumo de memória
- Hugging Face Hub substitui DagsHub — mais simples, sem dependência de protocolo S3
- Bronze permanece local (OneDrive) — Silver e Gold versionados remotamente no HF Hub
- `.gitignore` atualizado para ignorar `data/bronze/`, `data/silver/`, `data/gold/`

**Decisão estratégica:**
- Stack de produção custo zero definitiva:
  - Código: GitHub
  - Dados Silver+Gold: Hugging Face Hub (ilimitado público)
  - Dashboard: Streamlit Community Cloud (próxima etapa)
  - API: Render.com free tier (próxima etapa)

**Próximos passos — Semana 6 (continuação):**
- [x] Score de risco por bairro (shapefile IBGE + Folium)

### 23/03/2026

**O que foi feito:**
- Análise e priorização das 7 lacunas do projeto com referencial teórico
- Roadmap revisado — retreinamento dataset_features_v3 confirmado para Semana 7
- Instalação: geopandas, folium, streamlit-folium, mapclassify
- Download shapefile IBGE: 141 municípios MT + 143 bairros Cuiabá/VG (IBGE 2022)
- Avaliação de 3 proxies para score de risco por bairro:
  - Proxy 1 (ID_UNIDADE × CNES): escolhida — dados reais, referencial sólido
  - Proxy 2 (NDBI + exposição territorial): agendada para Semana 7
  - Proxy 3 (vulnerabilidade estrutural IBGE+OSM+GEE): v2.0
- `ID_UNIDADE` adicionado ao Silver SINAN (100% preenchido em 18 anos)
- Silver re-migrado e reenviado ao Hugging Face Hub
- API CNES: 3.099 estabelecimentos extraídos (Cuiabá + VG) com paginação manual
- Score de risco v1 calculado: 158 unidades × carga histórica SINAN 2007-2024
- Mapa Folium gerado: `reports/mapa_risco_dengue.html`

**Decisões técnicas:**
- Proxy ID_UNIDADE escolhida — Bohm et al. (2023, Pathogens and Global Health)
  usa áreas de abrangência dos centros de saúde como unidade espacial para dengue
- Score v1 usa volume histórico absoluto — normalização por incidência (casos/pop)
  agendada para próxima sessão [Lacuna 3]
- PNAD Contínua descartada para modelo preditivo — granularidade insuficiente

**Pendências identificadas:**
- Score assimétrico — 146/158 unidades classificadas como "Muito Baixo"
- Necessário normalizar por incidência por 100k hab (área de abrangência estimada)
- Indicador "Baixa Confiança" [Lacuna 3] ainda não implementado

**Próximos passos — Semana 6 (conclusão):**
- [x] Normalizar score por incidência (casos / pop estimada área abrangência)
- [x] Indicador "Baixa Confiança" para unidades com < 50 casos históricos
- [x] Merge dev → main

### 24/03/2026

**O que foi feito:**
- Reconstrução limpa do notebook `08_score_risco_bairro` (zero a zero)
- Git rebase corrompido resolvido (limpeza manual `.git/rebase-merge`)
- CNES rebuscado via API (3.099 estabelecimentos) e salvo localmente
- Score v2 implementado com percentil rank (elimina distorção hospital vs UBS)
- Indicador "Baixa Confiança" implementado (< 50 casos históricos)
- Mapa Folium v2 gerado com heatmap + círculos + legenda

**Resultados Score v2:**

| Risco | Unidades |
|---|---|
| Muito Alto | 39 |
| Alto | 38 |
| Moderado | 38 |
| Baixo | 38 |
| Muito Baixo | 38 |
| ⚠️ Baixa Confiança | 107 |
| ✅ Alta Confiança | 84 |

**Decisões técnicas:**
- Percentil rank escolhido sobre normalização por máximo — distribuição equilibrada
- Heatmap usa apenas unidades de Alta Confiança (≥ 50 casos)
- CNES salvo em `data/external/cnes_cuiaba_vg.parquet` para reuso
- Score salvo em `data/external/score_risco_v2.parquet`

**Próximos passos — Semana 7:**
- [ ] Nowcasting — fator de correção SINAN [Lacuna 2]
- [ ] Feature `municipio_id` + normalização por 100k hab [Lacuna 1]
- [ ] NDBI via GEE [Lacuna 6]
- [ ] Google Trends (pytrends) — Infoveillance
- [ ] Retreinamento dataset_features_v3 + Rolling Window LightGBM
- [ ] Prefect — pipeline de ingestão automática

---

## 📅 Semana 7: Arquitetura Medalhão + Prefect + Dashboard v2

### 24/03/2026 (continuação)
#### Nowcasting + Features v3 + Retreinamento

**O que foi feito:**
- Notebook `09_nowcasting_sinan.ipynb` criado
- Análise do lag de digitação SINAN: 99.9% dos registros digitados no mesmo ano
- Fator de completude calculado por semana epidemiológica (2018-2023)
- Nowcasting implementado: fator 3.0 em jan/fev, ~1.0 em nov/dez
- dataset_features_v3 gerado: 2.242 × 60 features (+5 novas)

**Novas features v3:**
- `fator_nowcasting` — fator de correção por semana epidemiológica
- `casos_nowcast` — casos corrigidos pelo fator
- `municipio_id` — ID do município (expansão futura)
- `casos_por_100k` — incidência por 100k habitantes
- `casos_nowcast_por_100k` — incidência corrigida por 100k

**Descoberta relevante:**
- O "rabo de peixe" é mais grave em jan/fev (fator 3.0) — exatamente o pico do surto
- Correção crítica para o modelo não subestimar o início dos surtos

**Próximos passos — Semana 7 (continuação):**
- [x] Retreinar Rolling Window LightGBM com dataset_features_v3
- [x] Comparar R² v2 vs v3
- [x] NDBI via GEE [Lacuna 6]
- [x] Google Trends (pytrends)
- [x] Prefect — pipeline de ingestão automática

### 25/03/2026

**O que foi feito:**
- Retreino LightGBM v3 — MAE=17.5 | RMSE=27.9 | R²=0.829 | sMAPE=32.4%
- Diagnóstico MAPE alto — distorção por valores baixos (1-10 casos): MAPE=137.8%
- sMAPE implementado como métrica recomendada pela literatura
- Google Trends MT extraído — r=0.922 com casos (lag=0)
- dataset_features_v3_trends gerado (64 features)
- NDBI via GEE extraído — correlação r=-0.446 com casos
- dataset_features_v4 gerado (67 features)
- Prefect 3.6.23 — pipeline semanal implementado e testado

**Métricas finais LightGBM v3 (Folds 2-5):**

| Métrica | Média | ±DP |
|---|---|---|
| MAE | 17.5 | ±5.6 casos/dia |
| RMSE | 27.9 | ±9.6 casos/dia |
| R² | 0.829 | ±0.039 |
| sMAPE | 32.4% | ±5.5% |

**Decisões técnicas:**
- sMAPE adotado sobre MAPE — robusto a valores baixos (literatura: Hyndman & Koehler 2006)
- Google Trends lag=0 tem r=0.922 — comportamento diferente de grandes centros (contribuição original)
- NDBI interpolação linear — justificada pela literatura (gaps < 20%, série periódica)
- Prefect substitui Airflow/Dagster — mais simples, free tier, Python nativo
- Data Contracts implementados no próprio Prefect (sem dbt — volume não justifica)

**Descobertas relevantes:**
- Google Trends em MT é simultâneo aos casos (lag=0) — diferente do padrão clássico
- Drift detectado no modelo v3 ao avaliar dataset v4 — comportamento esperado e correto
- NDBI negativo na maioria dos meses — área predominantemente verde (Cuiabá + vegetação)

**Próximos passos — Semana 8:**
- [x] Retreinar LightGBM v4 com dataset_features_v4 (67 features)
- [x] Drift monitoring com Evidently
- [x] FastAPI — endpoints de previsão
- [x] Deploy Streamlit Community Cloud
- [ ] Agendar Prefect na nuvem (Prefect Cloud free tier)

---

## 📅 Semana 8: Retreino v4 + FastAPI + Dashboard v2

### 25/03/2026 (continuação)

**O que foi feito:**
- LightGBM v4 retreinado com dataset_features_v4 (59 features)
- FastAPI implementada — 4 endpoints: `/previsao`, `/score-risco`, `/historico`, `/saude`
- Dashboard Streamlit v2 — conectado à FastAPI + mapa Folium integrado
- 4 abas funcionais: Mapa de Risco, Série Temporal, Previsão, Sobre

**Métricas LightGBM v4 (Folds 2-5):**

| Métrica | Média | ±DP |
|---|---|---|
| MAE | 17.6 | ±5.3 casos/dia |
| RMSE | 28.4 | ±9.3 casos/dia |
| R² | 0.820 | ±0.052 |
| sMAPE | 31.5% | ±4.9% |

**Decisões técnicas:**
- Google Trends e NDBI não melhoram R² histórico — valor em produção (nowcasting)
- FastAPI como backend — desacopla modelo do dashboard, permite múltiplos clientes
- Dashboard conectado via API — sidebar mostra métricas em tempo real
- Mapa Folium integrado no Streamlit via `streamlit-folium`

**Descobertas:**
- v4 ≈ v3 ≈ v2 em R² — modelo robusto, novas features não degradam performance
- sMAPE melhorou levemente (32.4% → 31.5%) — tendência positiva
- Dashboard funcional como MVP para gestores de saúde pública

**Próximos passos — Semana 8:**
- [x] Deploy Streamlit Community Cloud
- [ ] Prefect Cloud — agendamento automático na nuvem
- [x] Evidently — drift monitoring com relatórios visuais

### 25/03/2026 (Semana 8 — conclusão)

**O que foi feito:**
- Deploy Streamlit Community Cloud — https://dengue-mt-ifmt.streamlit.app
- Arquitetura 100% nuvem implementada — HF Hub como storage central
- Modelo lgbm_v4_producao.pkl publicado no HF Hub
- Dashboard v2 funcional na nuvem sem dependências locais
- Evidently 0.7.x — relatório de drift gerado

**Resultados Evidently:**
- 13/13 features com drift detectado (100%)
- Período: Referência 2018-2023 vs Atual 2023-2024
- Teste: Wasserstein distance (normed)
- Features críticas: oni_index, casos_lag_7d/14d/28d, temp_media, ndvi

**Interpretação do drift:**
- El Niño 2023-2024 excepcional — oni_index fora do padrão histórico
- Surto histórico 2024 — lags de casos em novo patamar
- Justifica Rolling Window LightGBM como escolha correta

**Arquitetura final — 100% nuvem custo zero:**
- Código: GitHub
- Dados + Modelo: Hugging Face Hub
- Dashboard: Streamlit Community Cloud
- Pipeline: Prefect (local) → Prefect Cloud (Semana 9)

**Próximos passos — Semana 9:**

**Produto:**
- [x] Prefect Cloud — agendamento automático semanal na nuvem
- [ ] CHANGELOG.md — rastrear versões do produto

**Documentação acadêmica:**
- [ ] Dicionário de dados — descrever cada feature (base para o artigo)
- [ ] Decisões de modelagem — justificar escolhas técnicas com referências
- [ ] Atualizar resumo expandido com resultados finais (v3 → v4, deploy, drift)
- [ ] Relatório extensionista IFMT

**Semana 10:**
- [ ] Artigo completo SENIC 2026
- [ ] Manual do usuário — para gestores de saúde usarem o dashboard

---

## 📅 Semana 9: MLOps Pipeline + CI/CD + Automação

### 26/03/2026

**O que foi feito:**
- pytest + Pandera — 13 testes automatizados (dados + modelo + nowcasting)
- GitHub Actions CI — roda a cada push em dev/main
- Schedule semanal — domingo 06h Cuiabá (09h UTC) automático
- Job de retreino automático no CI — testes → retreino → HF Hub
- Feature Schema Contract — `lgbm_v4_feature_schema.json`
- Pipeline Prefect atualizado com retreino real do modelo
- Lógica de promoção/rollback — novo modelo só promovido se R² não cair > 5%
- HF_TOKEN configurado como GitHub Secret

**Arquitetura MLOps implementada:**
```
Todo domingo 06h (automático — GitHub Actions):
  ├── pytest 13 testes — valida dados e modelo
  ├── Pandera — contratos de dados
  ├── Prefect — ingestão + drift + retreino
  ├── Feature Schema — garante compatibilidade de features
  ├── Promoção condicional — rollback automático se performance cair
  └── Upload HF Hub — dashboard atualiza automaticamente
```

**Decisões técnicas:**
- Feature Schema salvo em JSON — contrato formal entre dataset e modelo
- Promoção condicional: R² novo >= R² atual - 0.05
- GitHub Actions schedule substitui Prefect Cloud (custo zero)
- alertas.jsonl como fallback de notificações

**Próximos passos — Semana 9 (continuação):**
- [ ] MLflow — versionamento formal de experimentos
- [ ] CHANGELOG.md
- [ ] Dicionário de dados
- [ ] Relatório extensionista IFMT
---

*Instituto Federal de Mato Grosso (IFMT)*
*Projeto Extensionista — Dengue MT*