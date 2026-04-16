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
        {{ inicio_se('epoch_ms(data_iniSE)::date') }}   as data_se,
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
    select
        municipio_id,
        municipio_nome,
        data_se,
        -- Em caso de duplicata após normalização, mantém o maior valor de casos
        max(semana_epidemiologica)          as semana_epidemiologica,
        max(casos_confirmados)              as casos_confirmados,
        max(casos_estimados)                as casos_estimados,
        max(casos_confirmados_lab)          as casos_confirmados_lab,
        max(prob_rt_maior_1)                as prob_rt_maior_1,
        max(rt_index)                       as rt_index,
        max(nivel_alerta)                   as nivel_alerta,
        max(receptivo)                      as receptivo,
        max(transmissao)                    as transmissao,
        max(incidencia_100k)                as incidencia_100k,
        max(notificacoes_acumuladas_ano)    as notificacoes_acumuladas_ano,
        avg(temp_media)                     as temp_media,
        avg(temp_max)                       as temp_max,
        avg(temp_min)                       as temp_min,
        avg(umidade_media)                  as umidade_media,
        avg(umidade_max)                    as umidade_max,
        avg(umidade_min)                    as umidade_min,
        max(populacao)                      as populacao,
        max(dbt_updated_at)                 as dbt_updated_at
    from padronizado
    where
        municipio_id in ({{ var('municipios') | join(', ') }})
        and data_se >= {{ cast_date("'" ~ var('data_inicio') ~ "'") }}
        and data_se <= {{ cast_date("'" ~ var('data_fim') ~ "'") }}
        and casos_confirmados >= 0
    group by municipio_id, municipio_nome, data_se
)

select * from filtrado