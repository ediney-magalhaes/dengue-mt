# ADR-005 — Google Earth Engine + Sentinel-2 para dados de vegetação
 
**Status:** Substituído por ADR-014  
**Data:** 14/03/2026  
**Tema:** Ingestão de Dados / Geoespacial
 
---
 
## Contexto
 
O projeto previu desde o início o uso de dados de vegetação e cobertura do solo
como proxy para identificação de ambientes favoráveis à proliferação do
*Aedes aegypti*. NDVI (Normalized Difference Vegetation Index) e NDWI
(Normalized Difference Water Index) são variáveis estabelecidas na literatura
de modelos preditivos de dengue.
 
O Google Earth Engine (GEE) é a plataforma de referência para processamento
de imagens de satélite em escala — utiliza Sentinel-2 (resolução 10m) e MODIS
como fontes principais.
 
## Decisão
 
Utilizar GEE com imagens **Sentinel-2** para extração de NDVI e NDWI
para as regiões de Cuiabá e Várzea Grande:
 
- Conta registrada no plano Comunidade via IFMT
- 3 scripts GEE criados em `src/gee/`
- Extração manual de séries temporais via interface web do GEE
- Dados exportados para Google Drive e baixados localmente
## Problemas identificados em operação
 
- **Sem automação:** GEE não permite execução programática sem aprovação
  de conta para uso da API Python (`earthengine-api`) — solicitação pendente
- **Coleta manual:** cada atualização exigia acesso à interface web,
  execução manual e download — incompatível com pipeline semanal automático
- **Cobertura incompleta:** dados coletados manualmente até 2024;
  2025 ausente — comprometia o dataset de treino
- **Custo zero comprometido:** escalonamento futuro dependeria de cota paga
- **Resolução excessiva:** Sentinel-2 a 10m para análise municipal
  é over-engineered — resolução 1km do MODIS é suficiente para o escopo
## Consequências da substituição
 
Esta abordagem foi abandonada por ser incompatível com a premissa fundamental
do projeto: **custo zero e automação total**.
 
Ver ADR-014 para a solução adotada (MODIS via AppEEARS NASA Earthdata).
 
## Aprendizado registrado
 
- GEE é excelente para análises pontuais e exploratórias, mas não para
  pipelines de produção sem aprovação da API
- Resolução espacial deve ser calibrada ao escopo — granularidade municipal
  não justifica resolução sub-métrica
 