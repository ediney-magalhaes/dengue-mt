# ADR-026: data_fim Dinâmico no dbt — Eliminação de Hardcode Temporal

**Data:** 2026-04-30

**Status:** Aceito

---

## Problema identificado

O `dbt_project.yml` tinha `data_fim: "2025-12-31"` hardcoded.
O mart `mart_dengue_features` filtrava registros com:

```sql
data_se <= {{ cast_date("'" ~ var('data_fim') ~ "'") }}
```

Consequência: mesmo com Bronze de 2026 ingerido corretamente,
o Gold era truncado em 31/12/2025. Dados de janeiro a abril de 2026
existiam no Bronze mas nunca chegavam ao Gold — invisíveis para o modelo
e para o dashboard.

Isso violava a premissa fundamental do projeto:
> "Ano final deve ser sempre dinâmico - sem codificação fixa ano_fim=2025
> é um antipadrão explícito no projeto"

## Decisão

### 1. Default seguro no dbt_project.yml

```yaml
data_fim: "2099-12-31"
```

Garante que se o var não for passado via CLI, nenhum dado é cortado.

### 2. dbt_runner.py passa data_fim dinamicamente

```python
from datetime import datetime
data_fim_atual = datetime.now().strftime('%Y-%m-%d')
resultado = _executar_dbt([
    'dbt', 'run',
    '--vars', f'{{"data_fim": "{data_fim_atual}"}}'
], logger)
```

A cada execução semanal, o dbt recebe a data atual como `data_fim`.
Gold sempre cobre do início (2018-01-01) até o dia da execução.

## Impacto verificado

Antes da correção:
- Gold: 416 semanas × 2 municípios = 832 registros (até 2025-12-28)

Após a correção (30/04/2026):
- Gold: 428 semanas × 2 municípios = 856 registros (até 2026-04-12)
- 12 semanas de 2026 recuperadas — janeiro a abril

## Alternativas consideradas

| Alternativa | Por que descartada |
|---|---|
| Atualizar manualmente todo ano | Antipadrão explícito — erro humano garantido |
| Macro dbt para data atual | dbt não executa Python — macros são SQL/Jinja |
| Variável de ambiente no dbt_project.yml | dbt não lê env vars nativamente sem plugin |

## Consequências

- `dbt_project.yml` — `data_fim` nunca mais precisa ser atualizado
- `dbt_runner.py` — passa `--vars` com data atual em toda execução
- Gold sempre atual — previsões do modelo refletem dados recentes
- Pipeline CI/CD beneficiado automaticamente — sem intervenção manual

## Referências

- Premissas do projeto: "End year must always be dynamic"
- ADR-008 (dbt-duckdb medallion)
- ADR-023 (integração dbt pipeline Prefect)