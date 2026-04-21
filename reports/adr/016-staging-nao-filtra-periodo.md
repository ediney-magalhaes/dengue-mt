# ADR-016 — Staging Não Filtra por Período — Responsabilidade do Marts
 
**Status:** Aceito  
**Data:** 13/04/2026  
**Tema:** dbt / Arquitetura de Transformações
 
---
 
## Contexto
 
Durante a correção dos stagings, foi identificado que `stg_oni.sql` aplicava
um filtro de período diretamente na camada de staging:
 
```sql
WHERE data_inicio_trimestre >= '2018-01-01'
```
 
Esse filtro causou um bug sutil: o trimestre DJF (Dezembro-Janeiro-Fevereiro)
tem `data_inicio_trimestre = 2017-12-01`, mas seus dados cobrem
Janeiro e Fevereiro de 2018. O filtro descartava esse trimestre,
deixando as primeiras 4 semanas epidemiológicas de 2018 sem dados de ONI —
0% de cobertura nesse período, sem nenhum erro explícito.
 
## Decisão
 
**Princípio estabelecido:** staging padroniza e limpa — nunca filtra por período.
Filtro temporal é responsabilidade exclusiva do marts.
 
**Correções aplicadas:**
- Removido filtro `WHERE` de período do `stg_oni.sql`
- `generate_series` expandido para `2017-10-01` — cobre trimestres
  cujo início é anterior a 2018 mas cujos dados pertencem ao período do projeto
- Filtro de período `WHERE data_se >= '2018-01-07'` movido para
  `mart_dengue_features.sql`

**Por que esta separação é arquiteturalmente correta:**
 
| Camada | Responsabilidade |
|--------|-----------------|
| Staging | Padronizar tipos, limpar valores inválidos, renomear colunas |
| Intermediate | Joins entre fontes, granularidade semana epidemiológica |
| Marts | Filtro temporal, lags, features de ML, regras de negócio |
 
Staging com filtro temporal cria acoplamento entre a camada de limpeza
e a regra de negócio do projeto — qualquer mudança no período de análise
exigiria alterar o staging, que deveria ser estável.
 
## Consequências
 
- ONI com 100% de cobertura em todo o período 2018–2025
- Staging reutilizável para qualquer período futuro sem modificação
- Regra de período centralizada em um único lugar: `mart_dengue_features.sql`
- Princípio documentado e aplicável a todos os stagings futuros do projeto
## Aprendizado registrado
 
Filtros silenciosos em camadas intermediárias são especialmente perigosos
porque não geram erro — apenas produzem resultados incompletos.
A cobertura 0% do ONI nas primeiras semanas de 2018 só foi descoberta
ao inspecionar o intermediate — não havia nenhum teste dbt capturando isso.
 
**Ação preventiva:** testes dbt de cobertura mínima por fonte adicionados
ao intermediate para detectar situações similares no futuro.
 