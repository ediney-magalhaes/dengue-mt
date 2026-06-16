# ============================================================
# Dengue MT — Geração de Previsão por Bairro via IDW
# ============================================================
# Execução: semanal (chamado pelo pipeline_prefect.py)
# Uso: python scripts/gerar_previsao_bairros.py
#
# O que faz:
#   1. Carrega 12 modelos Direct CQR do HF Hub (ADR-030)
#   2. Carrega metadata com q_conformal por horizonte (ADR-031)
#   3. Carrega GeoJSON dos bairros e pesos IDW do HF Hub
#   4. Carrega Gold latest do HF Hub
#   5. Gera previsão municipal por horizonte:
#      - Mediana (q50) para previsão pontual
#      - Bandas calibradas (q01/q99 + q_conformal) para incerteza
#   6. Distribui previsão + bandas pelos bairros via IDW
#   7. Calcula limiares adaptativos percentílicos
#   8. Classifica nível de risco por bairro
#   9. Salva previsao_bairros_latest.geojson com bandas
#  10. Publica no HF Hub
#
# Propriedade pycnophylactic (conservação de massa):
#   Σ casos_bairro_i (município X) = previsao_municipal_X
#   Vale para mediana, lower e upper separadamente.
#
# Referências:
#   - Shepard (1968) — IDW original
#   - Taieb & Hyndman (2014) — Direct multi-step forecasting
#   - Romano, Patterson & Candès (NeurIPS 2019) — CQR
#   - ADR-030 — Direct Multi-Step + CQR em produção
#   - ADR-031 — Calibração conformal das bandas
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

# Horizontes alinhados com config.py (ADR-030)
HORIZONTES = [1, 2, 4, 8]

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


def carregar_modelos_direct() -> tuple:
    """
    Carrega 12 modelos Direct CQR + metadata do HF Hub.

    Retorna:
        modelos: dict {(h, q_str): modelo_lgbm}
        metadata: dict com q_conformal por horizonte
    """
    import joblib
    print('Carregando modelos Direct CQR do HF Hub...')

    # Metadata com calibração conformal
    path_meta = carregar_do_hf('models/direct_cqr_metadata.json')
    with open(path_meta, encoding='utf-8') as f:
        metadata = json.load(f)

    # 12 modelos: 4 horizontes × 3 quantis
    quantis = metadata['quantis']  # [0.01, 0.50, 0.99]
    modelos = {}
    for h in HORIZONTES:
        for q in quantis:
            q_str = str(int(q * 100)).zfill(2)
            nome_hf = f'models/lgbm_h{h}_q{q_str}_latest.pkl'
            path = carregar_do_hf(nome_hf)
            modelos[(h, q_str)] = joblib.load(path)

    print(f'  Modelos carregados: {len(modelos)} (4 horizontes × 3 quantis)')
    print(f'  Calibração conformal:')
    for h in HORIZONTES:
        cal = metadata['modelos'].get(f'h{h}_calibracao', {})
        print(f'    h={h}: q_conf={cal.get("q_conformal", "N/A")} '
              f'→ cobertura={cal.get("cobertura_calibrada", "N/A")}')

    return modelos, metadata


# ── Previsão municipal ────────────────────────────────────

def gerar_previsao_municipal(modelos: dict, metadata: dict) -> list[dict]:
    """
    Gera previsão municipal por horizonte via modelos Direct CQR.

    Para cada município e horizonte:
      - q50 → previsão pontual (mediana)
      - q01 - q_conformal → lower bound calibrado
      - q99 + q_conformal → upper bound calibrado

    Aplica expm1() para reverter log1p (ADR-024).
    """
    print('Carregando Gold do HF Hub...')
    path_gold = carregar_do_hf('gold/dataset_features_latest.parquet')
    df_gold   = pd.read_parquet(path_gold)
    df_gold['data_se'] = pd.to_datetime(df_gold['data_se'])
    df_gold = df_gold.sort_values('data_se')

    # Feature names do primeiro modelo (todos compartilham o mesmo schema)
    modelo_ref = modelos[(HORIZONTES[0], '50')]
    feature_cols = [c for c in modelo_ref.feature_name_ if c in df_gold.columns]

    previsoes = []
    for mun_id, info in MUNICIPIOS.items():
        df_mun      = df_gold[df_gold['municipio_id'] == mun_id]
        ultima_linha = df_mun[feature_cols].iloc[[-1]]
        ultima_data  = df_mun['data_se'].max()

        for h in HORIZONTES:
            data_prev = ultima_data + timedelta(weeks=h)

            # Previsão pontual (mediana)
            pred_q50 = max(float(np.expm1(
                modelos[(h, '50')].predict(ultima_linha)[0]
            )), 0)

            # Bandas brutas — quantis do metadata (dinâmico)
            q_lo_str = str(int(metadata['quantis'][0] * 100)).zfill(2)
            q_hi_str = str(int(metadata['quantis'][2] * 100)).zfill(2)

            pred_lo = max(float(np.expm1(
                modelos[(h, q_lo_str)].predict(ultima_linha)[0]
            )), 0)
            pred_hi = max(float(np.expm1(
                modelos[(h, q_hi_str)].predict(ultima_linha)[0]
            )), 0)

            # Calibração conformal (ADR-031)
            cal = metadata['modelos'].get(f'h{h}_calibracao', {})
            q_conf = cal.get('q_conformal', 0.0)

            lower = max(pred_lo - q_conf, 0)
            upper = pred_hi + q_conf

            # Segurança: upper nunca abaixo da mediana
            upper = max(upper, pred_q50)

            previsoes.append({
                'municipio_id':    mun_id,
                'cd_mun':          info['cd_mun'],
                'nome_municipio':  info['nome'],
                'horizonte_se':    h,
                'data_se':         data_prev.strftime('%Y-%m-%d'),
                'casos_municipio': round(pred_q50, 1),
                'lower_municipio': round(lower, 1),
                'upper_municipio': round(upper, 1),
            })

        print(f'  {info["nome"]}:')
        for h in HORIZONTES:
            p = next(p for p in previsoes
                     if p['municipio_id'] == mun_id and p['horizonte_se'] == h)
            print(f'    SE+{h}: {p["casos_municipio"]:.0f} '
                  f'[{p["lower_municipio"]:.0f}–{p["upper_municipio"]:.0f}]')

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
                     fracao: dict) -> gpd.GeoDataFrame:
    """
    Distribui previsão municipal pelos bairros via fração IDW.

    Propaga 3 valores por horizonte: mediana, lower, upper.
    Propriedade pycnophylactic vale para cada um separadamente:
      Σ casos_bairro = casos_municipio
      Σ lower_bairro = lower_municipio
      Σ upper_bairro = upper_municipio
    """
    print('Distribuindo previsão pelos bairros via IDW...')

    idx_prev = {}
    for p in previsoes_municipais:
        key = (p['cd_mun'], p['horizonte_se'])
        idx_prev[key] = {
            'casos':  p['casos_municipio'],
            'lower':  p['lower_municipio'],
            'upper':  p['upper_municipio'],
        }

    registros = []
    for _, bairro in gdf_bairros.iterrows():
        cd_bairro = bairro['CD_BAIRRO']
        cd_mun    = bairro['CD_MUN']
        f         = fracao[cd_bairro]

        row = {
            'CD_BAIRRO': cd_bairro,
            'NM_BAIRRO': bairro['NM_BAIRRO'],
            'CD_MUN':    cd_mun,
            'NM_MUN':    bairro['NM_MUN'],
            'geometry':  bairro['geometry'],
        }

        for h in HORIZONTES:
            vals = idx_prev.get((cd_mun, h), {'casos': 0, 'lower': 0, 'upper': 0})
            row[f'casos_se{h}'] = round(vals['casos'] * f, 2)
            row[f'lower_se{h}'] = round(vals['lower'] * f, 2)
            row[f'upper_se{h}'] = round(vals['upper'] * f, 2)

        registros.append(row)

    gdf = gpd.GeoDataFrame(registros, crs='EPSG:4326')
    print(f'  Distribuição concluída: {len(gdf)} bairros × {len(HORIZONTES)} horizontes')
    return gdf


# ── Limiares adaptativos ─────────────────────────────────

def calcular_limiares(gdf: gpd.GeoDataFrame) -> dict:
    """
    Calcula limiares adaptativos por percentis da distribuição
    IDW de cada município (baseado em SE+1).

    Referência: CDC/OPAS (2024) — epidemic alert thresholds
    via negative binomial percentiles (P60, P75, P85, P95).
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
                           limiares: dict) -> gpd.GeoDataFrame:
    """
    Aplica classificação de risco a todos os bairros usando
    limiares adaptativos do município correspondente.
    """
    print('Classificando risco por bairro...')
    gdf = gdf.copy()

    for idx, row in gdf.iterrows():
        lim = limiares[row['CD_MUN']]
        for h in HORIZONTES:
            nivel = classificar_risco(row[f'casos_se{h}'], lim)
            gdf.at[idx, f'nivel_risco_se{h}'] = nivel
            gdf.at[idx, f'cor_se{h}']         = CORES_RISCO[nivel]

    dist = gdf['nivel_risco_se1'].value_counts().to_dict()
    print(f'  SE+1: {dist}')

    return gdf


# ── Main ──────────────────────────────────────────────────

def main():
    print(f'\n{"="*55}')
    print('Geração Previsão por Bairro — Direct CQR + IDW')
    print(f'{"="*55}\n')

    # 1. Carrega modelos Direct CQR
    modelos, metadata = carregar_modelos_direct()

    # 2. Carrega dados espaciais
    pesos       = carregar_pesos_idw()
    gdf_bairros = carregar_bairros()

    # 3. Previsão municipal por horizonte com bandas
    previsoes_municipais = gerar_previsao_municipal(modelos, metadata)

    # 4. Calcula frações IDW
    fracao = calcular_fracoes_idw(gdf_bairros, pesos)

    # 5. Distribui casos + bandas pelos bairros
    gdf = distribuir_casos(previsoes_municipais, gdf_bairros, fracao)

    # 6. Calcula limiares adaptativos
    limiares = calcular_limiares(gdf)

    # 7. Aplica classificação de risco
    gdf = aplicar_classificacao(gdf, limiares)

    # 8. Salva GeoJSON com metadados
    ext_dir  = ROOT_DIR / 'data' / 'external'
    ext_dir.mkdir(parents=True, exist_ok=True)
    path_out = ext_dir / 'previsao_bairros_latest.geojson'
    gdf.to_file(path_out, driver='GeoJSON')

    # Injeta metadados no GeoJSON
    with open(path_out, encoding='utf-8') as f:
        geojson = json.load(f)

    geojson['limiares_risco'] = limiares
    geojson['gerado_em']      = datetime.now().isoformat()
    geojson['modelo']         = 'Direct CQR v1 (ADR-030)'
    geojson['metodo']         = 'IDW mass-preserving — Shepard 1968'
    geojson['horizontes']     = HORIZONTES
    geojson['bandas']         = 'CQR 90% calibrada (Romano et al. 2019)'
    geojson['n_bairros']      = len(gdf)

    with open(path_out, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False)

    print(f'\n  GeoJSON salvo: {path_out.name}')
    print(f'  Bairros: {len(gdf)} | Horizontes: {HORIZONTES}')
    print(f'  Bandas CQR 90% calibradas incluídas')

    # 9. Publica no HF Hub — latest + snapshot datado
    data_run = datetime.now().strftime('%Y-%m-%d')
    print('\nPublicando no HF Hub...')
    publicar_hf(path_out, 'external/previsao_bairros_latest.geojson')
    publicar_hf(path_out, f'external/snapshots/previsao_bairros_{data_run}.geojson')
    print(f'  Snapshot datado: previsao_bairros_{data_run}.geojson')

    # Resumo
    print(f'\n{"="*55}')
    print('Previsão por bairro concluída!')
    for p in previsoes_municipais:
        if p['horizonte_se'] == 1:
            print(f"  {p['nome_municipio']} SE+1: "
                  f"{p['casos_municipio']:.0f} "
                  f"[{p['lower_municipio']:.0f}–{p['upper_municipio']:.0f}]")
    for cd_mun, lim in limiares.items():
        nome = next(v['nome'] for v in MUNICIPIOS.values()
                    if v['cd_mun'] == cd_mun)
        print(f'  {nome} limiares: {lim}')
    print(f'{"="*55}\n')


if __name__ == '__main__':
    main()