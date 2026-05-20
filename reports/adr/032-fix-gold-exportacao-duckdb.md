# ADR-032: Fix Gold — Exportação DuckDB → Parquet antes de Publicar

## Status
Aceito — 2026-05-19

## Contexto
O Gold no HF Hub ficou parado em 2026-04-12 por 5 semanas, apesar
do pipeline semanal (CI/CD) rodar com sucesso todos os domingos e
enviar alertas "pipeline ok" via Telegram.

### Diagnóstico
O fluxo no CI/CD era:

1. `restore_artifacts_hf.py --gold` → restaura `data/gold/*.parquet` do HF Hub
2. Ingestão (5 fontes) → atualiza Bronze com dados novos
3. `dbt run` → atualiza tabela `main_marts.mart_dengue_features` no DuckDB
4. `publicar_gold_versionado()` → lê `data/gold/dataset_features_latest.parquet`
5. Publica no HF Hub

O problema: no passo 4, o parquet lido era o **restaurado no passo 1**
(dados antigos), não o gerado pelo dbt no passo 3. O dbt atualizava
o DuckDB corretamente, mas ninguém exportava a tabela do DuckDB para
o arquivo parquet no disco antes da publicação.

### Por que não foi detectado
- SHA256 do parquet restaurado = SHA256 do parquet no HF Hub (eram o mesmo arquivo)
- Todas as etapas retornavam `status: ok`
- O alerta Telegram reportava sucesso
- Nenhuma validação verificava se o Gold tinha avançado temporalmente

## Decisão
Adicionar exportação explícita do DuckDB → parquet dentro de
`publicar_gold_versionado()`, antes de publicar no HF Hub.

### Implementação
```python
# publicacao.py — dentro de publicar_gold_versionado()
import duckdb
conn = duckdb.connect(str(duckdb_path), read_only=True)
df_gold = conn.execute('SELECT * FROM main_marts.mart_dengue_features').df()
conn.close()
df_gold.to_parquet(gold_path, index=False)
```

O DuckDB é a fonte de verdade — o parquet é derivado dele.

## Consequências

### Positivas
- Gold no HF Hub avança a cada execução do pipeline
- Dashboard reflete dados atualizados
- Previsões usam as últimas semanas epidemiológicas disponíveis

### Negativas
- Dependência explícita do DuckDB no módulo de publicação
- Se o DuckDB não existir, fallback para parquet existente (mantém comportamento anterior)

### Lição aprendida
Falhas silenciosas violam o princípio "no silent failures" do projeto.
O pipeline deve validar que os dados publicados são mais recentes que
os anteriores — não apenas que a publicação foi bem-sucedida.

## Referências
- ADR-030 — Direct Multi-Step + CQR (contexto do pipeline)
- Princípio arquitetural: "no silent failures" (sessões 1-5 do projeto)