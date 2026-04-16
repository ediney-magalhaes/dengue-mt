-- stg_modis.sql
-- Bronze → Silver: MODIS MOD13A3
-- NDVI e EVI mensais 1km via AppEEARS NASA
-- Expande mensal → Semana Epidemiológica (repetição do valor mensal)
-- Período: 2018→atual | Municípios: Cuiabá + Várzea Grande

with bronze as (
    select * from {{ source('bronze_modis', 'modis_latest') }}
),

validado as (
    select
        -- Identificação
        cast(geocode as integer)                                as municipio_id,
        municipio                                               as municipio_nome,

        -- Data mensal
        {{ cast_date('Date') }}                                 as data_mes,

        -- NDVI e EVI — escala MODIS: dividir por 10000
        case
            when "MOD13A3_061__1_km_monthly_NDVI" = -3000 then null
            else round(cast("MOD13A3_061__1_km_monthly_NDVI" as float) / 10000.0, 4)
        end                                                     as ndvi,

        case
            when "MOD13A3_061__1_km_monthly_EVI" = -3000 then null
            else round(cast("MOD13A3_061__1_km_monthly_EVI" as float) / 10000.0, 4)
        end                                                     as evi,

        -- Qualidade do pixel (0=bom, 1=marginal, 2=neve/gelo, 3=nuvem)
        cast("MOD13A3_061__1_km_monthly_pixel_reliability" as integer) as pixel_reliability

    from bronze
    where "MOD13A3_061__1_km_monthly_NDVI" is not null
      and {{ cast_date('Date') }} >= {{ cast_date("'2018-01-01'") }}
),

-- Gera todas as SE do período
semanas as (
    select distinct
        unnest(
            generate_series(
                cast('2018-01-07' as date),
                {{ cast_date("'" ~ var('data_fim') ~ "'") }},
                interval '7 days'
            )
        )::date as data_se
),

-- Municípios disponíveis
municipios as (
    select distinct municipio_id, municipio_nome
    from validado
),

-- Cross join SE × municípios
semanas_municipios as (
    select s.data_se, m.municipio_id, m.municipio_nome
    from semanas s
    cross join municipios m
),

-- Expande mensal → semanal
expandido as (
    select
        sm.data_se,
        sm.municipio_id,
        sm.municipio_nome,
        g.ndvi,
        g.evi,
        g.pixel_reliability,
        case
            when g.pixel_reliability > 1 then true
            else false
        end                         as flag_qualidade_ruim,
        current_timestamp           as dbt_updated_at
    from semanas_municipios sm
    left join validado g
        on date_trunc('month', sm.data_se) = date_trunc('month', g.data_mes)
        and sm.municipio_id = g.municipio_id
)

select * from expandido