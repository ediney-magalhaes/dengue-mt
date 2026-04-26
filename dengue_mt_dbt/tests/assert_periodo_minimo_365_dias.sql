-- Teste customizado: Gold deve cobrir pelo menos 365 dias
-- Falha se o range de datas for menor que 1 ano
select
    datediff('day', min(data_se), max(data_se)) as dias_cobertura
from {{ ref('mart_dengue_features') }}
having datediff('day', min(data_se), max(data_se)) < 365