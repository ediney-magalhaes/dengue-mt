-- Teste customizado: features críticas devem ter < 5% de nulos
-- Falha se qualquer feature crítica exceder 5% de nulos
with contagem as (
    select
        count(*) as total,
        count(*) - count(casos_confirmados) as nulos_casos,
        count(*) - count(temp_media_lag1) as nulos_temp,
        count(*) - count(precip_lag1) as nulos_precip,
        count(*) - count(casos_lag1) as nulos_casos_lag
    from {{ ref('mart_dengue_features') }}
)
select *
from contagem
where nulos_casos   * 100.0 / total > 5
   or nulos_temp    * 100.0 / total > 5
   or nulos_precip  * 100.0 / total > 5
   or nulos_casos_lag * 100.0 / total > 5