# ADR-004 — Dataset SINAN+INMET substituído por InfoDengue API + NASA POWER
 
**Status:** Aceito (substitui ADR-002 e ADR-003)  
**Data:** 04/04/2026  
**Tema:** Arquitetura de Dados / Fonte Principal
 
---
 
## Contexto
 
A abordagem original do projeto usava duas fontes independentes processadas
localmente:
 
- **SINAN** (DATASUS): notificações individuais de dengue em formato `.dbc`
  — requer conversão manual, pipeline semi-automático, dados com atraso de
  publicação de até 15 semanas
- **INMET**: dados climáticos de estações automáticas em ZIPs anuais
  — apenas estação A901 (Cuiabá) disponível como proxy para os dois municípios
Após EDA inicial, foram identificados **problemas estruturais** nesse dataset:
- Dados SINAN são notificações individuais — agregação semanal por município
  requer limpeza extensa e é propensa a subnotificação
- INMET fornece apenas 1 estação para cobrir 2 municípios — sem dados de
  outras variáveis climáticas relevantes (radiação, umidade relativa completa)
- Pipeline de coleta era manual, não automatizável no GitHub Actions
- Impossível manter dados atualizados sem intervenção manual semanal
Esses problemas comprometiam a viabilidade do projeto como sistema de
monitoramento contínuo — premissa fundamental do extensionista.
 
## Decisão
 
Abandonar SINAN + INMET como fontes principais e adotar:
 
**InfoDengue API** como fonte epidemiológica:
- Dados já agregados por semana epidemiológica (SE) e município
- Inclui casos confirmados, estimados, nowcasting, Rt, nível de alerta
- Variáveis climáticas ERA5 já integradas (temperatura, umidade, precipitação)
- API REST pública, gratuita, mantida pela Fiocruz
- Atualização semanal automática — compatível com pipeline GitHub Actions
- Geocodes: Cuiabá `5103403`, Várzea Grande `5108402`
**NASA POWER API** como fonte climática complementar:
- Dados diários agrupáveis por semana para os geocodes exatos
- Cobertura global, sem dependência de estação física próxima
- Variáveis adicionais: radiação solar, umidade específica, velocidade do vento
- API REST pública e gratuita (NASA)
**Arquitetura adotada:** dbt-core + DuckDB medallion (ver ADR-008)
 
## Consequências
 
- Pipeline 100% automatizável via GitHub Actions
- Dados atualizados semanalmente sem intervenção manual
- Cobertura 2018→presente para ambos os municípios
- Elimina etapas de conversão `.dbc` e processamento de ZIPs climáticos
- Dataset de treino com qualidade superior ao SINAN bruto
## Alternativas consideradas
 
- Manter SINAN com pipeline de limpeza mais robusto — descartado pela
  impossibilidade de automação e pelo atraso de publicação de 15 semanas
- OpenDENGUE (global) — descartado por granularidade insuficiente para
  municípios específicos do MT
## Referências
 
- Codeco et al. 2018 — InfoDengue: a dengue surveillance system
- InfoDengue API: https://info.dengue.mat.br/api/alertcity