# ADR-009 — Modularização do Pipeline Prefect (726 linhas → módulos)
 
**Status:** Aceito  
**Data:** 27/03/2026  
**Tema:** Pipeline / Arquitetura de Código
 
---
 
## Contexto
 
O arquivo `pipeline_prefect.py` atingiu 726 linhas combinando orquestração,
ingestão, transformação, validação, retreino e publicação em um único módulo.
Esse antipadrão ("God Object") tornava o código impossível de testar
unitariamente, difícil de ler e arriscado de modificar — qualquer alteração
podia quebrar partes não relacionadas.
 
## Decisão
 
Separar `pipeline_prefect.py` em módulos com responsabilidade única:
 
```
src/
├── pipeline_prefect.py     ← flow principal ~130 linhas (só orquestra)
├── config.py               ← constantes e paths centralizados
├── observabilidade.py      ← logger estruturado independente do Prefect
└── tasks/
    ├── ingestao.py         ← InfoDengue, NASA POWER, ONI, Trends
    ├── validacao.py        ← contratos Pandera
    ├── drift.py            ← monitoramento de drift
    ├── retreino.py         ← retreino + promoção/rollback
    ├── cache.py            ← cache local com fallback
    ├── publicacao.py       ← HF Hub versionado
    └── alertas.py          ← notificações JSONL
```
 
**Princípios aplicados:**
- `pipeline_prefect.py` apenas orquestra — não implementa nenhuma lógica
- `config.py` centraliza todas as constantes — elimina valores hardcoded
- `observabilidade.py` independente do Prefect — logs funcionam mesmo
  fora do contexto de um flow
- Cada task em `tasks/` tem responsabilidade única e testável isoladamente

**Benefícios observados:**
- Logs estruturados funcionando: duração por etapa, % nulos, métricas
- `reports/pipeline.log` gravado a cada execução
- Testes unitários por módulo viáveis sem mockar o flow inteiro

## Consequências
 
- Pipeline principal legível em ~130 linhas
- Cada módulo pode ser testado, importado e evoluído independentemente
- `config.py` como fonte única de verdade para paths e parâmetros
- Impacto no artigo: cada módulo corresponde a uma subseção da metodologia

## Alternativas consideradas
 
- Refatorar em classes (OOP) — descartado por adicionar complexidade
  desnecessária; funções puras são suficientes e mais testáveis
- Manter monolito com melhor documentação interna — descartado por não
  resolver o problema de testabilidade e manutenção
 