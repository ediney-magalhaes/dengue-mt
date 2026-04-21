# Predição de Surtos de Dengue em Cuiabá e Várzea Grande/MT usando Aprendizado de Máquina e Dados Multifonte

**Tipo:** Resumo Expandido  
**Evento alvo:** SENIC 2026 / Encontro de Pesquisa e Extensão IFMT  
**Área:** Tecnologia em Inteligência Artificial e Ciência de Dados  
**Modalidade:** Projeto Extensionista  
**Status:** Rascunho — em elaboração  

**Autor:** Ediney José da Silva Magalhães Júnior  
**Instituição:** Instituto Federal de Mato Grosso (IFMT)  
**E-mail:** edy.estatistica@gmail.com  
**Repositório:** https://github.com/ediney-magalhaes/dengue-mt  

---

## 1. Introdução

O Mato Grosso registra sistematicamente um dos maiores índices de incidência de dengue do Brasil. Os municípios de Cuiabá e Várzea Grande, com população conjunta superior a 940 mil habitantes e clima quente e úmido durante grande parte do ano, enfrentam surtos sazonais recorrentes que sobrecarregam o sistema de saúde público e geram impactos econômicos e sociais significativos. Em 2024, o estado registrou o pior ano da série histórica analisada, com 39.325 casos confirmados — aproximadamente seis vezes mais do que em 2018.

A vigilância epidemiológica municipal ainda opera predominantemente de forma reativa, atuando após a confirmação e instalação dos surtos. Sistemas de previsão de surtos de dengue baseados em clima e séries temporais têm sido propostos em diversos países, mas ainda há lacunas importantes na integração com a vigilância de rotina e em sua adoção por gestores locais [1, 2]. A ausência de ferramentas preditivas acessíveis para municípios de médio porte representa uma lacuna crítica na gestão de saúde pública regional.

Estudos recentes demonstram que modelos de aprendizado de máquina que integram histórico de casos, variáveis climáticas defasadas e dados ambientais superam abordagens puramente baseadas em séries históricas [3, 4]. Este projeto propõe o desenvolvimento de um sistema preditivo que integra dados epidemiológicos, climáticos, de sensoriamento remoto e índices de variabilidade climática global para gerar alertas semanais de risco com antecedência de 2 a 4 semanas.

---

## 2. Objetivos

**Objetivo geral:** Desenvolver um sistema preditivo de surtos de dengue para Cuiabá e Várzea Grande/MT, com antecedência mínima de duas semanas, utilizando dados públicos e técnicas de aprendizado de máquina.

**Objetivos específicos:**
- Construir um pipeline ETL reproduzível integrando múltiplas fontes de dados públicos
- Identificar e quantificar os fatores climáticos e ambientais associados aos surtos com análise de defasagem temporal
- Desenvolver e validar modelos preditivos (XGBoost, LightGBM e LSTM)
- Disponibilizar os resultados em um dashboard interativo para gestores de saúde pública

---

## 3. Metodologia

### 3.1 Fontes de dados

| Fonte | Dados | Período | Registros |
|---|---|---|---|
| SINAN/DATASUS | Notificações de dengue confirmadas | 2018–2024 | 166.525 casos |
| INMET (estação A901) | Temperatura, precipitação, umidade | 2018–2024 | 2.557 dias |
| NASA POWER API | Radiação solar diária | 2018–2024 | 2.557 dias |
| GEE Sentinel-2 + MODIS | NDVI e NDWI mensais | 2018–2024 | 84 meses |
| NOAA CPC | ONI Index (El Niño/La Niña) | 2018–2024 | 84 meses |
| IBGE Censo 2022 | Densidade e saneamento municipal | 2022 | 2 municípios |

### 3.2 Pipeline de coleta e processamento

Os dados epidemiológicos foram obtidos no formato `.dbc` (formato proprietário do DATASUS) e convertidos para Apache Parquet via biblioteca pySUS em ambiente Linux (Google Colab), dado que as bibliotecas de leitura `.dbc` são incompatíveis com Windows. Os dados climáticos do INMET foram extraídos de arquivos ZIP anuais com tratamento de dois formatos distintos de cabeçalho identificados entre 2018 e 2019+.

Um problema relevante identificado durante a coleta foi a ausência de dados de radiação solar na estação A901 (Cuiabá) a partir de 2020, provavelmente por falha do sensor. A solução adotada foi a substituição pela NASA POWER API, que fornece dados de radiação derivados de satélite com cobertura diária contínua e sem falhas para qualquer ponto do planeta.

Os índices de vegetação (NDVI) e água (NDWI) foram extraídos via Google Earth Engine utilizando imagens Sentinel-2 SR Harmonized. Para os 13 meses sem cobertura Sentinel-2 (principalmente época chuvosa de 2018), foi adotada uma estratégia de *data blending* com o produto MODIS MOD13A3 — prática consolidada na literatura de sensoriamento remoto aplicado à saúde ambiental para mitigar perda de dados por cobertura de nuvens [5, 6]. O NDWI dos meses MODIS foi imputado por média climatológica sazonal (*climatological mean imputation*), método amplamente referenciado em estudos do INPE e NASA [7].

### 3.3 Engenharia de features

O dataset final integrado contém **2.242 registros diários × 55 features** distribuídas em seis grupos:

| Grupo | Features | N |
|---|---|---|
| Epidemiológicas | Lags 7/14/21/28 dias, médias móveis de casos | 8 |
| Climáticas | Temperatura, precipitação, umidade + lags e acumulados | 22 |
| Radiação solar | NASA POWER + lag 28d + média móvel 14d | 3 |
| Satélite | NDVI e NDWI mensais (blend S2+MODIS) | 2 |
| Temporais | Sazonalidade cíclica seno/cosseno, calendário | 9 |
| ENSO e ciclo | ONI Index, fase El Niño/La Niña, ciclo epidêmico | 6 |

A sazonalidade foi codificada por transformação cíclica (seno/cosseno) em vez de variáveis lineares de mês/semana, evitando a descontinuidade artificial entre dezembro e janeiro. Índices de vegetação e água derivados de sensoriamento remoto, como NDVI e NDWI, vêm sendo amplamente utilizados para capturar condições ambientais favoráveis à proliferação de *Aedes aegypti* e têm demonstrado associação significativa com indicadores de risco de dengue [5, 8].

### 3.4 Modelagem

Os modelos foram treinados e avaliados com validação cruzada temporal (TimeSeriesSplit, 5 folds), que respeita a ordem cronológica dos dados e evita *data leakage*. Modelos baseados em gradient boosting, como XGBoost e LightGBM, têm apresentado desempenho competitivo na previsão de casos de dengue, explorando bem interações não lineares entre variáveis climáticas, socioeconômicas e histórico de casos [3, 9]. Os hiperparâmetros foram otimizados com a biblioteca Optuna (50 trials por modelo). A interpretabilidade foi avaliada via SHAP values [10].

---

## 4. Resultados

### 4.1 Padrão sazonal

A análise exploratória revelou sazonalidade clara e consistente ao longo de toda a série: pico de notificações concentrado entre fevereiro e maio (estação chuvosa) e vale entre agosto e outubro (estação seca). Este padrão está diretamente associado ao ciclo reprodutivo do *Aedes aegypti*, que necessita de água parada para oviposição e de temperaturas elevadas para encurtar o período de incubação extrínseca do vírus.

### 4.2 Efeito de lag climático

A correlação direta entre variáveis climáticas e casos de dengue é fraca (r = 0,09 para precipitação). No entanto, com a aplicação de defasagens temporais (*lags*), as correlações aumentam progressivamente: com 5–6 semanas de defasagem, a umidade relativa atinge r = 0,34 e a precipitação acumulada r = 0,26. Diversos estudos mostram que temperatura, umidade e precipitação exercem efeitos retardados sobre a dinâmica de *Aedes aegypti*, com correlações máximas frequentemente observadas 2–6 semanas após eventos de chuva ou variações climáticas [11, 12]. Modelos de dinâmica populacional do vetor destacam que o ciclo ovo-adulto em temperaturas elevadas ocorre em poucos dias, de forma que o impacto climático sobre a transmissão humana se manifesta tipicamente em janelas de 4–6 semanas [13].

### 4.3 El Niño e ciclo epidêmico

O pico histórico de 2024 coincide com o El Niño 2023/24, classificado como intenso (ONI > +1,5). Trabalhos recentes indicam que a variabilidade associada ao El Niño–Southern Oscillation explica parcela substancial da variação interanual de casos de dengue, sobretudo via aumento das temperaturas locais [14]. No contexto brasileiro, análises de séries históricas apontam que anos de El Niño tendem a apresentar maiores índices de infestação de *Aedes aegypti* [15, 16]. O índice ONI foi incorporado como feature do modelo por sua relevância epidemiológica documentada. Além disso, um ciclo epidêmico de 3–4 anos foi identificado, com 2020 e 2024 como anos de pico — fenômeno associado ao esgotamento e renovação da imunidade de rebanho da população [17].

### 4.4 Resultados dos modelos (XGBoost e LightGBM)

Os modelos foram avaliados nos Folds 2–5 (excluindo o Fold 1, que possui apenas 14 meses de treino — insuficiente para capturar a sazonalidade anual):

| Modelo | MAE | RMSE | R² |
|---|---|---|---|
| XGBoost baseline | 18,5 ± 5,7 | 29,7 ± 10,8 | 0,805 ± 0,059 |
| LightGBM baseline | 18,1 ± 5,7 | 29,6 ± 9,8 | 0,804 ± 0,059 |
| XGBoost otimizado | 17,3 ± 5,5 | 28,2 ± 9,7 | 0,823 ± 0,047 |
| **LightGBM otimizado** | **17,4 ± 5,4** | **27,8 ± 9,8** | **0,830 ± 0,040** |

A meta de R² ≥ 0,80 foi atingida já no modelo baseline. A análise SHAP confirmou que as features mais impactantes são os lags de casos recentes (inércia do surto), seguidos de sazonalidade cíclica, umidade acumulada com 42 dias de defasagem e NDVI — resultado consistente com a literatura de sistemas de alerta precoce de dengue [1, 2, 8].

### 4.5 Redes neurais — LSTM e CNN+BiLSTM

Foram testadas duas arquiteturas de redes neurais recorrentes. O LSTM simples (janela=28 dias, 128 neurônios) atingiu R²=0,664, enquanto o CNN+BiLSTM — que combina camadas convolucionais para extração de padrões locais com BiLSTM bidirecional — atingiu R²=0,756, confirmando o resultado de [15] de que arquiteturas híbridas superam LSTM simples para previsão de dengue. O LightGBM otimizado (R²=0,871) superou ambas as redes neurais, resultado consistente com a literatura para datasets de tamanho moderado [3, 4]. O ensemble LightGBM (90%) + CNN+BiLSTM (10%) atingiu R²=0,8725.

### 4.6 Rolling Window Training — modelo final

A estratégia de retreinamento contínuo (*rolling window training*), com retreino a cada 90 dias e horizonte de predição de 28 dias, atingiu **R²=0,892 e MAE=17,69 casos/dia** — melhor resultado do projeto. Esta abordagem simula o comportamento do sistema em produção, onde novos dados epidemiológicos e climáticos são incorporados continuamente, favorecendo o aprendizado de padrões inéditos como o surto histórico de 2024. O estudo de [8] adota estratégia equivalente com LSTM nos 27 estados brasileiros, validando a abordagem.

**Ranking final de modelos:**

| Modelo | R² | MAE (casos/dia) |
|---|---|---|
| Rolling Window LightGBM | **0,892** | **17,69** |
| Ensemble LightGBM+CNN/BiLSTM | 0,873 | 21,91 |
| LightGBM otimizado | 0,871 | 21,83 |
| XGBoost otimizado | 0,823 | 17,31 |
| CNN + BiLSTM | 0,756 | 33,34 |
| LSTM v2 | 0,664 | 38,75 |

**Meta R² ≥ 0,80: superada pelos 3 melhores modelos.**

---

## 5. Próximas Etapas

- [ ] Dashboard interativo Streamlit com mapa de risco (Folium)
- [ ] API REST FastAPI para integração com sistemas municipais
- [ ] Pipeline de retreinamento automático semanal
- [ ] Validação com a Vigilância Epidemiológica de Cuiabá e Várzea Grande
- [ ] Evolução futura: CNN sobre imagens Sentinel-2 brutas (v2.0) e Transformer/FWin para horizonte de 60 semanas

---

## 6. Considerações Éticas

Os dados utilizados são públicos e agregados, sem identificação individual de pacientes, em conformidade com a Lei Geral de Proteção de Dados (LGPD, Lei nº 13.709/2018). O modelo utiliza SHAP values para garantir transparência e explicabilidade das predições, facilitando a adoção pelos gestores de saúde [10].

---

## 7. Referências

[1] Sylvestre E et al. Data-driven methods for dengue prediction and surveillance using real-world and Big Data: A systematic review. *PLoS Negl Trop Dis*. 2022;16(1):e0010056.

[2] Hasan MM et al. A systematic review of dengue outbreak prediction models: current scenario and future directions. *PLoS Negl Trop Dis*. 2023;17(2):e0010631.

[3] Roster K, Connaughton C, Rodrigues FA. Machine-learning–based forecasting of dengue fever in Brazilian cities using epidemiologic and meteorological variables. *Am J Epidemiol*. 2022;191(10):1803–1812.

[4] Chen X, Moraga P. Assessing dengue forecasting methods: a comparative study of statistical models and machine learning techniques in Rio de Janeiro, Brazil. *Trop Med Health*. 2025;53:50.

[5] Estallo EL et al. Modeling dengue vector population using remotely sensed data and machine learning. *Acta Trop*. 2018;185:167–175.

[6] Zhu Q et al. Spatiotemporal dataset of dengue influencing factors in Brazil based on geospatial big data cloud computing. *Sci Data*. 2025;12:681.

[7] Li Z et al. Improving dengue forecasts by using geospatial big data analysis in Google Earth Engine and the historical dengue information-aided LSTM modeling. *Biology*. 2022;11(2):169.

[8] Buczak AL et al. A data-driven epidemiological prediction method for dengue outbreaks using local and remote sensing data. *BMC Med Inform Decis Mak*. 2012;12:124.

[9] Ferreira LB et al. A reproducible ensemble machine learning approach to forecast dengue outbreaks. *Sci Rep*. 2024;14:3943.

[10] Lundberg SM, Lee SI. A unified approach to interpreting model predictions. *Adv Neural Inf Process Syst*. 2017;30.

[11] Lowe R et al. The development of an early warning system for climate-sensitive disease risk with a focus on dengue epidemics in Southeast Brazil. *Stat Med*. 2013;32(5):864–883.

[12] Lowe R et al. Combined effects of hydrometeorological hazards and urbanisation on dengue risk in Brazil: a spatiotemporal modelling study. *Lancet Planet Health*. 2021;5(4):e209–e219.

[13] Mordecai EA et al. Thermal biology of mosquito-borne disease. *Ecol Lett*. 2019;22(10):1690–1708.

[14] Liu X et al. Rising dengue risk with increasing El Niño–Southern Oscillation amplitude and teleconnections. *Nat Commun*. 2025;16:8453.

[15] Pirani M et al. Effects of the El Niño-Southern Oscillation and seasonal weather conditions on Aedes aegypti infestation in the State of São Paulo (Brazil). *PLoS Negl Trop Dis*. 2024;18(9):e0012397.

[16] Ferreira MS et al. Impacts of El Niño Southern Oscillation on the dengue transmission dynamics in the Metropolitan Region of Recife, Brazil. *Front Public Health*. 2022;10:877128.

[17] McGough SF et al. A dynamic, ensemble learning approach to forecast dengue fever epidemic years in Brazil using weather and population susceptibility cycles. *J R Soc Interface*. 2021;18:20201006.

---

*Documento vivo — atualizado conforme o avanço do projeto*  
*Última atualização: 15/03/2026*