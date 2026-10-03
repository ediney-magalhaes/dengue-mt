# ADR-036: Correção de Permissão no Restore do HF Hub e Conexão do Fallback de Cache

## Status
Implementado — 2026-10-03

## Contexto
O pipeline semanal falhou em duas fontes (`ingest_oni`, `ingest_google_trends`)
no dia 20/09/2026, com `Permission denied` ao tentar sobrescrever os arquivos
Bronze `*_latest.parquet`. A causa raiz estava em `scripts/restore_artifacts_hf.py`:
a função `restore_arquivo()` usava `shutil.copy()` para copiar arquivos do cache
do `huggingface_hub` (`hf_hub_download()`) para `data/bronze/`.

No Linux (GitHub Actions `ubuntu-latest`), o `huggingface_hub` armazena blobs em
cache como somente-leitura via symlink, para proteger a deduplicação entre
revisões. `shutil.copy()` preserva o modo de permissão do arquivo de origem,
diferente de `shutil.copyfile()`, que copia apenas o conteúdo. O resultado era
um arquivo somente-leitura em `data/bronze/`, que as tasks de ingestão não
conseguiam sobrescrever na execução seguinte.

O bug não é reproduzível no Windows: sem suporte nativo a symlinks (fora de
Developer Mode ou execução como administrador), o `huggingface_hub` usa um modo
de cache degradado que não aplica a mesma restrição, o que tornou o diagnóstico
mais difícil, já que testes locais não reproduziam o erro.

Adicionalmente, investigação revelou que o módulo de fallback por cache
(`src/tasks/cache.py` — `salvar_cache()`/`carregar_cache()`) já existia no
projeto, mas nunca havia sido conectado às tasks de ingestão. Uma falha de API
(NOAA ou Google Trends) resultava em `status: erro` sem qualquer tentativa de
usar o último dado válido, o alerta Telegram confirmava `Fallback: não` mesmo
havendo infraestrutura pronta para isso.

## Decisão

### 1. Correção da causa raiz — permissão no restore
`restore_arquivo()` em `scripts/restore_artifacts_hf.py` passou a usar
`shutil.copyfile()` em vez de `shutil.copy()`, com `chmod(0o644)` explícito
logo após a cópia:

```python
shutil.copyfile(downloaded, path_local)
path_local.chmod(0o644)
```

O `chmod` explícito é defensivo, blinda contra qualquer mudança futura no
comportamento interno de cache do `huggingface_hub`, em vez de depender
implicitamente do método de cópia escolhido.

### 2. Conexão do fallback de cache nas tasks de ingestão
`ingerir_oni_index()` e `ingerir_google_trends()`, em `src/tasks/ingestao.py`,
passaram a chamar `salvar_cache()` após ingestão bem-sucedida e `carregar_cache()`
no bloco `except`, retornando os dados em cache (com `fallback: True`) em vez de
falhar sem alternativa quando a API de origem está indisponível.

### Comportamento de degradação
- Ingestão OK → dado novo salvo no cache, `fallback: False`
- Ingestão falha + cache válido → dado em cache retornado, `status: ok`,
  `fallback: True`, alerta Telegram informativo (🟡)
- Ingestão falha + sem cache → `status: erro`, `fallback: False`,
  alerta Telegram crítico (🔴)

## Consequências
- O pipeline agora degrada graciosamente diante de falha de uma fonte externa
  (NOAA ONI, Google Trends), usando o último dado válido em vez de propagar
  o erro sem alternativa
- Risco de dado defasado é aceito conscientemente: ONI tem cadência mensal
  (baixo risco de staleness), Google Trends é semanal (merece acompanhamento
  se o fallback for acionado com frequência)
- `restore_artifacts_hf.py` corrigido de forma sistêmica — a mesma função é
  usada pelas 4 flags (`--gold`, `--modelo`, `--schema`, `--bronze`), então a
  correção protege todos os artefatos restaurados do HF Hub, não só Bronze
- Bug não reproduzível em ambiente de desenvolvimento local (Windows), reforça
  a necessidade de validar mudanças de infraestrutura no ambiente real de
  execução (GitHub Actions `ubuntu-latest`), não apenas localmente

## Referências
- Hugging Face Hub docs — Manage your cache (symlinks e blobs somente-leitura): https://huggingface.co/docs/huggingface_hub/en/guides/manage-cache
- Python docs — `shutil.copy` vs `shutil.copyfile` (preservação de permissões): https://docs.python.org/3/library/shutil.html