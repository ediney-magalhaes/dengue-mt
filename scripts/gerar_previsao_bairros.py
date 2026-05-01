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
#   6. Calcula limiares adaptativos percentílicos
#   7. Classifica nível de risco por bairro
#   8. Salva previsao_bairros_latest.geojson (limiares embutidos)
#   9. Publica no HF Hub
#
# Propriedade pycnophylactic (conservação de massa):
#   Σ casos_bairro_i (município X) = previsao_municipal_X
#
# Limiares adaptativos:
#   Calculados por percentis (P60/P75/P85/P95) sobre a distribuição
#   IDW de cada município. Recalculados a cada execução — sem hardcode.
#   Referência: CDC/OPAS epidemic threshold via negative binomial
#   percentiles (2024).
#
# Referências:
#   - Shepard (1968) — IDW original
#   - Cromley & McLafferty (2011) — GIS and Public Health
#   - Opasnet (2014) — Spatial disaggregation mass-preserving
# ============================================================

import os
import json
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

CORES_RISCO = {
    'Muito Alto':  '#d73027',
    'Alto':        '#fc8d59',
    'Moderado':    '#fee090',
    'Baixo':       '#91bfdb',
    'Muito Baixo': '#4575b4',
}

NIVEIS_ORDEM = ['Muito Baixo', 'Baixo', 'Moderado', 'Alto', 'Muito Alto']


# ── Helpers ───────────────────────────────────────────────

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


# ── Carregamento de dados ─────────────────────────────────

def carregar_pesos_idw() -> dict:
    """Carrega scores IDW brutos do HF Hub."""
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


# ── Previsão municipal ────────────────────────────────────

def gerar_previsao_municipal(semanas: int = 4) -> list[dict]:
    """
    Gera previsão municipal SE+1→SE+4 via LightGBM.
    Aplica expm1() para reverter transformação log1p do target.
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
            casos_pred = max(float(np.expm1(modelo.predict(ultima_linha)[0])), 0)
            previsoes.append({
                'municipio_id':    mun_id,
                'cd_mun':          info['cd_mun'],
                'nome_municipio':  info['nome'],
                'horizonte_se':    i,
                'data_se':         data_prev.strftime('%Y-%m-%d'),
                'casos_municipio': round(casos_pred, 1),
            })
        print(f'  {info["nome"]}: SE+1={previsoes[-semanas]["casos_municipio"]:.0f} casos')

    return previsoes


# ── Distribuição IDW ──────────────────────────────────────

def calcular_fracoes_idw(gdf_bairros: gpd.GeoDataFrame,
                          pesos: dict) -> dict:
    """
    Normaliza scores IDW brutos por município.
    fracao_bairro = score_bairro / Σ scores_municipio
    Garante: Σ frações por município = 1.0 (mass-preserving).
    """
    fracao = {}
    for cd_mun in gdf_bairros['CD_MUN'].unique():
        bairros_mun = gdf_bairros[gdf_bairros['CD_MUN'] == cd_mun]['CD_BAIRRO'].tolist()
        total_mun   = sum(pesos.get(b, 0) for b in bairros_mun)
        for b in bairros_mun:
            if total_mun > 0:
                fracao[b] = pesos.get(b, 0) / total_mun
            else:
                fracao[b] = 1.0 / len(bairros_mun)

    return fracao


def distribuir_casos(previsoes_municipais: list[dict],
                     gdf_bairros: gpd.GeoDataFrame,
                     fracao: dict,
                     semanas: int = 4) -> gpd.GeoDataFrame:
    """
    Distribui previsão municipal pelos bairros via fração IDW.
    Propriedade pycnophylactic: Σ casos_bairro = casos_municipio.
    Não classifica risco — apenas distribui valores.
    """
    print('Distribuindo previsão pelos bairros via IDW...')

    idx_previsao = {
        (p['cd_mun'], p['horizonte_se']): p['casos_municipio']
        for p in previsoes_municipais
    }

    registros = []
    for _, bairro in gdf_bairros.iterrows():
        cd_bairro = bairro['CD_BAIRRO']
        cd_mun    = bairro['CD_MUN']

        row = {
            'CD_BAIRRO': cd_bairro,
            'NM_BAIRRO': bairro['NM_BAIRRO'],
            'CD_MUN':    cd_mun,
            'NM_MUN':    bairro['NM_MUN'],
            'geometry':  bairro['geometry'],
        }

        for h in range(1, semanas + 1):
            casos_mun    = idx_previsao.get((cd_mun, h), 0)
            casos_bairro = round(casos_mun * fracao[cd_bairro], 2)
            row[f'casos_se{h}'] = casos_bairro

        registros.append(row)

    gdf = gpd.GeoDataFrame(registros, crs='EPSG:4326')
    print(f'  Distribuição concluída: {len(gdf)} bairros × {semanas} horizontes')
    return gdf


# ── Limiares adaptativos ─────────────────────────────────

def calcular_limiares(gdf: gpd.GeoDataFrame, semanas: int = 4) -> dict:
    """
    Calcula limiares adaptativos por percentis da distribuição
    IDW de cada município (baseado em SE+1).

    Recalculados a cada execução semanal — nunca hardcoded.
    Garante que sempre haverá bairros em múltiplos níveis,
    independente de período sazonal.

    Referência: CDC/OPAS (2024) — epidemic alert thresholds
    via negative binomial percentiles (P60, P75, P85, P95).

    Retorna: {cd_mun: {P60: x, P75: x, P85: x, P95: x}}
    """
    print('Calculando limiares adaptativos...')

    limiares = {}
    for cd_mun in gdf['CD_MUN'].unique():
        casos = gdf.loc[gdf['CD_MUN'] == cd_mun, 'casos_se1'].values

        limiares[cd_mun] = {
            'P60': round(float(np.percentile(casos, 60)), 3),
            'P75': round(float(np.percentile(casos, 75)), 3),
            'P85': round(float(np.percentile(casos, 85)), 3),
            'P95': round(float(np.percentile(casos, 95)), 3),
        }

        nome = next(v['nome'] for v in MUNICIPIOS.values()
                    if v['cd_mun'] == cd_mun)
        lim = limiares[cd_mun]
        print(f'  {nome}: P60={lim["P60"]:.3f} | P75={lim["P75"]:.3f} | '
              f'P85={lim["P85"]:.3f} | P95={lim["P95"]:.3f}')

    return limiares


def classificar_risco(casos: float, lim: dict) -> str:
    """Classifica risco usando limiares adaptativos do município."""
    if casos > lim['P95']:
        return 'Muito Alto'
    if casos > lim['P85']:
        return 'Alto'
    if casos > lim['P75']:
        return 'Moderado'
    if casos > lim['P60']:
        return 'Baixo'
    return 'Muito Baixo'


def aplicar_classificacao(gdf: gpd.GeoDataFrame,
                           limiares: dict,
                           semanas: int = 4) -> gpd.GeoDataFrame:
    """
    Aplica classificação de risco a todos os bairros usando
    limiares adaptativos do município correspondente.
    """
    print('Classificando risco por bairro...')
    gdf = gdf.copy()

    for idx, row in gdf.iterrows():
        lim = limiares[row['CD_MUN']]
        for h in range(1, semanas + 1):
            nivel = classificar_risco(row[f'casos_se{h}'], lim)
            gdf.at[idx, f'nivel_risco_se{h}'] = nivel
            gdf.at[idx, f'cor_se{h}']         = CORES_RISCO[nivel]

    # Resumo
    dist = gdf['nivel_risco_se1'].value_counts().to_dict()
    print(f'  SE+1: {dist}')

    return gdf


# ── Main ──────────────────────────────────────────────────

def main(semanas: int = 4):
    print(f'\n{"="*55}')
    print('Geração Previsão por Bairro — IDW Dengue MT')
    print(f'{"="*55}\n')

    # 1. Carrega dados
    pesos       = carregar_pesos_idw()
    gdf_bairros = carregar_bairros()

    # 2. Previsão municipal
    previsoes_municipais = gerar_previsao_municipal(semanas)

    # 3. Calcula frações IDW (normalizadas por município)
    fracao = calcular_fracoes_idw(gdf_bairros, pesos)

    # 4. Distribui casos pelos bairros (sem classificação)
    gdf = distribuir_casos(previsoes_municipais, gdf_bairros, fracao, semanas)

    # 5. Calcula limiares adaptativos percentílicos
    limiares = calcular_limiares(gdf, semanas)

    # 6. Aplica classificação de risco
    gdf = aplicar_classificacao(gdf, limiares, semanas)

    # 7. Salva GeoJSON com limiares embutidos como metadados
    ext_dir  = ROOT_DIR / 'data' / 'external'
    ext_dir.mkdir(parents=True, exist_ok=True)
    path_out = ext_dir / 'previsao_bairros_latest.geojson'
    gdf.to_file(path_out, driver='GeoJSON')

    # Injeta limiares e metadados no GeoJSON
    with open(path_out, encoding='utf-8') as f:
        geojson = json.load(f)

    geojson['limiares_risco'] = limiares
    geojson['gerado_em']      = datetime.now().isoformat()
    geojson['modelo']         = 'LightGBM v5'
    geojson['metodo']         = 'IDW mass-preserving — Shepard 1968'
    geojson['n_bairros']      = len(gdf)
    geojson['semanas']        = semanas

    with open(path_out, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False)

    print(f'\n  GeoJSON salvo: {path_out.name}')
    print(f'  Bairros: {len(gdf)} | Horizontes: SE+1→SE+{semanas}')
    print(f'  Limiares adaptativos embutidos')

    # 8. Publica no HF Hub
    print('\nPublicando no HF Hub...')
    publicar_hf(path_out, 'external/previsao_bairros_latest.geojson')

    # Resumo
    print(f'\n{"="*55}')
    print('Previsão por bairro concluída!')
    for p in previsoes_municipais:
        if p['horizonte_se'] == 1:
            print(f"  {p['nome_municipio']} SE+1: {p['casos_municipio']:.0f} casos")
    for cd_mun, lim in limiares.items():
        nome = next(v['nome'] for v in MUNICIPIOS.values()
                    if v['cd_mun'] == cd_mun)
        print(f'  {nome} limiares: {lim}')
    print(f'{"="*55}\n')


if __name__ == '__main__':
    main()