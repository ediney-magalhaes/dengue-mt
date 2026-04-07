-- stg_nasa_power.sql
-- Bronze → Silver: NASA POWER
-- Converte data_str para date, substitui -999 por NULL,
-- valida faixas de valores, agrega diário → Semana Epidemiológica
-- Período: 2018→2025

with bronze as (
    select * from {{ source('bronze_nasa_power', 'historico') }}
),

convertido as (
    select
        -- Converte data string YYYYMMDD → date
        strptime(cast(data_str as varchar), '%Y%m%d')::date   as data,

        -- Substitui -999 (valor inválido NASA) por NULL
        case when radiacao_raw = -999 then null
             else cast(radiacao_raw as float) end              as radiacao_mj,

        case when temp_media_raw = -999 then null
             else cast(temp_media_raw as float) end            as temp_media_nasa,

        case when temp_max_raw = -999 then null
             else cast(temp_max_raw as float) end              as temp_max_nasa,

        case when temp_min_raw = -999 then null
             else cast(temp_min_raw as float) end              as temp_min_nasa,

        case when precipitacao_raw = -999 then null
             else cast(precipitacao_raw as float) end          as precipitacao_nasa,

        case when umidade_raw = -999 then null
             else cast(umidade_raw as float) end               as umidade_nasa

    from bronze
    where data_str is not null
),

validado as (
    select *
    from convertido
    where
        data >= cast('{{ var("data_inicio") }}' as date)
        and data <= cast('{{ var("data_fim") }}' as date)
        -- Valida faixas climaticas
        and (temp_media_nasa is null or temp_media_nasa between -10 and 55)
        and (precipitacao_nasa is null or precipitacao_nasa >= 0)
        and (umidade_nasa is null or umidade_nasa between 0 and 100)
        and (radiacao_mj is null or radiacao_mj >= 0)
),

-- Agrega diário → Semana Epidemiológica (início no domingo)
agregado_se as (
    select
        -- Início da SE = domingo anterior
        date_trunc('week', data) - interval '1 day'            as data_se,

        -- Temperatura: média da SE
        round(avg(temp_media_nasa), 2)                         as temp_media_nasa,
        round(avg(temp_max_nasa), 2)                           as temp_max_nasa,
        round(avg(temp_min_nasa), 2)                           as temp_min_nasa,
        round(avg(umidade_nasa), 2)                            as umidade_nasa,
        round(avg(radiacao_mj), 2)                             as radiacao_mj,

        -- Precipitação: acumulado da SE
        round(sum(precipitacao_nasa), 2)                       as precipitacao_total_nasa,

        -- Qualidade: quantos dias válidos na SE
        count(*)                                               as dias_validos_se,
        count(temp_media_nasa)                                 as dias_temp_validos

    from validado
    group by date_trunc('week', data) - interval '1 day'
),

finalizado as (
    select
        *,
        -- Flag de qualidade: SE com menos de 5 dias válidos
        case when dias_validos_se < 5 then true
             else false end                                    as flag_se_incompleta,
        current_timestamp                                      as dbt_updated_at
    from agregado_se
    where data_se >= cast('{{ var("data_inicio") }}' as date)
      and data_se <= cast('{{ var("data_fim") }}' as date)
)

select * from finalizado