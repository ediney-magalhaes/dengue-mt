# ADR-029: Intervalos de Predição via Conformalized Quantile Regression

## Status
Aceito — 2026-05-13

## Contexto
O LightGBM v5 produz previsões pontuais, mas gestores de saúde pública
precisam de informação sobre a incerteza associada às previsões para
tomada de decisão (ex: dimensionar leitos, planejar ações de campo).

Modelos de ML baseados em árvores não possuem distribuição paramétrica
associada — diferentemente de modelos clássicos (ARIMA, GLM) que derivam
intervalos analiticamente a partir de pressupostos distribucionais.

Três abordagens foram avaliadas:

| Abordagem | Garantia teórica | Adaptativo | Dependências |
|---|---|---|---|
| Quantile Regression nativa | Não | Sim | Nenhuma |
| Bootstrap dos resíduos | Não | Não | Nenhuma |
| **CQR (Romano et al., 2019)** | **Sim** | **Sim** | mapie 1.4.0 |

## Decisão
Adotar **Conformalized Quantile Regression (CQR)** para quantificação
de incerteza, implementado com LightGBM quantílico + calibração conformal.

### Justificativa
1. **Garantia teórica de cobertura** — distribution-free, sem pressupostos
   de normalidade ou homocedasticidade (Romano et al., NeurIPS 2019)
2. **Adaptatividade** — intervalos largos nos picos epidêmicos e estreitos
   na entressafra, capturando a heteroscedasticidade dos dados de dengue
3. **Precedente na literatura** — conformal prediction já aplicado em
   previsão de dengue no Brasil (PMC 2025, medRxiv)
4. **Compatível com LightGBM** — usa objective='quantile' nativo
5. **Custo zero** — mapie é open-source (BSD-3)

### Resultados empíricos (período de avaliação: 2023-2026)

| Método | Cobertura | Largura média |
|---|---|---|
| CQR 90% | 91.5% ✅ | 129.0 |
| QR bruto 90% | 58.9% ❌ | 70.6 |
| Fixo 90% | 71.3% ❌ | 88.2 |
| CQR 80% | 69.8% ⚠️ | 63.7 |
| QR bruto 80% | 45.7% ❌ | 47.1 |
| Fixo 80% | 59.7% ❌ | 48.7 |

CQR 90% é o único método que atinge a cobertura nominal.
CQR 80% ficou abaixo do nominal — conjunto de calibração (43 semanas)
insuficiente para intervalos mais estreitos.

### Configuração
- Calibração: 25% do período de teste (43 semanas)
- Quantis: [0.05, 0.95] para 90%, [0.10, 0.90] para 80%
- Nonconformity score: max(lower - y, y - upper)
- Ajuste conformal: q=32.14 (90%), q=8.30 (80%)

## Consequências

### Positivas
- Dashboard pode exibir bandas de incerteza na aba Previsão
- Gestores de saúde recebem range de cenários, não apenas ponto
- Artigo SENIC ganha seção de uncertainty quantification com referência
  estado-da-arte

### Negativas
- Treinar 3 modelos quantílicos por previsão (3x custo computacional)
- Dependência nova: mapie 1.4.0

### Pendências de integração
- [ ] Aba Previsão do dashboard: exibir bandas CQR 90%
- [ ] Pipeline de produção: treinar modelos quantílicos junto com pontual
- [ ] Avaliar CQR 80% com conjunto de calibração maior (>60 semanas)

## Perspectivas futuras (alternativas para evolução)

Abordagens que permitiriam modelagem probabilística completa,
substituindo a necessidade de CQR:

1. **NGBoost / GBMLSS** — Distributional Gradient Boosting que otimiza
   todos os parâmetros de uma distribuição (μ, σ) simultaneamente.
   Mantém flexibilidade das árvores + distribuição condicional completa.
   Referência: Duan et al. (ICML 2020), März et al. (2022).

2. **Binomial Negativa via GLM/GAM** — Distribuição padrão para dados
   de contagem com sobredispersão (como dengue). Intervalos analíticos
   derivados da própria distribuição. Referência: Hilbe (2011).

3. **Modelos bayesianos hierárquicos (INLA/Stan)** — Distribuição
   posterior completa com intervalos de credibilidade. Permite
   incorporar estrutura espacial e temporal. Referência: bandas
   epidemiológicas probabilísticas para dengue (PMC 2025, INLA).

## Referências
- Romano, Y., Patterson, E., Candès, E. (2019). Conformalized Quantile
  Regression. NeurIPS 32.
- Cordier, T. et al. (2023). Flexible and systematic uncertainty
  estimation with conformal prediction via the MAPIE library. COPA/PMLR.
- Lundberg, S., Lee, S. (2017). A unified approach to interpreting
  model predictions. NeurIPS 30.
- Rahman et al. (2025). Dengue Early Warning System Using Interpretable
  Tree-Based ML Model. Health Science Reports.

## Artefatos
- `notebooks/backtesting/02_intervalos_confianca.py`
- `notebooks/backtesting/config_intervalos.py`
- `reports/intervalos/metricas_intervalos.csv`
- `reports/intervalos/*.png` (6 figuras)
- `notebooks/backtesting/03_shap_analysis.py`
- `reports/shap/*.png` (4 figuras)
- `reports/shap/shap_values.csv`