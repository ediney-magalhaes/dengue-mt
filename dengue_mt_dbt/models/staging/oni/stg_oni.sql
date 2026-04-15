-- stg_oni.sql
-- Bronze → Silver: ONI Index NOAA
-- Converte seas+yr para data, valida faixas
-- Agrega trimestral → Semana Epidemiológica (repetição do valor trimestral)
-- Período: 2018→2025

with bronze as (
    select * from {{ source('bronze_oni', 'oni_latest') }}
),

-- Mapeamento de trimestres NOAA para mês inicial
-- DJF=Dez-Jan-Fev → mês 12 ano anterior
-- JFM=Jan-Fev-Mar → mês 1
-- FMA=Fev-Mar-Abr → mês 2 ... etc
com_data as (
    select
        cast(yr as integer)     as ano,
        cast(total as float)    as temp_superficie_mar,
        cast(anom as float)     as oni_index,
        seas                    as trimestre_noaa,

        -- Converte trimestre NOAA para data do primeiro mês
        case seas
            when 'DJF' then make_date(cast(yr as integer) - 1, 12, 1)
            when 'JFM' then make_date(cast(yr as integer), 1, 1)
            when 'FMA' then make_date(cast(yr as integer), 2, 1)
            when 'MAM' then make_date(cast(yr as integer), 3, 1)
            when 'AMJ' then make_date(cast(yr as integer), 4, 1)
            when 'MJJ' then make_date(cast(yr as integer), 5, 1)
            when 'JJA' then make_date(cast(yr as integer), 6, 1)
            when 'JAS' then make_date(cast(yr as integer), 7, 1)
            when 'ASO' then make_date(cast(yr as integer), 8, 1)
            when 'SON' then make_date(cast(yr as integer), 9, 1)
            when 'OND' then make_date(cast(yr as integer), 10, 1)
            when 'NDJ' then make_date(cast(yr as integer), 11, 1)
        end                     as data_inicio_trimestre,

        -- Fase ENSO baseada no índice ONI
        -- Padrão NOAA: >= 0.5 = El Niño, <= -0.5 = La Niña
        case
            when cast(anom as float) >= 1.5  then 'el_nino_forte'
            when cast(anom as float) >= 0.5  then 'el_nino'
            when cast(anom as float) <= -1.5 then 'la_nina_forte'
            when cast(anom as float) <= -0.5 then 'la_nina'
            else 'neutro'
        end                     as fase_enso,

        -- Numérico para uso como feature no modelo
        case
            when cast(anom as float) >= 1.5  then 2
            when cast(anom as float) >= 0.5  then 1
            when cast(anom as float) <= -1.5 then -2
            when cast(anom as float) <= -0.5 then -1
            else 0
        end                     as fase_enso_num

    from bronze
    where yr is not null
      and seas is not null
      and anom is not null
),

validado as (
    select *
    from com_data
    where
        data_inicio_trimestre is not null
        and data_inicio_trimestre >= cast('{{ var("data_inicio") }}' as date)
        and data_inicio_trimestre <= cast('{{ var("data_fim") }}' as date)

        -- Faixa válida para ONI (-4 a +4)
        and oni_index between -4 and 4
),

-- Expande trimestral → semanal
-- Cada SE recebe o valor ONI do trimestre correspondente
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

expandido as (
    select
        s.data_se,
        o.oni_index,
        o.fase_enso,
        o.fase_enso_num,
        o.temp_superficie_mar,
        o.trimestre_noaa,
        current_timestamp as dbt_updated_at
    from semanas s
    -- depois
    left join validado o
        on extract('month' from s.data_se)
           = extract('month' from o.data_inicio_trimestre + interval '1 month')
        and extract('year' from s.data_se)
           = extract('year' from o.data_inicio_trimestre + interval '1 month')
)

select * from expandido