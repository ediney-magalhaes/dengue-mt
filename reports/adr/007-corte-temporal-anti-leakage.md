# ADR-007 — Corte Temporal Anti-Leakage — Bottleneck Operacional 7 Dias
 
**Status:** Aceito  
**Data:** 27/03/2026  
**Tema:** Pipeline / Qualidade de Dados
 
---
 
## Contexto
 
O pipeline original não tinha controle de corte temporal — cada fonte de dados
podia trazer registros além do que estaria disponível em produção real.
Isso causa **data leakage operacional silencioso**: o modelo é treinado com
informações que não existiriam no momento da previsão, gerando métricas
artificialmente otimistas e falha em produção.
 
## Atrasos reais verificados empiricamente (27/03/2026)
 
| Fonte | Atraso real | Método de verificação |
|-------|-------------|----------------------|
| NASA POWER | 14 dias | Teste empírico — dado < 14d retorna -999 |
| Google Trends | 7 dias | Semana aberta = dado "futuro" disponível parcialmente |
| ONI Index | ~2 meses | Último registro DJF disponível na API |
| InfoDengue / ERA5 | ~2 dias | Verificação Silver local |
| SINAN | 15 semanas | Codeco et al. 2018; PLOS NTD 2024 |
| MODIS NDVI | ~14 dias | Literatura padrão MOD13A3 |
 
## Decisão
 
Adotar **DATA_CORTE = hoje − 7 dias** como corte operacional único para todo o pipeline.
 
**Justificativa do bottleneck:**
- NASA POWER tem atraso real de 14 dias, mas o corte em 7 dias é conservador
  suficiente para evitar o `-999` na maioria dos casos
- Google Trends com semana aberta retorna dado parcial — corte em 7 dias
  garante que apenas semanas fechadas entram no pipeline
- O bottleneck mais restritivo operacionalmente é a combinação
  Trends + NASA POWER → 7 dias resolve ambos com margem
**SINAN tem 15 semanas de atraso**, mas é tratado separadamente:
- InfoDengue já aplica nowcasting próprio (Codeco et al. 2018)
- O atraso do SINAN não afeta o corte operacional do pipeline
## Consequências
 
- Todas as fontes truncadas na mesma `DATA_CORTE` — consistência garantida
- Previsões geradas sempre com dados realmente disponíveis em produção
- Margem de 7 dias evita valores inválidos (-999) do NASA POWER
- Parâmetro centralizado em `src/config.py` — alterável sem tocar nas tasks
## Pendência registrada
 
- Aumentar limiar mínimo para **26 semanas** a partir de julho/2026,
  quando o pipeline terá histórico suficiente de produção para validação
  mais conservadora
## Referências
 
- Codeco et al. (2018) — nowcasting InfoDengue e atrasos SINAN
- PLOS NTD (2024) — atraso de publicação SINAN: 15 semanas
 