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

A vigilância epidemiológica municipal ainda opera predominantemente de forma reativa, atuando após a confirmação e instalação dos surtos. A ausência de ferramentas preditivas acessíveis para municípios de médio porte representa uma lacuna crítica na gestão de saúde pública regional. Este projeto propõe o desenvolvimento de um sistema preditivo baseado em aprendizado de máquina (ML) que integra dados epidemiológicos, climáticos, de sensoriamento remoto e socioeconômicos para gerar alertas semanais de risco com antecedência de 2 a 4 semanas.

---

## 2. Objetivos

**Objetivo geral:** Desenvolver um sistema preditivo de surtos de dengue para Cuiabá e Várzea Grande/MT, com antecedência mínima de duas semanas, utilizando dados públicos e técnicas de aprendizado de máquina.

**Objetivos específicos:**
- Construir um pipeline ETL reproduzível integrando múltiplas fontes de dados públicos
- Identificar e quantificar os fatores climáticos e ambientais associados aos surtos
- Desenvolver e validar modelos preditivos (XGBoost, LSTM e CNN)
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

Os índices de vegetação (NDVI) e água (NDWI) foram extraídos via Google Earth Engine utilizando imagens Sentinel-2 SR Harmonized. Para os 13 meses sem cobertura Sentinel-2 (principalmente época chuvosa de 2018), foi adotada uma estratégia de *data blending* com o produto MODIS MOD13A3, prática validada pela literatura de sensoriamento remoto aplicado à saúde pública. O NDWI dos meses MODIS foi imputado por média climatológica sazonal (*climatological mean imputation*), método amplamente utilizado em estudos do INPE e NASA.

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

A sazonalidade foi codificada por transformação cíclica (seno/cosseno) em vez de variáveis lineares de mês/semana, evitando a descontinuidade artificial entre dezembro e janeiro.

---

## 4. Resultados Preliminares

### 4.1 Padrão sazonal

A análise exploratória revelou sazonalidade clara e consistente ao longo de toda a série: pico de notificações concentrado entre fevereiro e maio (estação chuvosa) e vale entre agosto e outubro (estação seca). Este padrão está diretamente associado ao ciclo reprodutivo do *Aedes aegypti*, que necessita de água parada para oviposição e de temperaturas elevadas para encurtar o período de incubação extrínseca do vírus.

### 4.2 Efeito de lag climático

A correlação direta entre variáveis climáticas e casos de dengue é fraca (r = 0,09 para precipitação). No entanto, com a aplicação de defasagens temporais (*lags*), as correlações aumentam progressivamente: com 5–6 semanas de defasagem, a umidade relativa atinge r = 0,34 e a precipitação acumulada r = 0,26. Este resultado confirma o ciclo biológico do vetor — a chuva de hoje não causa casos hoje, mas gera criadouros que produzem mosquitos infectantes em 4 a 6 semanas.

### 4.3 Tendência crescente e El Niño

O pico histórico de 2024 coincide com o El Niño 2023/24, classificado como intenso (ONI > +1,5). O índice ONI foi incorporado como feature do modelo por sua relevância epidemiológica documentada. Além disso, um ciclo epidêmico de 3–4 anos foi identificado, com 2020 e 2024 como anos de pico — fenômeno associado ao esgotamento e renovação da imunidade de rebanho da população.

### 4.4 Features mais preditivas (análise de correlação)

As features com maior correlação com os casos diários de dengue foram:
- `casos_lag_7d`: r = 0,93 — inércia do surto
- `casos_lag_14d`: r = 0,89
- `casos_mm_7d`: r = 0,85 — média móvel semanal
- `semana_seno`: r = 0,57 — sazonalidade cíclica
- `ndvi`: r = 0,40 — cobertura vegetal como proxy de criadouros
- `umidade_mm_28d`: r = 0,34 — umidade acumulada com lag

---

## 5. Próximas Etapas

*(A preencher conforme o avanço do projeto)*

- [ ] Treinamento e validação do modelo baseline XGBoost com TimeSeriesSplit
- [ ] Otimização de hiperparâmetros com Optuna
- [ ] Desenvolvimento do modelo LSTM para séries temporais
- [ ] Ensemble final e mapa de risco por bairro
- [ ] Dashboard Streamlit com mapa interativo (Folium)
- [ ] Validação com a Vigilância Epidemiológica municipal

---

## 6. Considerações Éticas

Os dados utilizados são públicos e agregados, sem identificação individual de pacientes, em conformidade com a Lei Geral de Proteção de Dados (LGPD, Lei nº 13.709/2018). O modelo utilizará técnicas de explicabilidade (SHAP values) para garantir transparência nas predições.

---

## 7. Referências

*(A completar — referências principais já identificadas)*

- MINISTÉRIO DA SAÚDE. Sistema de Informação de Agravos de Notificação (SINAN). Disponível em: https://datasus.saude.gov.br
- INMET. Banco de Dados Meteorológicos. Disponível em: https://bdmep.inmet.gov.br
- NASA. POWER API — Prediction of Worldwide Energy Resources. Disponível em: https://power.larc.nasa.gov
- NOAA. Oceanic Niño Index (ONI). Climate Prediction Center. Disponível em: https://www.cpc.ncep.noaa.gov
- GOOGLE EARTH ENGINE. Sentinel-2 SR Harmonized. Disponível em: https://developers.google.com/earth-engine
- IBGE. Censo Demográfico 2022. Disponível em: https://censo2022.ibge.gov.br

---

*Documento vivo — atualizado conforme o avanço do projeto*  
*Última atualização: 14/03/2026*