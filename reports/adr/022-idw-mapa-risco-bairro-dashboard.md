# ADR-022 — IDW Dinâmico para Mapa de Risco por Bairro — Acoplado ao Modelo
 
**Status:** Aceito — implementado em 30/04/2026 (ver ADR-027)

**Data:** 20/04/2026

**Tema:** Dashboard / Visualização Espacial / Produto
 
---
 
## Contexto
 
O dashboard é o **produto principal do projeto** — uma ferramenta proativa
de apoio à decisão para gestores de saúde e agentes de endemias.
Seu propósito não é exibir comportamento histórico, mas **antecipar surtos
com granularidade geográfica acionável**.
 
O dashboard original exibia pontos estáticos por UBS com score baseado
em carga histórica — sem atualização, sem previsão, sem utilidade operacional
real para tomada de decisão semanal.
 
O modelo LightGBM v5 gera previsões municipais atualizadas semanalmente.
O desafio é **distribuir essa previsão espacialmente pelos bairros** de forma
que o mapa reflita sempre a previsão mais recente — inclusive após retreinos
disparados por drift.
 
## Decisão
 
Adotar **IDW (Inverse Distance Weighting) dinâmico** como camada de
distribuição espacial da previsão municipal para os bairros:
 
### Arquitetura do fluxo semanal
 
```
Pipeline semanal (GitHub Actions)
        │
        ▼
LightGBM v5
  → previsão: N casos em Cuiabá    SE+1, SE+2, SE+3, SE+4
  → previsão: M casos em Várzea Grande SE+1, SE+2, SE+3, SE+4
        │
        ▼
IDW distribuidor espacial
  → pesos históricos por UBS (calibrados com SINAN, revisados anualmente)
  → distribuição proporcional da previsão municipal pelos bairros
        │
        ▼
GeoJSON de saída: 143 bairros × 4 horizontes de previsão
  bairro_i → casos_se1, casos_se2, casos_se3, casos_se4
        │
        ▼
Dashboard Streamlit
  → mapa Choropleth por bairro, atualizado semanalmente
  → slider de horizonte (SE+1 a SE+4)
  → cores refletem previsão, não histórico
```
 
### Fórmula IDW
 
```
casos_bairro_i = previsao_municipal × (peso_UBS_i / Σ peso_UBS_j)
 
onde:
  peso_UBS_i = notificacoes_historicas_UBS_i / distancia_centroide_bairro_UBS_i²
```
 
O peso de cada UBS combina dois fatores:
 
- **Peso histórico:** UBS com mais notificações históricas recebem maior
  proporção da previsão — reflete capacidade notificadora e cobertura real
  da área de abrangência

- **Peso espacial (IDW):** UBS mais próximas do centroide do bairro têm
  maior influência — reflete proximidade geográfica

### Calibração dos pesos
 
Os pesos por UBS são **calibrados uma vez com o SINAN histórico** e
revisados anualmente — não mudam semanalmente. O que muda toda semana
é a **magnitude da previsão municipal** vinda do LightGBM.
 
Comportamento quando o modelo é retreinado por drift:
- Nova previsão municipal gerada automaticamente pelo pipeline
- IDW redistribui a nova previsão com os mesmos pesos calibrados
- Dashboard reflete o novo estado **sem nenhuma intervenção manual**

### Camadas de dados necessárias
 
| Dado | Fonte | Frequência de atualização |
|------|-------|--------------------------|
| Previsão municipal SE+1 a SE+4 | LightGBM v5 | Semanal — automático |
| Pesos IDW por UBS | SINAN histórico + CNES | Anual |
| Shapefile bairros | IBGE CD2022 | Estático |
| Coordenadas UBS | CNES | Estático |
 
### Implementação planejada
 
```
scripts/calibrar_pesos_idw.py        ← calibração anual dos pesos por UBS
scripts/gerar_previsao_bairros.py    ← aplica IDW à previsão municipal (semanal)
data/external/
  pesos_idw_ubs_cuiaba_vg.json       ← pesos calibrados por UBS
  previsao_bairros_latest.geojson    ← output semanal para o dashboard
app/components/aba_mapa.py           ← Choropleth Folium com slider SE+1→SE+4
```
 
### O que NÃO muda no pipeline de treino
 
- Bronze, Staging, Intermediate e Marts — inalterados
- Modelo LightGBM v5 — inalterado (granularidade municipal)
- IDW é camada de pós-processamento exclusiva da camada de serving/dashboard

## Separação de escopos — Produto vs Artigo
 
| Escopo | Granularidade | Método | Atualização | Onde aparece |
|--------|--------------|--------|-------------|--------------|
| **Artigo SENIC** | Municipal | LightGBM v5 + TimeSeriesSplit | — | Paper |
| **Dashboard (produto)** | Bairro | Previsão municipal × IDW | Semanal automático | Deploy |
 
O artigo documenta e avalia o modelo preditivo municipal.
O dashboard distribui a previsão municipal espacialmente para uso operacional.
 
## Consequências
 
- Mapa sempre reflete a previsão mais recente — produto proativo, não retroativo
- Retreino por drift propaga automaticamente para o mapa sem intervenção manual
- 143 bairros com score de risco prospectivo para 4 horizontes (SE+1 a SE+4)
- Gestores e agentes de endemias priorizam bairros com antecedência real de
  1 a 4 semanas

## Comunicação ao usuário no dashboard
 
O mapa deve exibir claramente:
 
> *"Previsão de casos para as próximas 4 semanas distribuída por bairro.
> Modelo LightGBM v5 atualizado automaticamente toda semana.
> Distribuição espacial via IDW com base no histórico de notificações por UBS."*
 
Isso garante transparência metodológica sem comprometer a usabilidade do produto.
 
## Referências
 
- Cromley & McLafferty (2011) — *GIS and Public Health*: IDW para
  análise espacial em saúde pública
- Shepard (1968) — método IDW original
- Ministério da Saúde (2020) — análise espacial de cobertura da APS
 