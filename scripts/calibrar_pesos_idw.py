# ============================================================
# Dengue MT — Calibração de Pesos IDW por UBS
# ============================================================
# Execução: única (ou anual)
# Uso: python scripts/calibrar_pesos_idw.py
#
# O que faz:
#   1. Baixa shapefile IBGE CD2022 — 143 bairros Cuiabá + VG
#   2. Carrega UBS do score_risco_v2.parquet (HF Hub)
#   3. Calcula peso IDW por UBS para cada bairro
#      peso = casos_historicos / distancia_centroide²
#   4. Salva pesos_idw_ubs.json + bairros_cuiaba_vg.geojson
#   5. Publica ambos no HF Hub
# ============================================================

import os
import json
import requests
import zipfile
import tempfile
import numpy as np
import pandas as pd
import geopandas as gpd
from pathlib import Path
from dotenv import load_dotenv
from math import radians, cos, sin, asin, sqrt

load_dotenv()

HF_REPO_ID = 'edyestatistica/dengue-mt-medallion'
HF_TOKEN   = os.environ.get('HF_TOKEN')
ROOT_DIR   = Path(__file__).parent.parent

MUNICIPIOS = {
    '5103403': 'Cuiabá',
    '5108402': 'Várzea Grande',
}

URL_IBGE = (
    'https://geoftp.ibge.gov.br/organizacao_do_territorio/'
    'malhas_territoriais/malhas_de_setores_censitarios__divisoes_intramunicipais/'
    'censo_2022/bairros/shp/UF/MT_bairros_CD2022.zip'
)


def haversine(lat1, lon1, lat2, lon2) -> float:
    """Distância em km entre dois pontos geográficos."""
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return R * 2 * asin(sqrt(a))


def baixar_shapefile() -> gpd.GeoDataFrame:
    """Baixa shapefile IBGE e retorna GeoDataFrame dos 143 bairros."""
    print('Baixando shapefile IBGE CD2022...')
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / 'MT_bairros_CD2022.zip'
        r = requests.get(URL_IBGE, stream=True, timeout=120)
        r.raise_for_status()
        with open(zip_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmp)

        shp = list(Path(tmp).glob('*.shp'))[0]
        gdf = gpd.read_file(shp)

    # Filtra Cuiabá e Várzea Grande
    # CD_MUN no shapefile usa 7 dígitos sem o dígito verificador
    gdf = gdf[gdf['CD_MUN'].isin(['5103403', '5108402'])].copy()
    gdf = gdf.to_crs('EPSG:4326')

    print(f'  Bairros carregados: {len(gdf)} '
          f'(Cuiabá: {len(gdf[gdf["CD_MUN"]=="5103403"])} | '
          f'VG: {len(gdf[gdf["CD_MUN"]=="5108402"])})')
    return gdf


def carregar_ubs() -> pd.DataFrame:
    """Carrega UBS do HF Hub."""
    from huggingface_hub import hf_hub_download
    print('Carregando UBS do HF Hub...')
    path = hf_hub_download(
        repo_id=HF_REPO_ID,
        filename='external/score_risco_v2.parquet',
        repo_type='dataset',
        token=HF_TOKEN,
    )
    df = pd.read_parquet(path)
    # Normaliza codigo_municipio para 7 dígitos string
    df['codigo_municipio'] = df['codigo_municipio'].astype(str).str[:7]
    print(f'  UBS carregadas: {len(df)}')
    return df


def calcular_pesos_idw(gdf_bairros: gpd.GeoDataFrame,
                        df_ubs: pd.DataFrame) -> dict:
    """
    Calcula pesos IDW por UBS para cada bairro.

    peso_ubs_i_no_bairro_j = casos_historicos_i / distancia(i,j)²
    peso_normalizado = peso_ubs_i / Σ peso_ubs_k  (para o bairro j)

    Retorna dict: {cd_bairro: {codigo_cnes: peso_normalizado}}
    """
    print('Calculando centroides dos bairros...')
    gdf_bairros = gdf_bairros.copy()
    # Reprojetar para SIRGAS 2000 UTM zona 21S (EPSG:31981)
    # projeção métrica oficial para Mato Grosso — centroides mais precisos
    centroides = (
        gdf_bairros.geometry
        .to_crs('EPSG:31981')
        .centroid
        .to_crs('EPSG:4326')
    )
    gdf_bairros['lat_centroide'] = centroides.y
    gdf_bairros['lon_centroide'] = centroides.x

    pesos = {}
    print('Calculando pesos IDW...')

    for _, bairro in gdf_bairros.iterrows():
        cd_bairro  = bairro['CD_BAIRRO']
        cd_mun     = bairro['CD_MUN']
        lat_b      = bairro['lat_centroide']
        lon_b      = bairro['lon_centroide']

        # Filtra UBS do mesmo município
        df_mun = df_ubs[df_ubs['codigo_municipio'] == cd_mun].copy()

        if df_mun.empty:
            pesos[cd_bairro] = {}
            continue

        pesos_brutos = {}
        for _, ubs in df_mun.iterrows():
            dist_km = haversine(
                lat_b, lon_b,
                ubs['latitude_estabelecimento_decimo_grau'],
                ubs['longitude_estabelecimento_decimo_grau']
            )
            # Evita divisão por zero — distância mínima 0.1 km
            dist_km = max(dist_km, 0.1)

            # Peso = casos históricos / distância²
            casos = max(float(ubs['casos_historicos']), 1.0)
            pesos_brutos[str(ubs['codigo_cnes'])] = casos / (dist_km ** 2)

        # Normaliza
        total = sum(pesos_brutos.values())
        pesos[cd_bairro] = {
            cnes: round(p / total, 6)
            for cnes, p in pesos_brutos.items()
        }

    return pesos


def publicar_hf(path_local: Path, path_hf: str):
    """Publica arquivo no HF Hub."""
    from huggingface_hub import HfApi
    api = HfApi()
    api.upload_file(
        path_or_fileobj=str(path_local),
        path_in_repo=path_hf,
        repo_id=HF_REPO_ID,
        repo_type='dataset',
        token=HF_TOKEN,
    )
    print(f'  Publicado: {path_hf}')


def main():
    print(f'\n{"="*55}')
    print('Calibração Pesos IDW — Dengue MT')
    print(f'{"="*55}\n')

    ext_dir = ROOT_DIR / 'data' / 'external'
    ext_dir.mkdir(parents=True, exist_ok=True)

    # 1. Shapefile
    gdf_bairros = baixar_shapefile()

    # 2. UBS
    df_ubs = carregar_ubs()

    # 3. Pesos IDW
    pesos = calcular_pesos_idw(gdf_bairros, df_ubs)
    print(f'  Pesos calculados para {len(pesos)} bairros')

    # 4. Salva pesos JSON
    # Inclui metadados do bairro para facilitar o dashboard
    output_pesos = {
        'metadata': {
            'metodo':      'IDW — casos_historicos / distancia_km²',
            'municipios':  list(MUNICIPIOS.values()),
            'n_bairros':   len(pesos),
            'n_ubs':       len(df_ubs),
            'fonte_ubs':   'CNES via score_risco_v2',
            'fonte_shape': 'IBGE CD2022',
        },
        'pesos': pesos
    }
    path_pesos = ext_dir / 'pesos_idw_ubs.json'
    with open(path_pesos, 'w', encoding='utf-8') as f:
        json.dump(output_pesos, f, ensure_ascii=False, indent=2)
    print(f'  Pesos salvos: {path_pesos.name}')

    # 5. Salva GeoJSON dos bairros com metadados
    gdf_export = gdf_bairros[[
        'CD_BAIRRO', 'NM_BAIRRO', 'CD_MUN', 'NM_MUN', 'geometry'
    ]].copy()
    path_geojson = ext_dir / 'bairros_cuiaba_vg.geojson'
    gdf_export.to_file(path_geojson, driver='GeoJSON')
    print(f'  GeoJSON salvo: {path_geojson.name}')

    # 6. Publica no HF Hub
    print('\nPublicando no HF Hub...')
    publicar_hf(path_pesos,   'external/pesos_idw_ubs.json')
    publicar_hf(path_geojson, 'external/bairros_cuiaba_vg.geojson')

    print(f'\n{"="*55}')
    print('Calibração concluída!')
    print(f'  Bairros: {len(pesos)}')
    print(f'  UBS:     {len(df_ubs)}')
    print(f'{"="*55}\n')


if __name__ == '__main__':
    main()