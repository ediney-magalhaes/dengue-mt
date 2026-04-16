"""
Auditoria do intermediate int_dengue_mt
Verifica completude, nulos e cobertura por fonte
"""
import duckdb

conn = duckdb.connect('dengue_mt_dbt/dev.duckdb')

print('=== COBERTURA POR FONTE ===')
df = conn.execute("""
    SELECT
        municipio_id,
        count(*)                                                  as total_semanas,
        count(casos_confirmados)                                  as casos_ok,
        count(precipitacao_total_nasa)                            as nasa_ok,
        count(oni_index)                                          as oni_ok,
        count(trends_dengue)                                      as trends_ok,
        count(ndvi)                                               as modis_ok,
        round(100.0 * count(precipitacao_total_nasa)/count(*), 1) as pct_nasa,
        round(100.0 * count(oni_index)/count(*), 1)               as pct_oni,
        round(100.0 * count(trends_dengue)/count(*), 1)           as pct_trends,
        round(100.0 * count(ndvi)/count(*), 1)                    as pct_modis
    FROM main_intermediate.int_dengue_mt
    GROUP BY municipio_id
    ORDER BY municipio_id
""").df()
print(df.to_string())

print('\n=== PERÍODO ===')
df2 = conn.execute("""
    SELECT municipio_id, min(data_se) as data_min,
           max(data_se) as data_max, count(*) as total
    FROM main_intermediate.int_dengue_mt
    GROUP BY municipio_id
""").df()
print(df2.to_string())

print('\n=== SEMANAS FALTANDO NASA ===')
df3 = conn.execute("""
    SELECT municipio_id, data_se
    FROM main_intermediate.int_dengue_mt
    WHERE precipitacao_total_nasa IS NULL
    ORDER BY data_se
""").df()
print(f'Total: {len(df3)}')
print(df3.to_string())

print('\n=== SEMANAS FALTANDO ONI ===')
df4 = conn.execute("""
    SELECT DISTINCT data_se
    FROM main_intermediate.int_dengue_mt
    WHERE oni_index IS NULL
    ORDER BY data_se
""").df()
print(f'Total: {len(df4)}')
print(df4.to_string())

print('\n=== SEMANAS FALTANDO MODIS ===')
df5 = conn.execute("""
    SELECT DISTINCT data_se
    FROM main_intermediate.int_dengue_mt
    WHERE ndvi IS NULL
    ORDER BY data_se
""").df()
print(f'Total: {len(df5)}')
print(df5.to_string())