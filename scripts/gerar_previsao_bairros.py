# ============================================================
# Dengue MT — Geração de Previsão por Bairro via IDW
# ============================================================
# Execução: semanal (chamado pelo pipeline_prefect.py)
# Uso: python scripts/gerar_previsao_bairros.py
#
# O que faz:
#   1. Carrega pesos IDW calibrados do HF Hub
#   2. Carrega GeoJSON dos bairros do HF Hub
#   3. Carrega Gold latest + modelo LightGBM do HF Hub
#   4. Gera previsão municipal SE+1→SE+4 (com expm1)
#   5. Distribui previsão pelos bairros via IDW (mass-preserving)
#   6. Classifica nível de risco por bairro
#   7. Salva previsao_bairros_latest.geojson
#   8. Publica no HF Hub
#
# Propriedade pycnophylactic (conservação de massa):
#   Σ casos_bairro_i (município X) = previsao_municipal_X
#
# Referências:
#   - Shepard (1968) — IDW original
#   - Cromley & McLafferty (2011) — GIS and Public Health
#   - Opasnet (2014) — Spatial disaggregation mass-preserving
# ============================================================

import os
import json
import tempfile
import numpy as np
import pandas as pd
import geopandas as gpd
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

HF_REPO_ID = 'edyestatistica/dengue-mt-medallion'
HF_TOKEN   = os.environ.get('HF_TOKEN')
ROOT_DIR   = Path(__file__).parent.parent

MUNICIPIOS = {
    5103403: {'nome': 'Cuiabá',       'cd_mun': '5103403'},
    5108402: {'nome': 'Várzea Grande', 'cd_mun': '5108402'},
}

NIVEIS_RISCO = [
    (200, 'Muito Alto'),
    (100, 'Alto'),
    (50,  'Moderado'),
    (20,  'Baixo'),
    (0,   'Muito Baixo'),
]

CORES_RISCO = {
    'Muito Alto':  '#d73027',
    'Alto':        '#fc8d59',
    'Moderado':    '#fee090',
    'Baixo':       '#91bfdb',
    'Muito Baixo': '#4575b4',
}


def classificar_risco(casos: float) -> str:
    for limiar, nivel in NIVEIS_RISCO:
        if casos > limiar:
            return nivel
    return 'Muito Baixo'


def carregar_do_hf(filename: str, repo_id: str = HF_REPO_ID,
                   token: str = HF_TOKEN):
    """Baixa arquivo do HF Hub e retorna path local."""
    from huggingface_hub import hf_hub_download
    return hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        repo_type='dataset',
        token=token,
    )


def carregar_pesos_idw() -> dict:
    """Carrega pesos IDW calibrados do HF Hub."""
    print('Carregando pesos IDW do HF Hub...')
    path = carregar_do_hf('external/pesos_idw_ubs.json')
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    pesos = data['pesos']
    print(f'  Pesos carregados: {len(pesos)} bairros')
    return pesos


def carregar_bairros() -> gpd.GeoDataFrame:
    """Carrega GeoJSON dos bairros do HF Hub."""
    print('Carregando bairros do HF Hub...')
    path = carregar_do_hf('external/bairros_cuiaba_vg.geojson')
    gdf  = gpd.read_file(path)
    print(f'  Bairros carregados: {len(gdf)}')
    return gdf


def gerar_previsao_municipal(semanas: int = 4) -> list[dict]:
    """
    Gera previsão municipal SE+1→SE+4 via LightGBM.
    Aplica expm1() para reverter transformação log1p do target.
    Retorna lista de dicts: {municipio_id, horizonte_se, casos_previstos, data_se}
    """
    import joblib
    print('Carregando modelo e Gold do HF Hub...')

    path_modelo = carregar_do_hf('models/lgbm_producao_latest.pkl')
    path_gold   = carregar_do_hf('gold/dataset_features_latest.parquet')

    modelo   = joblib.load(path_modelo)
    df_gold  = pd.read_parquet(path_gold)
    df_gold['data_se'] = pd.to_datetime(df_gold['data_se'])
    df_gold  = df_gold.sort_values('data_se')

    feature_cols = [c for c in modelo.feature_name_ if c in df_gold.columns]

    previsoes = []
    for mun_id, info in MUNICIPIOS.items():
        df_mun      = df_gold[df_gold['municipio_id'] == mun_id]
        ultima_linha = df_mun[feature_cols].iloc[[-1]]
        ultima_data  = df_mun['data_se'].max()

        for i in range(1, semanas + 1):
            data_prev  = ultima_data + timedelta(weeks=i)
            # expm1() reverte log1p — ADR-024
            casos_pred = max(float(np.expm1(modelo.predict(ultima_linha)[0])), 0)
            previsoes.append({
                'municipio_id':  mun_id,
                'cd_mun':        info['cd_mun'],
                'nome_municipio': info['nome'],
                'horizonte_se':  i,
                'data_se':       data_prev.strftime('%Y-%m-%d'),
                'casos_municipio': round(casos_pred, 1),
            })
        print(f'  {info["nome"]}: SE+1={previsoes[-semanas]["casos_municipio"]:.0f} casos')

    return previsoes


def distribuir_idw(previsoes_municipais: list[dict],
                   gdf_bairros: gpd.GeoDataFrame,
                   pesos: dict) -> gpd.GeoDataFrame:
    """
    Distribui previsão municipal pelos bairros via IDW.
    Propriedade pycnophylactic: Σ casos_bairro = casos_municipio.

    Para cada bairro b no município M e horizonte H:
      casos_bairro_b_H = casos_municipio_M_H × peso_normalizado_bairro_b
    """
    print('Distribuindo previsão pelos bairros via IDW...')

    # Índice: (cd_mun, horizonte_se) → casos_municipio
    idx_previsao = {
        (p['cd_mun'], p['horizonte_se']): p['casos_municipio']
        for p in previsoes_municipais
    }

    # Horizonte máximo
    semanas = max(p['horizonte_se'] for p in previsoes_municipais)

    registros = []
    for _, bairro in gdf_bairros.iterrows():
        cd_bairro = bairro['CD_BAIRRO']
        cd_mun    = bairro['CD_MUN']
        nm_bairro = bairro['NM_BAIRRO']
        nm_mun    = bairro['NM_MUN']

        # Pesos deste bairro
        pesos_bairro = pesos.get(cd_bairro, {})
        peso_total   = sum(pesos_bairro.values())

        row = {
            'CD_BAIRRO': cd_bairro,
            'NM_BAIRRO': nm_bairro,
            'CD_MUN':    cd_mun,
            'NM_MUN':    nm_mun,
            'geometry':  bairro['geometry'],
        }

        for h in range(1, semanas + 1):
            casos_mun = idx_previsao.get((cd_mun, h), 0)

            # Distribuição mass-preserving
            if peso_total > 0:
                casos_bairro = round(casos_mun * peso_total, 1)
            else:
                # Fallback: distribuição uniforme
                n_bairros_mun = len(gdf_bairros[gdf_bairros['CD_MUN'] == cd_mun])
                casos_bairro  = round(casos_mun / max(n_bairros_mun, 1), 1)

            nivel = classificar_risco(casos_bairro)
            row[f'casos_se{h}']     = casos_bairro
            row[f'nivel_risco_se{h}'] = nivel
            row[f'cor_se{h}']       = CORES_RISCO[nivel]

        registros.append(row)

    gdf_result = gpd.GeoDataFrame(registros, crs='EPSG:4326')
    print(f'  Distribuição concluída: {len(gdf_result)} bairros × {semanas} horizontes')
    return gdf_result


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


def main(semanas: int = 4):
    print(f'\n{"="*55}')
    print('Geração Previsão por Bairro — IDW Dengue MT')
    print(f'{"="*55}\n')

    # 1. Carrega dados
    pesos       = carregar_pesos_idw()
    gdf_bairros = carregar_bairros()

    # 2. Previsão municipal
    previsoes_municipais = gerar_previsao_municipal(semanas)

    # 3. Distribui via IDW
    gdf_resultado = distribuir_idw(previsoes_municipais, gdf_bairros, pesos)

    # 4. Adiciona metadados ao GeoJSON
    gdf_resultado.attrs = {
        'gerado_em':      datetime.now().isoformat(),
        'semanas':        semanas,
        'metodo':         'IDW mass-preserving — Shepard 1968',
        'modelo':         'LightGBM v5',
        'municipios':     [info['nome'] for info in MUNICIPIOS.values()],
        'n_bairros':      len(gdf_resultado),
    }

    # 5. Salva GeoJSON
    ext_dir  = ROOT_DIR / 'data' / 'external'
    ext_dir.mkdir(parents=True, exist_ok=True)
    path_out = ext_dir / 'previsao_bairros_latest.geojson'
    gdf_resultado.to_file(path_out, driver='GeoJSON')
    print(f'\n  GeoJSON salvo: {path_out.name}')
    print(f'  Bairros: {len(gdf_resultado)} | Horizontes: SE+1→SE+{semanas}')

    # 6. Publica no HF Hub
    print('\nPublicando no HF Hub...')
    publicar_hf(path_out, 'external/previsao_bairros_latest.geojson')

    # Resumo
    print(f'\n{"="*55}')
    print('Previsão por bairro concluída!')
    for p in previsoes_municipais:
        if p['horizonte_se'] == 1:
            print(f"  {p['nome_municipio']} SE+1: {p['casos_municipio']:.0f} casos")
    print(f'{"="*55}\n')


if __name__ == '__main__':
    main()