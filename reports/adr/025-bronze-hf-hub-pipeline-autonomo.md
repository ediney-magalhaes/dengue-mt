# ADR-025: Persistência e Restore do Bronze no HF Hub — Pipeline Autônomo

**Data:** 2026-04-30
**Status:** Aceito

---

## Problema identificado

O pipeline CI/CD nascia sem Bronze a cada execução — o GitHub Actions
usa ambiente efêmero (Ubuntu limpo). Consequências:

- Todas as ingestões rodavam do zero toda semana
- MODIS AppEEARS demorava 60+ min aguardando processamento NASA
- Pipeline semanal quebrava por timeout no CI
- Dependência implícita da máquina local do desenvolvedor para ter Bronze

A raiz do problema: `publicacao.py` publicava apenas o Gold no HF Hub.
Bronze nunca foi incluído na estratégia de persistência.

## Decisão

### 1. Bronze como cidadão de primeira classe no HF Hub

Publicar Bronze completo no HF Hub com a mesma rastreabilidade do Gold:
```
bronze/
infodengue/   → arquivos por ano por município
nasa_power/   → arquivos por ano por município
modis/        → modis_ndvi_evi_latest.parquet
oni/          → oni_index_latest.parquet
trends/       → trends_dengue_latest + historico
bronze_manifest_latest.json  → rastreabilidade por execução
```

### 2. Publicação incremental por SHA256

A cada execução semanal, `publicar_bronze_incremental()` compara
SHA256 local vs HF Hub — publica apenas arquivos modificados.
Respeita a cadência natural de cada fonte:

| Fonte | Cadência | Comportamento esperado |
|---|---|---|
| InfoDengue | Semanal | arquivo do ano corrente sempre atualizado |
| NASA POWER | Semanal | arquivo do ano corrente sempre atualizado |
| MODIS | Mensal | skip nas 3 semanas sem dado novo |
| ONI | Trimestral | skip na maioria das semanas |
| Trends | Semanal | latest sempre atualizado |

### 3. Manifesto de rastreabilidade

`bronze_manifest_latest.json` publicado a cada execução contendo:
- `snapshot_date` + `commit_sha` + `pipeline_version`
- Por arquivo: `sha256`, `size_bytes`, `status` (publicado/skipped/erro)

### 4. Script centralizado de restore

`scripts/restore_artifacts_hf.py` centraliza todo restore do HF Hub
via flags independentes:
```
--gold    → data/gold/dataset_features_latest.parquet
--modelo  → models/lgbm_producao_latest.pkl
--schema  → models/lgbm_feature_schema_latest.json
--bronze  → data/bronze/**/*.parquet (todos os arquivos)
```

Qualquer flag que falhar encerra com `exit(1)` — sem exceções.

### 5. CI/CD atualizado

```yaml
# Job testes:
python scripts/restore_artifacts_hf.py --gold --modelo

# Job pipeline_semanal:
python scripts/restore_artifacts_hf.py --gold --modelo --schema --bronze
```

Elimina código Python inline duplicado no `ci.yml`.

## Fluxo resultante
```
GitHub Actions (domingo)
→ Restore Bronze + Gold + modelo do HF Hub (segundos)
→ Ingestão: busca apenas dados NOVOS da semana
→ MODIS: Bronze existe e atualizado → skip AppEEARS
→ dbt run → Gold
→ publicar_bronze_incremental() → SHA256 → publica só modificados
→ publicar_gold_versionado() → snapshot datado + latest
→ Dashboard atualiza automaticamente
```

Pipeline completamente autônomo — sem dependência de máquina local.

## Alternativas consideradas

| Alternativa | Por que descartada |
|---|---|
| Pipeline mensal separado para MODIS | Quebra dependência Gold — dbt precisa do Bronze completo |
| Skip MODIS no CI via variável de ambiente | Trata sintoma, não a causa raiz |
| Comparação por tamanho de arquivo | Menos robusto — arquivo pode mudar sem alterar tamanho |
| Comparação por timestamp | Instável entre timezones e re-downloads |

## Consequências

- Pipeline CI/CD completamente autônomo — roda em qualquer ambiente
- MODIS timeout resolvido — Bronze restaurado do HF Hub em segundos
- `publicacao.py` — duas tasks separadas: Bronze e Gold
- `ci.yml` — código inline Python eliminado, substituído por script
- Bootstrap inicial executado em 30/04/2026: 40 arquivos Bronze publicados

## Referências

- ADR-014 (MODIS AppEEARS substitui GEE)
- ADR-011 (versionamento dataset snapshot)
- ADR-013 (artefatos commit SHA)
- ADR-023 (integração dbt pipeline Prefect)
