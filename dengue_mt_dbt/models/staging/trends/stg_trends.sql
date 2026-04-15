-- stg_trends.sql
-- Bronze → Silver: Google Trends
-- Aplica lag obrigatório de 7 dias (anti-leakage)
-- Limitação: API retorna apenas últimos 90 dias

with bronze as (
    select * from {{ source('bronze_trends', 'trends_latest') }}
),

padronizado as (
    select
        cast(data as date)                                         as data_se,
        cast(trends_dengue_raw as float)                           as trends_dengue,

        -- Lag obrigatório de 7 dias — garante domingo (início SE)
        {{ inicio_se("cast(data as date) + interval '7 days'") }} as data_se_lag,

        current_timestamp                                          as dbt_updated_at

    from bronze
    where data is not null
      and trends_dengue_raw is not null
      and cast(trends_dengue_raw as float) between 0 and 100
),

finalizado as (
    select
        data_se_lag                    as data_se,
        avg(trends_dengue)             as trends_dengue,
        current_timestamp              as dbt_updated_at
    from padronizado
    group by data_se_lag
)
select * from finalizado