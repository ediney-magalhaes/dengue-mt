"""
baixar_ibge.py
--------------
Dados socioeconômicos IBGE para Cuiabá e Várzea Grande.

Fonte atual: Censo Demográfico 2022 (dados estáticos municipais)
Fonte futura (Fase 2): Censo por setor censitário + PNAD Contínua trimestral

Nota metodológica:
    Variáveis censitárias são estáticas — mesmo valor para todo o período 2018–2024.
    Úteis como contexto municipal agora; tornam-se features dinâmicas na predição
    por bairro (Fase 2), quando combinadas com dados de setor censitário.

Como usar:
    python src/baixar_ibge.py
"""

import pandas as pd
from pathlib import Path

SAIDA = Path('data/external/ibge_censo2022_cuiaba_vg.csv')


def gerar_ibge() -> pd.DataFrame:
    # Censo Demográfico 2022 — IBGE
    # https://censo2022.ibge.gov.br/panorama/
    df = pd.DataFrame({
        'municipio': ['Cuiabá', 'Várzea Grande'],
        'cod_municipio': ['510340', '510790'],
        'populacao_2022': [654820, 285588],
        'area_km2': [3538.17, 946.94],
        'densidade_hab_km2': [185.08, 301.59],
        'domicilios_total': [238847, 99438],
        'domicilios_com_esgoto_pct': [72.4, 58.3],
        'domicilios_com_agua_pct': [94.1, 91.8],
        'domicilios_com_lixo_pct': [96.2, 93.7],
    })
    return df


if __name__ == '__main__':
    df = gerar_ibge()
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SAIDA, index=False)
    print(f"Salvo: {SAIDA}")
    print(df.to_string(index=False))
    print("""
📋 PRÓXIMOS PASSOS — IBGE Fase 2:
    - Dados por setor censitário (shapefile) para predição por bairro
    - PNAD Contínua trimestral — saneamento e renda com variação temporal
    """)