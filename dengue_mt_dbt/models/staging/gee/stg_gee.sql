-- stg_gee.sql
-- Bronze → Silver: Google Earth Engine (NDVI, NDWI)
-- Expande granularidade mensal → semanal
-- Cada SE recebe o valor do mês correspondente (repetição)
-- Período: 2018→2024 (sem dados 2025 ainda)

with bronze as (
    select * from {{ source('bronze_gee', 'gee_blend') }}
),

validado as (
    select
        cast(data as date)          as data_mes,
        cast(ndvi_final as float)   as ndvi,
        cast(ndwi_final as float)   as ndwi,
        cast(fonte as varchar)      as fonte_imagem,
        cast(n_s2 as integer)       as n_imagens_sentinel2,
        cast(n_modis as integer)    as n_imagens_modis

    from bronze
    where ndvi_final is not null
      and ndwi_final is not null
      -- Faixas válidas NDVI/NDWI: -1 a +1
      and cast(ndvi_final as float) between -1 and 1
      and cast(ndwi_final as float) between -1 and 1
      and cast(data as date) >= cast('{{ var("data_inicio") }}' as date)
),

-- Gera todas as SE do período
semanas as (
    select
        unnest(
            generate_series(
                cast('{{ var("data_inicio") }}' as date)
                    + cast((7 - dayofweek(cast('{{ var("data_inicio") }}' as date))) % 7 as integer),
                cast('{{ var("data_fim") }}' as date),
                interval '7 days'
            )
        )::date as data_se
),


-- Expande mensal → semanal
-- Cada SE recebe o valor do mês em que cai
expandido as (
    select
        s.data_se,
        g.ndvi,
        g.ndwi,
        g.fonte_imagem,
        g.n_imagens_sentinel2,
        g.n_imagens_modis,
        case
            when g.ndvi is null then true
            else false
        end                     as flag_sem_dados_gee,
        current_timestamp       as dbt_updated_at

    from semanas s
    left join validado g
        on date_trunc('month', s.data_se) = date_trunc('month', g.data_mes)
)

select * from expandido