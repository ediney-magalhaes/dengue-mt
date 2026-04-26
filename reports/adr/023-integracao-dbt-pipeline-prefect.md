# ADR-023: Integração dbt no Pipeline Prefect

**Data:** 2026-04-21 (decisão) / 2026-04-26 (validação end-to-end)

**Status:** Aceito

**Contexto:** Refatoração v2.0 — substituição do build_gold monolítico

---

## Problema identificado

O pipeline v1.x usava `src/tasks/build_gold.py` (monolítico) para construir o Gold dataset.
Problemas:
- Transformações misturadas com lógica de orquestração
- Sem testes declarativos — validação era manual ou via Pandera redundante
- Feature engineering acoplado ao pipeline — difícil de auditar
- Sem rastreabilidade de linhagem entre camadas

## Decisão

Substituir `build_gold.py` por `dbt run` + `dbt test` executados via `src/tasks/dbt_runner.py`.

### Arquitetura implementada
```
Prefect (orquestração)
└── ingestão (5 fontes → Bronze)
└── dbt_runner.py
├── dbt run  → staging (6 views) + intermediate (1 table) + marts (1 table)
└── dbt test → 59 testes declarativos
└── publicação (Gold → HF Hub)
└── drift monitoring
└── retreino condicional
```
### Fluxo de dados
```
Bronze (Parquet) → dbt staging (views) → dbt intermediate (table) → dbt marts (Gold table)
↓
DuckDB → export Parquet → HF Hub
```
### Validação

Pipeline end-to-end validado em 26/04/2026:
- dbt run: PASS=8 (6 views + 2 tables) em 1.17s
- dbt test: PASS=59 em 2.11s
- pytest: 10/10 PASS
- Drift: MAE=1.82, R²=0.866, nível=normal
- Gold publicado no HF Hub com snapshot datado + latest
- Alerta Telegram recebido
- MLflow run registrado

### Encerramento antecipado

Se `dbt run` ou `dbt test` falhar, o pipeline aborta antes de publicar
ou avaliar drift — não propaga dados inválidos.

## Alternativas consideradas

| Alternativa | Por que descartada |
|---|---|
| Manter `build_gold.py` | Monolítico, sem testes declarativos, sem linhagem |
| Pandera para validação | Redundante com dbt test — mesmas validações em camada anterior |
| dbt Cloud | Custo — violaria premissa de R$ 0,00 |
| Great Expectations | Overhead de configuração vs dbt test nativo |

## Consequências

- `build_gold.py` removido — responsabilidade migrou para dbt
- `validacao.py` movido para archive — substituído por 59 testes dbt + 2 customizados
- `feature_engineering.py` movido para archive — lags calculados no SQL do intermediate
- Pipeline mais rápido: ~24s total (ingestão 15s + dbt 10s)
- Linhagem auditável: Bronze → staging → intermediate → marts

## Referências

- dbt-core documentation: https://docs.getdbt.com
- DuckDB + dbt-duckdb: https://github.com/duckdb/dbt-duckdb
- ADR-004 (fontes de dados) — define o que entra no Bronze
- ADR-016 (staging não filtra período) — regra aplicada nos modelos staging