# ADR-028: Backtesting com Expanding Window e Estratégia Recursiva

## Status
Aceito

## Data
2026-05-11

## Contexto

O modelo LightGBM v5 foi validado com TimeSeriesSplit 5-fold (R²=0.741 ± 0.081, MAE=9.7),
mas essa métrica não simula o cenário real de produção onde o modelo é retreinado
periodicamente e prevê semanas futuras. Para o artigo SENIC 2026, é obrigatório demonstrar
performance em backtesting retrospectivo com comparação contra baselines, conforme padrão
da literatura (Reich et al. 2019, Araujo et al. PNAS 2026).

Decisões necessárias:
1. Estratégia de janela: expanding vs rolling
2. Estratégia de previsão multi-horizonte: recursiva vs direta
3. Período de teste e baselines de comparação

## Decisão

### Expanding Window
Janela de treino cresce a cada passo (2018→t), prevendo t+h.
Escolhida sobre rolling window porque maximiza dados de treino em cada passo,
importante dado o tamanho limitado da série (856 registros).

### Estratégia Recursiva como padrão de produção
Avaliadas duas estratégias:
- **Recursiva**: 1 modelo treinado para h=1, reutilizado para h=2,3,4
- **Direta**: 4 modelos independentes, cada um otimizado para seu horizonte

Resultado: recursiva superou direta em MAE para todos os horizontes (h=1: 14.1 vs 14.6,
h=4: 17.9 vs 19.4). A vantagem da recursiva se explica pelo forte componente autoregressivo
dos dados (casos_lag1 r=0.93) — o modelo único captura melhor a dinâmica temporal.

### Período de teste: 2023→2026
Treino inicial: 2018-2022 (5 anos, ~260 semanas por município).
Teste: 2023-2026 (~170 semanas), cobrindo período endêmico (2023), surto histórico (2024)
e período recente (2025-2026). Justificativa: mínimo 2 ciclos epidêmicos completos
(Reich et al. 2019).

### Baselines
- Naïve: previsão = último valor observado
- Média Móvel 4 SE: previsão = média das últimas 4 semanas

### Métricas oficiais
- MAE (casos/semana) — interpretabilidade
- RMSE — penaliza erros em picos
- MASE — escalonado pelo baseline naïve (< 1 = melhor que naïve)
- R² — comparabilidade com cross-validation

## Resultados

| Horizonte | MAE Recursivo | MAE Naïve | MASE | R² |
|---|---|---|---|---|
| h=1 | 14.1 | 14.3 | 0.99 | 0.74 |
| h=2 | 15.7 | 19.9 | 0.79 | 0.65 |
| h=3 | 17.1 | 24.8 | 0.69 | 0.59 |
| h=4 | 17.9 | 30.3 | 0.59 | 0.54 |

Degradação MAE h=1→h=4: 27% (< 50%, considerado bom).
Limitação identificada: subestima picos epidêmicos (log1p comprime extremos).

## Referências
- Reich et al. (2019) — FluSight: expanding window + baselines para forecasting epidemiológico
- Araujo et al. (PNAS 2026) — IMDC24 Dengue Forecasting Sprint: avaliação multi-modelo Brasil
- Hyndman & Koehler (2006) — MASE como métrica escalada para séries temporais

## Consequências
- Pipeline de produção mantém estratégia recursiva com 1 modelo
- Métricas de backtesting reportadas no artigo SENIC junto com cross-validation
- Intervalos de confiança (sessão 12) endereçarão a subestimação de picos