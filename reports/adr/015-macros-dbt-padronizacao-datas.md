# ADR-015 — Macros dbt para Padronização de Tipos de Data entre Fontes
 
**Status:** Aceito  
**Data:** 13/04/2026  
**Tema:** dbt / Qualidade de Dados
 
---
 
## Contexto
 
Os joins entre stagings no modelo intermediate (`int_dengue_mt`) produziam
0% de cobertura — as semanas epidemiológicas não se conectavam entre fontes.
A causa raiz foi identificada: cada fonte representava datas de forma diferente,
gerando tipos incompatíveis que impediam o match silenciosamente.
 
**Inconsistências identificadas:**
 
| Fonte | Representação original | Tipo |
|-------|----------------------|------|
| InfoDengue | `data_iniSE` — timestamp em milissegundos | BIGINT |
| NASA POWER | `YYYYMMDD` como inteiro | INTEGER |
| ONI Index | `YYYY-MM-DD` string | VARCHAR |
| MODIS | `YYYY-MM-DD` string | VARCHAR |
| Google Trends | `YYYY-MM-DD` string | VARCHAR |
 
Adicionalmente, a InfoDengue retornou 1 registro com data irregular
`2018-04-04` (quarta-feira) em vez de domingo — causando NULL no join
com as demais fontes que usam domingo como âncora da semana epidemiológica.
 
## Decisão
 
Criar macros dbt em `dengue_mt_dbt/macros/cast_date.sql` para padronização
centralizada:
 
| Macro | Uso | Justificativa |
|-------|-----|---------------|
| `cast_date(column)` | Converte qualquer campo para `DATE` | Padronização geral |
| `cast_epoch_ms(column)` | Timestamp ms → `DATE` | InfoDengue retorna BIGINT |
| `inicio_se(column)` | Calcula o domingo da SE de qualquer data | Portaria SVS/MS nº 5/2010 |
| `primeiro_domingo(date_str)` | Primeiro domingo após uma data | `generate_series` a partir de domingo |
 
**Correção defensiva no stg_infodengue:**
 
```sql
{{ inicio_se('epoch_ms(data_iniSE)::date') }}
```
 
Normaliza qualquer data para o domingo da SE correspondente — corrige
a data irregular `2018-04-04` e protege contra futuras irregularidades
da API sem intervenção manual. `GROUP BY` adicionado para resolver
a duplicata gerada pela normalização.
 
**Princípio estabelecido:** toda data no pipeline passa por uma macro
antes de participar de qualquer join — nunca comparação direta entre
representações brutas de fontes distintas.
 
## Consequências
 
- Joins entre todas as fontes funcionando corretamente
- Cobertura do intermediate passou de 0% para 100% nas 4 fontes principais
- Correção automática e defensiva de datas irregulares da InfoDengue
- Macros reutilizáveis em qualquer model dbt futuro do projeto
## Referências
 
- Portaria SVS/MS nº 5/2010 — define domingo como início da semana
  epidemiológica no Brasil
 