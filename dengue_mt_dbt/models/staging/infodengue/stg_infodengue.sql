-- stg_infodengue.sql
-- Bronze → Silver: InfoDengue
-- Padroniza nomes, tipos, valida municipios e remove colunas desnecessárias
-- Período: 2018→2025 | Municípios: Cuiabá (5103403) + Várzea Grande (5108402)

with cuiaba as (
    select * from {{ source('bronze_infodengue', 'cuiaba') }}
),

varzea_grande as (
    select * from {{ source('bronze_infodengue', 'varzea_grande') }}
),

unificado as (
    select * from cuiaba
    union all
    select * from varzea_grande
),

padronizado as (
    select
        -- Identificação
        cast(geocode as integer)                        as municipio_id,
        municipio                                       as municipio_nome,

        -- Data — Bronze usa data_iniSE
        {{ cast_epoch_ms('data_iniSE') }}               as data_se,
        cast(SE as integer)                             as semana_epidemiologica,

        -- Casos
        cast(casos as integer)                          as casos_confirmados,
        cast(casos_est as float)                        as casos_estimados,
        cast(casconf as float)                          as casos_confirmados_lab,

        -- Nowcasting e alertas
        cast(p_rt1 as float)                            as prob_rt_maior_1,
        cast(Rt as float)                               as rt_index,
        cast(nivel as integer)                          as nivel_alerta,
        cast(receptivo as integer)                      as receptivo,
        cast(transmissao as integer)                    as transmissao,
        cast(p_inc100k as float)                        as incidencia_100k,
        cast(notif_accum_year as integer)               as notificacoes_acumuladas_ano,

        -- Clima (ERA5 via Mosqlimate)
        cast(tempmed as float)                          as temp_media,
        cast(tempmax as float)                          as temp_max,
        cast(tempmin as float)                          as temp_min,
        cast(umidmed as float)                          as umidade_media,
        cast(umidmax as float)                          as umidade_max,
        cast(umidmin as float)                          as umidade_min,

        -- População
        cast(pop as integer)                            as populacao,

        -- Metadados
        current_timestamp                               as dbt_updated_at

    from unificado
),

filtrado as (
    select *
    from padronizado
    where
        -- Apenas municípios definidos
        municipio_id in ({{ var('municipios') | join(', ') }})
        -- Período definido nas decisões: 2018→2025
        and data_se >= cast('{{ var("data_inicio") }}' as date)
        and data_se <= cast('{{ var("data_fim") }}' as date)
        -- Sem casos negativos
        and casos_confirmados >= 0
)

select * from filtrado