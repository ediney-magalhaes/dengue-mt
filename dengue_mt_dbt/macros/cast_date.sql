-- macros/cast_date.sql
-- Converte qualquer campo para DATE de forma padronizada

-- Converte qualquer campo para DATE de forma padronizada
{% macro cast_date(column) %}
    cast({{ column }} as date)
{% endmacro %}

-- Calcula o primeiro domingo a partir de uma data
{% macro primeiro_domingo(date_str) %}
    cast({{ date_str }} as date) + 
    case dayofweek(cast({{ date_str }} as date))
        when 0 then 0
        else 7 - dayofweek(cast({{ date_str }} as date))
    end
{% endmacro %}


-- Converte timestamp em milissegundos (BIGINT) para DATE
-- Usado especificamente para data_iniSE da InfoDengue
{% macro cast_epoch_ms(column) %}
    epoch_ms({{ column }})::date
{% endmacro %}


-- Calcula início da Semana Epidemiológica brasileira (domingo)
-- Portaria SVS/MS nº 5/2010 — SE começa no domingo
{% macro inicio_se(column) %}
    cast({{ column }} as date) - cast(dayofweek(cast({{ column }} as date)) as integer)
{% endmacro %}