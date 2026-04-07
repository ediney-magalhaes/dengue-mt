-- stg_trends.sql
-- Bronze → Silver: Google Trends
-- Aplica lag obrigatório de 7 dias (anti-leakage)
-- Limitação: API retorna apenas últimos 90 dias
-- Período disponível: últimos 90 dias

with bronze as (
    select * from {{ source('bronze_trends', 'trends_latest') }}
),

padronizado as (
    select
        cast(data as date)              as data_se,
        cast(trends_dengue_raw as float) as trends_dengue,

        -- Lag obrigatório de 7 dias para evitar leakage
        -- Google Trends da semana atual não está disponível
        -- até o final da semana — aplicamos lag conservador
        cast(data as date) + interval '7 days' as data_se_lag,

        current_timestamp               as dbt_updated_at

    from bronze
    where data is not null
      and trends_dengue_raw is not null
      and cast(trends_dengue_raw as float) between 0 and 100
),

-- Usa data com lag como chave de join
finalizado as (
    select
        data_se_lag                     as data_se,
        trends_dengue,
        dbt_updated_at
    from padronizado
)

select * from finalizado