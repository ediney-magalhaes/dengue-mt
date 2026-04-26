# ADR-024: Transformação log1p/expm1 — Par Obrigatório no Target

**Data:** 2026-04-19 (decisão log1p) / 2026-04-26 (bug expm1 detectado e corrigido)

**Status:** Aceito

**Contexto:** Bug crítico de escala na inferência — modelo subestimava por fator 10x

---

## Problema identificado

O modelo LightGBM v5 foi treinado com `log1p(casos_confirmados)` como target
(ADR-020) para reduzir o impacto de surtos extremos (até 477 casos/semana em 2024).

Na sessão de 26/04/2026, ao rodar o pipeline end-to-end, o diagnóstico revelou:

| Métrica | Sem expm1 | Com expm1 |
|---|---|---|
| R² (todo dataset) | -0.230 | 0.995 (in-sample) |
| MAE | 23.9 | 1.3 |
| Predição média | 2.5 | 26.2 |
| Casos reais média | 26.4 | 26.4 |

O modelo previa `log1p(casos)` ≈ 2.5, que corresponde a `expm1(2.5)` ≈ 11 casos.
Sem a transformação inversa, o valor 2.5 era comparado diretamente com 26.4 casos reais,
gerando R² negativo em todos os anos e todos os períodos.

## Diagnóstico

O bug não gerava exceção — o modelo produzia predições numéricas válidas na escala
errada. Sem erro visível, o problema só foi detectado ao investigar por que o
R² era sistematicamente negativo.

### Módulos afetados

| Módulo | Antes (bug) | Depois (corrigido) |
|---|---|---|
| `src/tasks/drift.py:89` | `np.maximum(modelo.predict(X), 0)` | `np.maximum(np.expm1(modelo.predict(X)), 0)` |
| `tests/test_pipeline.py:101` | `np.maximum(modelo.predict(X), 0)` | `np.maximum(np.expm1(modelo.predict(X)), 0)` |
| `tests/test_pipeline.py:119` | `np.maximum(modelo.predict(X), 0)` | `np.maximum(np.expm1(modelo.predict(X)), 0)` |
| `src/tasks/retreino.py:187` | Já correto | — |

O `retreino.py` já aplicava `expm1` porque foi escrito na mesma sessão em que
a decisão do log1p foi tomada (19/04). Os outros módulos foram refatorados em
25/04 sem perceber que faltava a transformação inversa.

## Decisão

**Regra: toda predição de modelo treinado com log1p DEVE aplicar expm1 antes
de qualquer comparação com valores reais.**

Padrão canônico:

```python
# CORRETO — par completo
preds = np.maximum(np.expm1(modelo.predict(X)), 0)

# ERRADO — escala log, valores ~2-5 ao invés de ~10-150
preds = np.maximum(modelo.predict(X), 0)
```

## Aprendizado registrado

1. **Bug silencioso** — a ausência do expm1 não gera erro, apenas métricas ruins.
   Isso torna o bug difícil de detectar sem investigação ativa.

2. **Métricas enganosas** — R² negativo pode parecer "modelo ruim" quando na
   verdade é "escala errada". O diagnóstico correto exige comparar as duas escalas.

3. **In-sample vs out-of-sample** — o R²=0.995 do diagnóstico é in-sample
   (modelo prevendo dados de treino). A métrica oficial permanece o TimeSeriesSplit
   5-fold: R²=0.741 ± 0.081.

4. **Refatoração como vetor de bugs** — ao refatorar múltiplos módulos
   simultaneamente, é fácil esquecer detalhes específicos de cada um. O par
   log1p/expm1 deveria ter sido tratado como contrato, não como detalhe.

## Prevenção futura

O `build_features.py` centraliza a seleção de features e poderia centralizar
também a predição com transformação inversa. Candidato para refatoração futura:

```python
def predict_casos(modelo, X):
    """Predição com transformação inversa — ponto único."""
    return np.maximum(np.expm1(modelo.predict(X)), 0)
```

## Referências

- ADR-020: Transformação log1p no target
- Hastie, Tibshirani, Friedman (2009) — Elements of Statistical Learning, seção training error vs test error
- Hyndman & Athanasopoulos (2021) — Forecasting: Principles and Practice, avaliação temporal
- Chen et al. (2025) — Assessing dengue forecasting methods, Tropical Medicine and Health
- Sebastianelli et al. (2024) — A reproducible ensemble ML approach to forecast dengue outbreaks, Scientific Reports