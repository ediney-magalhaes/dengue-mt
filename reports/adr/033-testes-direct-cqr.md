# ADR-033: Testes Automatizados para Modelos Direct CQR

## Status
Implementado — 2026-05-20

## Contexto
Com 12 modelos Direct CQR em produção (ADR-030), o pipeline precisa de validação
automatizada que garanta integridade dos artefatos, invariantes matemáticas e
qualidade mínima das predições antes de qualquer promoção ou deploy.

Os testes existentes (10 em `test_pipeline.py`) cobrem apenas o Gold e o modelo
pontual v5. Os 12 modelos Direct, o metadata JSON e as bandas CQR não tinham
cobertura.

## Decisão
Criar `tests/test_direct_cqr.py` com 11 testes organizados em 5 categorias:

### Artefatos (3 testes)
- 12 arquivos `.pkl` existem em `models/`
- `direct_cqr_metadata.json` existe
- Metadata contém campos obrigatórios e `n_modelos == 12`

### Import e targets (3 testes)
- `treinar_direto_cqr` e `criar_targets_direct` importam sem erro
- `criar_targets_direct` gera 4 colunas `y_h{1,2,4,8}` com >100 valores válidos
- Targets estão em escala `log1p` (>= 0 e max < 1000) — ADR-024

### Predições e invariante expm1 (2 testes)
- Todos os 12 modelos geram predições >= 0 após `np.expm1()` — ADR-024
- Predições em escala log (sem expm1) têm média < 10; com expm1, média é maior

### Bandas CQR (1 teste)
- Para cada horizonte: lower (q05) <= mediana (q50) <= upper (q95)
- Tolerância ajustada para h=8 (15 casos, até 15% de violações) devido a
  quantile crossing — fenômeno documentado por Koenker (2005) onde regressão
  quantílica não-restrita permite cruzamento entre quantis em regiões de
  alta incerteza. A calibração conformal corrige isso em produção.

### Consistência e qualidade (2 testes)
- Todos os 12 modelos usam as mesmas features
- R² dos modelos q50 >= 0.30 (h=1,2,4) ou >= 0.20 (h=8) nas últimas 52 SE

## Consequências
- Suíte completa: 21 testes (10 pipeline + 11 Direct CQR)
- `_rodar_pytest()` no `retreino.py` bloqueia promoção se qualquer teste falhar
- CI/CD roda ambos os arquivos de teste automaticamente
- Quantile crossing em h=8 é tolerado nos testes mas corrigido em produção
  pela calibração conformal (q_conformal — ADR-031)

## Referências
- Koenker, R. (2005). *Quantile Regression*. Cambridge University Press.
- Romano, Y., Patterson, E., & Candès, E. (NeurIPS 2019). Conformalized Quantile Regression.