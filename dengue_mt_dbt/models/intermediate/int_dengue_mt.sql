-- int_dengue_mt.sql
-- Intermediate: join entre todas as fontes staging
-- Granularidade: (municipio_id, data_se)
-- Período: 2018→2025

with infodengue as (
    select * from {{ ref('stg_infodengue') }}
),

nasa as (
    select * from {{ ref('stg_nasa_power') }}
),

oni as (
    select * from {{ ref('stg_oni') }}
),

trends as (
    select * from {{ ref('stg_trends') }}
),

modis as (
    select * from {{ ref('stg_modis') }}
),

-- Join principal: InfoDengue como âncora (casos + clima ERA5)
-- NASA POWER: clima completo com precipitação
-- ONI: índice climático global
-- Trends: interesse público
-- GEE: vegetação e água
joined as (
    select
        -- Identificação
        i.municipio_id,
        i.municipio_nome,
        i.data_se,
        i.semana_epidemiologica,

        -- Target
        i.casos_confirmados,
        i.casos_estimados,
        i.prob_rt_maior_1,
        i.rt_index,
        i.nivel_alerta,
        i.receptivo,
        i.transmissao,
        i.incidencia_100k,
        i.notificacoes_acumuladas_ano,
        i.populacao,

        -- Clima InfoDengue (ERA5)
        i.temp_media,
        i.temp_max,
        i.temp_min,
        i.umidade_media,
        i.umidade_max,
        i.umidade_min,

        -- Clima NASA POWER (precipitação + radiação)
        n.temp_media_nasa,
        n.temp_max_nasa,
        n.temp_min_nasa,
        n.umidade_nasa,
        n.radiacao_mj,
        n.precipitacao_total_nasa,
        n.flag_se_incompleta                as nasa_flag_se_incompleta,

        -- ONI Index
        o.oni_index,
        o.fase_enso,
        o.fase_enso_num,

        -- Google Trends
        t.trends_dengue,

        -- Modis
        m.ndvi,
        m.evi,
        m.pixel_reliability                 as modis_pixel_reliability,
        m.flag_qualidade_ruim               as modis_flag_qualidade_ruim

    from infodengue i
    left join nasa n
        on i.municipio_id = n.municipio_id
        and i.data_se = n.data_se
    left join oni o
        on i.data_se = o.data_se
    left join trends t
        on i.data_se = t.data_se
    left join modis m
        on i.data_se = m.data_se
        and i.municipio_id = m.municipio_id
)

select * from joined