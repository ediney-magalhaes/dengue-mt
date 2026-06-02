# ADR-034: Análise SHAP para Modelos Direct CQR

## Status
Implementado — 2026-06-01

## Contexto
Com 12 modelos Direct CQR em produção (ADR-030), o pipeline gera previsões
com intervalos de incerteza mas sem explicabilidade — não é possível saber
quais variáveis mais influenciam cada previsão nem como essa influência muda
entre horizontes e municípios.

O SHAP existente no projeto (`03_shap_analysis.py` + `reports/shap/`) foi
calculado para o modelo pontual LightGBM v5 (single-step) e está obsoleto.
Não cobre os 4 horizontes Direct nem a separação por município.

A aba de explicabilidade no dashboard estava ausente — o dashboard exibia
previsões mas não fornecia ao gestor de saúde nem ao revisor acadêmico
nenhuma justificativa para os valores gerados.

## Decisão

### 1. Método — TreeSHAP (Lundberg et al., Nature MI 2020)
TreeSHAP é o único método exato e eficiente para modelos baseados em árvores.
Calcula valores SHAP em tempo polinomial percorrendo as árvores de decisão do
LightGBM — viável para o dataset (856 registros × 46 features) em segundos.
SHAP genérico (amostragem de coalições) seria impraticável para 46 features
(2⁴⁶ combinações possíveis).

### 2. Somente quantil q50 (mediana)
Os modelos q05 e q95 definem os limites do intervalo de incerteza — sua
interpretação via SHAP é tecnicamente válida mas epidemiologicamente menos
relevante: o que importa explicar é a previsão central, não os extremos.
Calcular SHAP para os 3 quantis triplicaria o tempo de execução e a
quantidade de artefatos sem ganho proporcional para o artigo ou o dashboard.
Decisão revisável após o CBIS'26 se houver demanda de revisores.

### 3. Script offline — não integrado ao pipeline semanal
O SHAP é computacionalmente significativo e semanticamente estável: enquanto
os modelos não mudam, os valores SHAP não mudam. Integrar ao pipeline semanal
geraria custo de processamento sem ganho de informação nas semanas sem retreino
(maioria dos runs, conforme evidenciado pelos runs de 24/05 e 31/05 com
`retreino: nao_executado`).

Ciclo de atualização definido:
- Pipeline reporta `Retreino: executado` → operador roda manualmente:
  `python notebooks/backtesting/04_shap_direct_cqr.py`
- Figuras atualizadas em `reports/shap/direct_cqr/` e `app/assets/shap/`
- Commit e push para refletir no dashboard

### 4. Análise por município
Cuiabá (5103403) e Várzea Grande (5108402) têm populações, densidades e
perfis epidemiológicos distintos. Gerar SHAP separado por município permite
identificar se as features dominantes diferem entre os dois — informação
relevante tanto para o gestor de saúde quanto para o artigo. O custo
computacional adicional é mínimo (filtro de máscara sobre shap_values já
calculados).

### 5. PNG estático — não Plotly interativo
As figuras SHAP são geradas offline pelo script e servidas como assets
estáticos no dashboard via `st.image()`. Plotly interativo exigiria recalcular
os SHAP values em tempo real no Streamlit — inviável sem GPU e incompatível
com o Streamlit Community Cloud gratuito. PNG estático com troca dinâmica
por horizonte/município via sidebar é o equilíbrio correto entre
interatividade e custo zero.

## Artefatos gerados
```
notebooks/backtesting/04_shap_direct_cqr.py   ← script de análise
reports/shap/direct_cqr/
├── global/
│   ├── fig01_h{1,2,4,8}_beeswarm.png         ← ranking + direção do efeito
│   ├── fig02_h{1,2,4,8}_bar_top20.png        ← top 20 por |SHAP| médio
│   ├── fig03_h{1,2,4,8}_dependence.png       ← relações não-lineares
│   ├── fig04_h{1,2,4,8}_temporal.png         ← importância por fase epidêmica
│   └── fig05_comparativo_horizontes.png      ← mudança de estratégia h=1→h=8
├── municipios/
│   ├── fig01_h{1,2,4,8}_cuiaba_beeswarm.png
│   ├── fig01_h{1,2,4,8}_varzea_grande_beeswarm.png
│   ├── fig02_h{1,2,4,8}_cuiaba_bar_top20.png
│   └── fig02_h{1,2,4,8}_varzea_grande_bar_top20.png
└── dados/
├── shap_importance_h{1,2,4,8}.csv
├── shap_importance_h{1,2,4,8}_cuiaba.csv
├── shap_importance_h{1,2,4,8}_varzea_grande.csv
└── shap_importance_consolidado.csv        ← 184 linhas, todos horizontes
app/assets/shap/                              ← cópia para o dashboard
app/components/aba_shap.py                    ← aba Explicabilidade

```
## Resultado principal

Padrão de mudança de estratégia por horizonte (gold dataset 2018–2026):

| Horizonte | Feature dominante    | \|SHAP\| | Interpretação             |
|-----------|----------------------|----------|---------------------------|
| h=1 SE    | casos_mm4            | 0.6923   | Modelo reativo            |
| h=2 SE    | casos_mm4            | 0.6681   | Momentum ainda domina     |
| h=4 SE    | casos_mm4            | 0.4129   | Transição estrutural      |
| h=8 SE    | notif_acum_ano_lag1  | 0.3885   | Modelo prospectivo        |

Transição de momentum autoregressivo (h=1,2) para sazonalidade histórica
e precipitação acumulada (h=8) é consistente com o ciclo biológico do
Aedes aegypti (~2-3 semanas) e com a literatura de previsão multi-step
(Taieb & Hyndman, 2014).

## Consequências
- Dashboard v2.5.0 passa a ter 6 abas — nova aba "🔍 Explicabilidade"
- Figuras respondem ao sidebar (horizonte + município) via troca de PNG
- Artefatos SHAP versionados no repositório junto com os modelos
- Revisores do CBIS'26 têm acesso à explicabilidade completa do modelo
- Atualização manual necessária após cada retreino — sem automação por ora

## Referências
- Lundberg, S. M., & Lee, S. I. (NeurIPS 2017). A Unified Approach to
  Interpreting Model Predictions.
- Lundberg, S. M., et al. (Nature Machine Intelligence, 2020). From local
  explanations to global understanding with explainable AI for trees.
- Taieb, S. B., & Hyndman, R. J. (2014). A gradient boosting approach to
  the Kaplan-Meier estimator. *Statistics and Computing*.
- Rahman, M. et al. (Health Science Reports, 2025). Explainable machine
  learning for dengue fever prediction.
- Molnar, C. (2023). *Interpretable Machine Learning* (cap. 8-9).
  https://christophm.github.io/interpretable-ml-book/