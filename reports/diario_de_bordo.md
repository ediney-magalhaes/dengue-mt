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

**Próximos passos:**
- [x] Atualizar resumo expandido com resultados finais de modelagem
- [x] Merge dev → main (entrega Semana 4-5)
- [ ] Iniciar Semana 5 — CNN para imagens de satélite
- [ ] Iniciar desenvolvimento do dashboard Streamlit

---

## 📅 Semana 5 — Modelos Avançados
> *A preencher*

---

## 📅 Semana 6 — NN para Imagens de Satélite
> *A preencher*

---

## 📅 Semana 7 — Ensemble e Validação Final
> *A preencher*

---

## 📅 Semana 8 — Dashboard Streamlit
> *A preencher*

---

## 📅 Semana 9 — App Mobile MVP
> *A preencher*

---

## 📅 Semana 10 — Integração e Polimento
> *A preencher*

---

## 📅 Semana 11 — Entrega e Publicação
> *A preencher*


---

*Instituto Federal de Mato Grosso (IFMT)*
*Projeto Extensionista — Dengue MT*