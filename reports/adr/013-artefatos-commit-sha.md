# ADR-013 — Artefatos Amarrados ao Commit SHA via GITHUB_SHA
 
**Status:** Aceito  
**Data:** 27/03/2026  
**Tema:** MLOps / Rastreabilidade
 
---
 
## Contexto
 
Modelos e datasets gerados pelo pipeline não tinham vínculo formal com o
código que os produziu. Era impossível responder: "qual versão do código
gerou esse modelo?" — requisito básico de auditoria em MLOps e de
reprodutibilidade científica.
 
## Decisão
 
Capturar o SHA do commit atual via variável de ambiente `GITHUB_SHA`
e registrá-lo em todos os artefatos gerados:
 
```python
commit_sha = os.environ.get('GITHUB_SHA', 'local')[:8]
```
 
**Comportamento por ambiente:**
- Execução no GitHub Actions CI: retorna os 8 primeiros caracteres do SHA real
- Execução local: retorna a string `'local'` — rastreabilidade parcial,
  sem quebrar o pipeline

**Onde o SHA é registrado:**
- `models/lgbm_v5_feature_schema.json` — vincula modelo ao commit
- `metadata/run_metadata.json` — vincula execução ao commit
- Log estruturado de cada run — visível no `reports/pipeline.log`
- Snapshots do dataset no HF Hub (via metadata JSON — ver ADR-011)

## Consequências
 
- Dado qualquer modelo em produção, é possível fazer `git checkout <sha>`
  e reproduzir exatamente o código que o gerou
- Auditoria completa: modelo → schema → commit → código → dataset
- Execuções locais são identificadas como `local` — não confundidas
  com runs do CI

## Alternativas consideradas
 
- Hash do arquivo do modelo (MD5) — complementar, não substituto;
  vincula ao conteúdo do modelo mas não ao código que o gerou
- Tag git manual por versão — descartado por ser processo manual
  sujeito a esquecimento; SHA automático é mais confiável
 