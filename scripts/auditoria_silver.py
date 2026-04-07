import pandas as pd
from pathlib import Path

ROOT = Path('.')
SILVER = ROOT / 'data' / 'silver'


def auditar_silver(nome, path, col_data, col_valor=None, esperado_inicio=None, esperado_fim=None):
    print(f'\n{"="*60}')
    print(f'FONTE: {nome.upper()}')
    print(f'{"="*60}')

    p = Path(path)
    if not p.exists():
        print(f'❌ ARQUIVO NÃO EXISTE: {path}')
        return

    df = pd.read_parquet(p)
    print(f'Shape: {df.shape}')
    print(f'Colunas: {df.columns.tolist()}')

    # Período
    if col_data in df.columns:
        df[col_data] = pd.to_datetime(df[col_data])
        dmin = df[col_data].min().date()
        dmax = df[col_data].max().date()
        print(f'Período: {dmin} → {dmax}')

        # Checar período esperado
        if esperado_inicio and dmin > pd.to_datetime(esperado_inicio).date():
            print(f'⚠️  INÍCIO POSTERIOR AO ESPERADO! Esperado: {esperado_inicio} | Encontrado: {dmin}')
        if esperado_fim and dmax < pd.to_datetime(esperado_fim).date():
            print(f'⚠️  FIM ANTERIOR AO ESPERADO! Esperado: {esperado_fim} | Encontrado: {dmax}')

        # Gaps temporais
        datas = df[col_data].drop_duplicates().sort_values()
        diff = datas.diff().dropna()
        gaps = diff[diff > pd.Timedelta('35 days')]
        if len(gaps) > 0:
            print(f'⚠️  GAPS TEMPORAIS: {len(gaps)} gaps > 35 dias')
            for i in range(len(gaps)):
                idx = gaps.index[i]
                pos = datas.index.get_loc(idx)
                antes = datas.iloc[pos - 1].date()
                depois = datas.iloc[pos].date()
                print(f'    {antes} → {depois} ({gaps.iloc[i].days} dias)')
        else:
            print(f'✅ Sem gaps temporais')

        # Duplicatas temporais
        dupl = df.duplicated(subset=[col_data]).sum()
        if dupl > 0:
            print(f'⚠️  DUPLICATAS na coluna data: {dupl}')
        else:
            print(f'✅ Sem duplicatas temporais')
    else:
        print(f'❌ Coluna data "{col_data}" NÃO ENCONTRADA')

    # Nulos
    nulos = df.isnull().sum()
    nulos = nulos[nulos > 0]
    if len(nulos) > 0:
        print(f'⚠️  Nulos:')
        for col, n in nulos.items():
            pct = n / len(df) * 100
            print(f'    {col}: {n} ({pct:.1f}%)')
    else:
        print(f'✅ Sem nulos')

    # Valores -999
    nums = df.select_dtypes('number')
    inv = (nums == -999).sum().sum()
    if inv > 0:
        print(f'❌ VALORES -999 NÃO TRATADOS: {inv}')
    else:
        print(f'✅ Sem valores -999')

    # Coluna de valor principal
    if col_valor and col_valor in df.columns:
        negativos = (df[col_valor] < 0).sum()
        print(f'\nEstatísticas {col_valor}:')
        print(df[col_valor].describe().round(2).to_string())
        if negativos > 0:
            print(f'⚠️  Valores negativos: {negativos}')
        else:
            print(f'✅ Sem negativos')


if __name__ == '__main__':
    print('AUDITORIA COMPLETA — CAMADA SILVER')
    print(f'Data de execução: {pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}')

    auditar_silver(
        nome='InfoDengue — 2025/atual',
        path='data/silver/infodengue/infodengue_2025_atual.parquet',
        col_data='data',
        col_valor='casos_confirmados',
        esperado_inicio='2024-12-29',
        esperado_fim='2026-03-15',
    )

    auditar_silver(
        nome='NASA POWER — 2025/atual',
        path='data/silver/nasa_power/nasa_power_2025_atual.parquet',
        col_data='data',
        col_valor='temp_media',
        esperado_inicio='2025-01-01',
        esperado_fim='2026-03-21',
    )

    auditar_silver(
        nome='ONI Index',
        path='data/silver/oni/oni_index_latest.parquet',
        col_data='data',
        col_valor='oni_index',
        esperado_inicio='2018-01-01',
    )

    auditar_silver(
        nome='Google Trends',
        path='data/silver/trends/trends_dengue_latest.parquet',
        col_data='data',
        col_valor='trends_dengue',
        esperado_inicio='2025-12-01',
    )

    auditar_silver(
        nome='INMET — histórico 2018-2024',
        path='data/silver/inmet/inmet_cuiaba_2018_2024.parquet',
        col_data='data',
        col_valor='temp_media',
        esperado_inicio='2018-01-01',
        esperado_fim='2024-12-31',
    )

    auditar_silver(
        nome='GEE — blend 2018-2024',
        path='data/silver/gee/gee_ndvi_ndwi_blend_2018_2024.parquet',
        col_data='data',
        col_valor='ndvi_final',
        esperado_inicio='2018-01-01',
        esperado_fim='2024-12-01',
    )

    auditar_silver(
        nome='SINAN — 2007',
        path='data/silver/sinan/dengue_mt_2007.parquet',
        col_data='data',
        col_valor='casos',
        esperado_inicio='2007-01-01',
        esperado_fim='2007-12-31',
    )

    auditar_silver(
        nome='SINAN — 2024',
        path='data/silver/sinan/dengue_mt_2024.parquet',
        col_data='data',
        col_valor='casos',
        esperado_inicio='2024-01-01',
        esperado_fim='2024-12-31',
    )

    print(f'\n{"="*60}')
    print('AUDITORIA SILVER CONCLUÍDA')
    print(f'{"="*60}')