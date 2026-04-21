# ADR-002 — SINAN via datasus-fetcher (pySUS incompatível com Windows)
 
**Status:** Substituído por ADR-004  
**Data:** 11/03/2026  
**Tema:** Ingestão de Dados
 
---
 
## Contexto
 
O SINAN (Sistema de Informação de Agravos de Notificação) distribui dados de dengue
em formato `.dbc` — formato binário proprietário do DATASUS. A biblioteca padrão
da comunidade para acesso programático é o `pySUS`, que depende internamente do
`pyreaddbc` para leitura dos arquivos `.dbc`.
 
O ambiente de desenvolvimento do projeto roda Windows 11.
 
## Problema identificado
 
`pySUS` e `pyreaddbc` requerem o header `unistd.h` para compilação — arquivo
presente apenas em sistemas Unix/Linux. A instalação falhou no Windows mesmo
após instalação do `Microsoft C++ Build Tools`.
 
Portais do governo (DATASUS, INMET) também bloqueiam downloads diretos via
requisições sem `User-Agent`, retornando erro 403.
 
## Decisão
 
Substituir `pySUS` pelo **`datasus-fetcher`** para download dos arquivos `.dbc`:
 
- Não requer compilação — compatível com Windows sem dependências nativas
- Download direto dos arquivos `.dbc` anuais por agravo e UF
- Script reproduzível criado em `src/download_sinan.py`
- Dados nacionais baixados e filtrados por `SG_UF_NOT == '51'` (código MT) no Python
Para portais com bloqueio 403, adicionar header `User-Agent: Mozilla/5.0`
nas requisições HTTP resolve o problema.
 
## Consequências
 
- Download do SINAN/Dengue 2018–2024 bem-sucedido (~624 MB)
- Pipeline de coleta reproduzível via script versionado
- Filtro por MT aplicado em Python durante limpeza — não no download
## Nota
 
Esta decisão foi posteriormente superada pela adoção do **InfoDengue API**
como fonte principal (ver ADR-004), que elimina a necessidade de processar
arquivos `.dbc` do DATASUS diretamente.
 
## Aprendizado registrado
 
- `datasus-fetcher` é a forma mais confiável de acessar dados do DATASUS
  via Python no Windows
- Arquivos `.dbc` são o formato nativo do DATASUS — requerem conversão
  para uso em pipelines Python (ver ADR-003)