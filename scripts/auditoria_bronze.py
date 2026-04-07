import pandas as pd
from pathlib import Path

ROOT = Path('.')
BRONZE = ROOT / 'data' / 'bronze'

def auditar_fonte(nome, pasta, col_data, col_casos=None):
    print(f'\n{"="*60}')
    print(f'FONTE: {nome.upper()}')
    print(f'{"="*60}')
    
    arquivos = sorted(pasta.glob('*.parquet'))
    if not arquivos:
        print('❌ NENHUM ARQUIVO ENCONTRADO')
        return
    
    frames = []
    for f in arquivos:
        df = pd.read_parquet(f)
        print(f'\n  Arquivo: {f.name}')
        print(f'  Shape: {df.shape}')
        print(f'  Colunas: {df.columns.tolist()}')
        frames.append(df)
    
    # Concatena tudo para análise consolidada
    df_all = pd.concat(frames, ignore_index=True)
    
    # Período
    if col_data in df_all.columns:
        df_all[col_data] = pd.to_datetime(df_all[col_data])
        print(f'\n  Período consolidado: {df_all[col_data].min().date()} → {df_all[col_data].max().date()}')
        
        # Checar gaps
        datas = df_all[col_data].drop_duplicates().sort_values()
        diff = datas.diff().dropna()
        gaps = diff[diff > pd.Timedelta('35 days')]
        if len(gaps) > 0:
            print(f'  ⚠️  GAPS TEMPORAIS: {len(gaps)} gaps > 35 dias')
            for idx, g in gaps.items():
                print(f'      {datas[idx-1].date()} → {datas[idx].date()} ({g.days} dias)')
        else:
            print(f'  ✅ Sem gaps temporais relevantes')
    else:
        print(f'  ⚠️  Coluna data "{col_data}" não encontrada!')
    
    # Nulos
    nulos = df_all.isnull().sum()
    nulos = nulos[nulos > 0]
    if len(nulos) > 0:
        print(f'\n  ⚠️  Nulos encontrados:')
        for col, n in nulos.items():
            pct = n / len(df_all) * 100
            print(f'      {col}: {n} ({pct:.1f}%)')
    else:
        print(f'  ✅ Sem nulos')
    
    # Valores inválidos (-999 NASA POWER)
    nums = df_all.select_dtypes('number')
    invalidos = (nums == -999).sum().sum()
    if invalidos > 0:
        print(f'  ⚠️  Valores -999 (inválidos NASA): {invalidos}')
    
    # Casos negativos
    if col_casos and col_casos in df_all.columns:
        negativos = (df_all[col_casos] < 0).sum()
        if negativos > 0:
            print(f'  ⚠️  Casos negativos: {negativos}')
        else:
            print(f'  ✅ Sem casos negativos')
        print(f'\n  Estatísticas {col_casos}:')
        print(df_all[col_casos].describe().round(2).to_string())
    
    print(f'\n  Total registros consolidados: {len(df_all)}')


if __name__ == '__main__':
    print('AUDITORIA COMPLETA — CAMADA BRONZE')
    print('Data de execução:', pd.Timestamp.now().strftime('%Y-%m-%d %H:%M'))
    
    auditar_fonte(
        nome='InfoDengue',
        pasta=BRONZE / 'infodengue',
        col_data='data',
        col_casos='casos_confirmados'
    )
    
    auditar_fonte(
        nome='NASA POWER',
        pasta=BRONZE / 'nasa_power',
        col_data='data',
    )
    
    auditar_fonte(
        nome='ONI Index',
        pasta=BRONZE / 'oni',
        col_data='data',
    )
    
    auditar_fonte(
        nome='Google Trends',
        pasta=BRONZE / 'trends',
        col_data='data',
    )
    
    auditar_fonte(
        nome='SINAN',
        pasta=BRONZE / 'sinan',
        col_data='data',
        col_casos='casos'
    )
    
    auditar_fonte(
        nome='INMET',
        pasta=BRONZE / 'inmet',
        col_data='data',
    )
    
    auditar_fonte(
        nome='GEE',
        pasta=BRONZE / 'gee',
        col_data='data',
    )
    
    print(f'\n{"="*60}')
    print('AUDITORIA BRONZE CONCLUÍDA')
    print(f'{"="*60}')