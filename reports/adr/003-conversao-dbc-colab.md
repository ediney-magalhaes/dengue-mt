# ADR-003 — Conversão .dbc → Parquet via Google Colab
 
**Status:** Substituído por ADR-004  
**Data:** 11–12/03/2026  
**Tema:** Ingestão de Dados / Engenharia
 
---
 
## Contexto
 
Após o download dos arquivos `.dbc` via `datasus-fetcher` (ADR-002), era necessário
convertê-los para Parquet — formato colunar eficiente para processamento em Python.
A biblioteca `pyreaddbc`, responsável por ler `.dbc`, é incompatível com Windows
(requer `unistd.h`). O ambiente local de desenvolvimento é Windows 11.
 
## Decisão
 
Utilizar **Google Colab** (ambiente Linux gratuito) para a etapa de conversão:
 
- `pySUS` instalado no Colab funciona perfeitamente em Linux
- Arquivos `.dbc` carregados via Google Drive
- Conversão e filtro por MT (`SG_UF_NOT == '51'`) executados no Colab
- Parquets resultantes baixados para o OneDrive local
- Script `src/converter_sinan_dbc.py` documenta e reproduz o processo
**Tratamento especial por ano:**
- 2018–2023: processamento direto, filtro por UF
- 2022: colunas com dtype `object` convertidas para `str` antes do Parquet
- 2024: processado em chunks (219 partições) por limite de RAM do Colab gratuito (~12 GB)
**Resultado:** dataset SINAN MT 2018–2024 consolidado com **216.479 registros**.
 
## Consequências
 
- Conversão bem-sucedida sem custo adicional (Colab gratuito)
- Etapa manual e dependente de ambiente externo — não integrável ao pipeline automático
- Script documentado garante reprodutibilidade mesmo fora do pipeline
## Limitações identificadas
 
- Colab gratuito tem limite de RAM — arquivos grandes (>200 MB) precisam de chunks
- Processo semi-manual: requer upload/download via Google Drive
- Não automatizável no GitHub Actions por depender de sessão interativa
## Nota
 
Esta decisão foi posteriormente superada pela adoção do **InfoDengue API**
como fonte principal (ver ADR-004), que fornece dados já agregados por semana
epidemiológica — eliminando completamente a necessidade de processar `.dbc`.
 
## Aprendizado registrado
 
- Colab é uma alternativa viável para etapas únicas de conversão que requerem Linux
- Processar grandes arquivos em chunks é preferível a aumentar RAM — mais robusto
- Dados nacionais + filtro local é mais simples que tentar filtrar no download
 