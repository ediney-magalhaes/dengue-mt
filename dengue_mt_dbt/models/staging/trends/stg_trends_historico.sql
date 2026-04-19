-- stg_trends_historico.sql
-- Bronze → Silver: Google Trends histórico 2018→2025
-- Série reconstruída via overlapping windows com normalização
-- Referência: Scientific Data (Nature) 2026
-- Lag obrigatório de 7 dias aplicado (anti-leakage)

with bronze as (
    select * from {{ source('bronze_trends', 'trends_historico') }}
),

padronizado as (
    select
        -- Lag obrigatório de 7 dias — garante domingo (início SE)
        {{ inicio_se(cast_date('data') ~ " + interval '7 days'") }} as data_se,

        cast(trends_dengue_historico as float)  as trends_dengue_historico,

        current_timestamp                       as dbt_updated_at

    from bronze
    where data is not null
      and trends_dengue_historico is not null
      and cast(trends_dengue_historico as float) between 0 and 100
),

finalizado as (
    select distinct
        data_se,
        avg(trends_dengue_historico)    as trends_dengue_historico,
        current_timestamp               as dbt_updated_at
    from padronizado
    where data_se >= {{ cast_date("'" ~ var('data_inicio') ~ "'") }}
      and data_se <= {{ cast_date("'" ~ var('data_fim') ~ "'") }}
    group by data_se
)

select * from finalizado