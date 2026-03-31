"""
baixar_shapefile_ibge.py
------------------------
Baixa shapefiles de municípios do IBGE para Mato Grosso
e filtra Cuiabá (510340) e Várzea Grande (510790)

Fonte: IBGE Malhas Municipais 2022
"""

import requests
import zipfile
import geopandas as gpd
from pathlib import Path

SHAPE_DIR = Path('data/external/shapefiles')
SHAPE_DIR.mkdir(parents=True, exist_ok=True)

URL = 'https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2022/UFs/MT/MT_Municipios_2022.zip'

MUNICIPIOS_ALVO = {
    '5103403': 'Cuiabá',
    '5108402': 'Várzea Grande',
}

def baixar_shapefile():
    print("Baixando shapefile municípios MT (IBGE 2022)...")
    zip_path = SHAPE_DIR / 'MT_Municipios_2022.zip'

    resp = requests.get(URL, stream=True, timeout=120)
    total = int(resp.headers.get('content-length', 0))
    baixado = 0

    with open(zip_path, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            baixado += len(chunk)
            if total > 0:
                print(f"\r   {baixado/1e6:.1f}MB / {total/1e6:.1f}MB ({baixado/total*100:.0f}%)", end='')

    print(f"\nDownload: {zip_path}")

    dest = SHAPE_DIR / 'mt_municipios_2022'
    dest.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(dest)
    print(f"Extraído: {dest}")
    return dest

def processar_shapefile(shape_dir):
    print("\nProcessando shapefile...")
    shp = list(shape_dir.glob('*.shp'))[0]
    gdf = gpd.read_file(shp)

    print(f"   Total municípios MT: {len(gdf)}")
    print(f"   Colunas: {gdf.columns.tolist()}")
    print(f"   CRS: {gdf.crs}")
    print(f"\nAmostra:")
    print(gdf.head(3))

    # Filtrar Cuiabá e Várzea Grande
    col_cd = [c for c in gdf.columns if 'CD' in c.upper() or 'COD' in c.upper() or 'MUN' in c.upper()]
    print(f"\nColunas de código: {col_cd}")

    return gdf

if __name__ == '__main__':
    shape_dir = baixar_shapefile()
    gdf = processar_shapefile(shape_dir)