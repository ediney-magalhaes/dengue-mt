# ADR-020 — Transformação log1p no Target
 
**Status:** Aceito  
**Data:** 19/04/2026  
**Tema:** Modelagem / Pré-processamento
 
---
 
## Contexto
 
A distribuição de casos semanais de dengue em Cuiabá e Várzea Grande é
fortemente assimétrica à direita — a maioria das semanas tem poucos casos
(cauda esquerda densa), com surtos ocasionais de magnitude extrema
(cauda direita longa). O surto de 2024/2025 atingiu picos de centenas de
casos por semana em municípios que tipicamente registram dezenas.
 
Treinar o modelo diretamente sobre casos brutos faz com que os surtos
extremos dominem a função de perda — o modelo aprende a prever os
picos às custas de errar sistematicamente nas semanas de baixa incidência,
que representam a maioria do período de operação.
 
## Decisão
 
Aplicar transformação **log1p** no target antes do treinamento:
 
```python
y_train = np.log1p(casos_confirmados)
# Predição revertida para escala original:
y_pred = np.expm1(model.predict(X))
```
 
**Por que log1p em vez de log:**
- `log1p(x) = log(1 + x)` — trata corretamente semanas com zero casos
  (frequentes em Várzea Grande) sem gerar `-inf`

**Efeito da transformação:**
  na função de perda
- Preserva a ordem relativa dos valores — modelo ainda distingue
  semanas de alta e baixa incidência
- MAE calculado na escala transformada — reportado na escala original
  via `expm1` para interpretabilidade

## Consequências
 
- Ganho de R² e MAE observado após aplicação, especialmente em
  Várzea Grande onde a esparsidade e os surtos extremos eram mais impactantes
- Previsões em produção sempre revertidas via `expm1` antes de exibir
  no dashboard — usuário vê casos reais, não valores transformados
- Transformação documentada no feature schema para garantir consistência
  entre treino e serving

## Limitação conhecida
 
A transformação log1p suaviza os picos — o modelo tende a subestimar
a magnitude dos surtos mais extremos. Para alertas de saúde pública,
subestimar um surto é mais perigoso que superestimá-lo. Reportar
esta característica na seção de limitações do artigo.
 
## Referências
 
- Hyndman & Athanasopoulos (2021) — transformações de Box-Cox e log
  para séries com heterocedasticidade
- James et al. (2021, ISLR) — tratamento de targets assimétricos
  em modelos supervisionados
 