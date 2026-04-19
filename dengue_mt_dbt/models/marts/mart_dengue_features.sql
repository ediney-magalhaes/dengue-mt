-- mart_dengue_features.sql
-- Gold final para ML — dataset de features para LightGBM v5
-- Período: 2018→2025 | Municípios: Cuiabá + Várzea Grande
-- Inclui lags epidemiológicos conforme literatura
-- Hii et al. 2012: temperatura lag 2-4 SE, precipitação lag 1-3 SE
-- Codeco et al. 2018: nowcasting InfoDengue

with base as (
    select * from {{ ref('int_dengue_mt') }}
),

-- Calcula lags e médias móveis por município
features as (
    select
        -- Identificação
        municipio_id,
        municipio_nome,
        data_se,
        semana_epidemiologica,

        -- TARGET
        casos_confirmados,
        casos_estimados,
        incidencia_100k,

        -- Indicadores epidemiológicos (sem lag — são observados na SE)
        lag(rt_index, 1) over w           as rt_index_lag1,
        lag(nivel_alerta, 1) over w       as nivel_alerta_lag1,
        lag(receptivo, 1) over w          as receptivo_lag1,
        lag(transmissao, 1) over w        as transmissao_lag1,
        lag(prob_rt_maior_1, 1) over w    as prob_rt_maior_1_lag1,
        lag(notificacoes_acumuladas_ano, 1) over w as notif_acum_ano_lag1,
        populacao,

        -- Clima InfoDengue ERA5 — lags 1-4 SE
        lag(temp_media, 1) over w             as temp_media_lag1,
        lag(temp_media, 2) over w             as temp_media_lag2,
        lag(temp_media, 3) over w             as temp_media_lag3,
        lag(temp_media, 4) over w             as temp_media_lag4,
        lag(temp_max, 1) over w               as temp_max_lag1,
        lag(temp_max, 2) over w               as temp_max_lag2,
        lag(temp_min, 1) over w               as temp_min_lag1,
        lag(temp_min, 2) over w               as temp_min_lag2,
        lag(umidade_media, 1) over w          as umidade_lag1,
        lag(umidade_media, 2) over w          as umidade_lag2,

        -- NASA POWER — precipitação lags 1-4 SE
        lag(precipitacao_total_nasa, 1) over w as precip_lag1,
        lag(precipitacao_total_nasa, 2) over w as precip_lag2,
        lag(precipitacao_total_nasa, 3) over w as precip_lag3,
        lag(precipitacao_total_nasa, 4) over w as precip_lag4,

        -- NASA POWER — radiação e umidade lags 1-2 SE
        lag(radiacao_mj, 1) over w            as radiacao_lag1,
        lag(radiacao_mj, 2) over w            as radiacao_lag2,
        lag(umidade_nasa, 1) over w           as umidade_nasa_lag1,
        lag(umidade_nasa, 2) over w           as umidade_nasa_lag2,

        -- Médias móveis temperatura (4 e 8 SE)
        avg(temp_media) over (
            partition by municipio_id
            order by data_se
            rows between 3 preceding and current row
        )                                     as temp_media_mm4,
        avg(temp_media) over (
            partition by municipio_id
            order by data_se
            rows between 7 preceding and current row
        )                                     as temp_media_mm8,

        -- Médias móveis precipitação (4 e 8 SE)
        sum(precipitacao_total_nasa) over (
            partition by municipio_id
            order by data_se
            rows between 3 preceding and current row
        )                                     as precip_acum4,
        sum(precipitacao_total_nasa) over (
            partition by municipio_id
            order by data_se
            rows between 7 preceding and current row
        )                                     as precip_acum8,

        -- ONI/ENSO — lags 4-8 SE (ciclo climático lento)
        lag(oni_index, 4) over w              as oni_lag4,
        lag(oni_index, 6) over w              as oni_lag6,
        lag(oni_index, 8) over w              as oni_lag8,
        lag(fase_enso_num, 4) over w          as fase_enso_num_lag4,
        lag(fase_enso_num, 6) over w          as fase_enso_num_lag6,

        -- MODIS NDVI/EVI — lags 2-4 SE
        lag(ndvi, 2) over w                   as ndvi_lag2,
        lag(ndvi, 3) over w                   as ndvi_lag3,
        lag(ndvi, 4) over w                   as ndvi_lag4,
        lag(evi, 2) over w                    as evi_lag2,
        lag(evi, 3) over w                    as evi_lag3,

        -- Google Trends — lags 1-2 SE (já tem lag 7d do staging)
        lag(trends_dengue, 1) over w          as trends_lag1,
        lag(trends_dengue, 2) over w          as trends_lag2,

        -- Casos anteriores (autoregressive features)
        lag(casos_confirmados, 1) over w      as casos_lag1,
        lag(casos_confirmados, 2) over w      as casos_lag2,
        lag(casos_confirmados, 3) over w      as casos_lag3,
        lag(casos_confirmados, 4) over w      as casos_lag4,

        -- Média móvel casos (4 SE)
        avg(casos_confirmados) over (
            partition by municipio_id
            order by data_se
            rows between 3 preceding and current row
        )                                     as casos_mm4,

        -- Metadados
        current_timestamp                     as dbt_updated_at

    from base
    window w as (
        partition by municipio_id
        order by data_se
        rows between unbounded preceding and current row
    )
),

-- Filtro final de período e qualidade
filtrado as (
    select *
    from features
    where
        data_se >= {{ cast_date("'" ~ var('data_inicio') ~ "'") }}
        and data_se <= {{ cast_date("'" ~ var('data_fim') ~ "'") }}
        -- Garante target disponível
        and casos_confirmados is not null
        -- Remove primeiras SEs sem histórico suficiente para lags
        and casos_lag4 is not null
)

select * from filtrado