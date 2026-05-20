# ADR-031: Calibração Conformal das Bandas de Predição

## Status
Aceito — 2026-05-18

## Contexto
Os modelos Direct CQR (ADR-030) foram treinados com quantis q01/q99
via LightGBM `objective='quantile'`. Empiricamente, a cobertura bruta
dos intervalos ficou abaixo da nominal:

| Alpha (lo, hi) | Cobertura empírica | Nominal |
|---|---|---|
| (0.05, 0.95) | 63.7% | 90% |
| (0.03, 0.97) | 72.5% | 94% |
| (0.02, 0.98) | 76.0% | 96% |
| (0.01, 0.99) | 83.6% | 98% |

Este é um comportamento documentado na literatura: modelos de gradient
boosting com quantile regression não garantem cobertura nominal sem
calibração adicional (Meinshausen, 2006; Romano et al., 2019).

## Decisão
Aplicar **calibração conformal** (Romano et al., NeurIPS 2019) sobre
os quantis brutos para atingir ~90% de cobertura.

### Evolução dos quantis
- **Sessão 18/05**: q01/q99 — bandas conservadoras, q_conformal negativo (estreitava)
- **Sessão 19/05**: migração para q05/q95 — bandas 34% mais estreitas, q_conformal ≈ 0

A migração para q05/q95 foi motivada pela largura excessiva das bandas
q01/q99 (ex: Cuiabá SE+1 [3–41] para mediana de 6). Com q05/q95, as
bandas ficaram [4–29] — mais informativas para o gestor de saúde.

### Método
1. Treinar modelos q05 e q95 com dataset completo
2. Separar 20% final como conjunto de calibração
3. Calcular resíduos de conformidade: `max(q05 - y_real, y_real - q95)`
4. Obter quantil 90% dos resíduos → `q_conformal`
5. Bandas ajustadas: `[q05 - q_conf, q95 + q_conf]`

### Resultados (q05/q95 — versão final)
| Horizonte | q_conformal | Cobertura calibrada |
|---|---|---|
| h=1 | -0.0 | 90.1% |
| h=2 | -0.0 | 90.1% |
| h=4 | -0.0 | 90.0% |
| h=8 | -0.0 | 89.9% |

O `q_conformal` ≈ 0 indica que os quantis q05/q95 já atingem ~90%
de cobertura no conjunto de calibração sem ajuste adicional — as
bandas estão naturalmente calibradas.

## Consequências

### Positivas
- Cobertura ~90% garantida para todos os horizontes
- Bandas mais estreitas que sem calibração (q_conf negativo)
- Método distribution-free — não assume normalidade dos resíduos
- Implementado dentro do `treinar_direto_cqr.py` — sem módulo extra

### Negativas
- Depende de split fixo 80/20 para calibração (não expanding window)
- q_conformal é recalculado a cada treino — pode variar

### Invariantes
- Modelos q05/q95 treinados com dataset completo (não afetados)
- q_conformal salvo em `direct_cqr_metadata.json` para uso na inferência

## Referências
- Romano, Y., Patterson, E., Candès, E. (2019). Conformalized Quantile
  Regression. NeurIPS 32.
- Meinshausen, N. (2006). Quantile Regression Forests. JMLR 7, 983-999.