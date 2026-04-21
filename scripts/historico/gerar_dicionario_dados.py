# ============================================================
# Dengue MT — Gerador de Dicionário de Dados
# ============================================================
# Gera data_dictionary.md e data_dictionary.csv
# Fontes: feature_schema.json + dataset Gold + validacao.py
# ============================================================

import json
import pandas as pd
from pathlib import Path

ROOT_DIR    = Path(__file__).parent.parent
MODELS_DIR  = ROOT_DIR / 'models'
DATA_DIR    = ROOT_DIR / 'data'
REPORTS_DIR = ROOT_DIR / 'reports'

# ============================================================
# Dicionário manual das features — descrição, fonte, etc.
# ============================================================
FEATURES_META = {
    # ── Clima INMET ──────────────────────────────────────────
    'temp_media':          {'descricao': 'Temperatura média diária',           'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'interpolação linear',  'unidade': '°C',    'intervalo': '[10, 45]'},
    'temp_max':            {'descricao': 'Temperatura máxima diária',          'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'interpolação linear',  'unidade': '°C',    'intervalo': '[15, 50]'},
    'temp_min':            {'descricao': 'Temperatura mínima diária',          'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'interpolação linear',  'unidade': '°C',    'intervalo': '[5, 40]'},
    'precipitacao_total':  {'descricao': 'Precipitação total diária',          'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'zero (sem chuva)',     'unidade': 'mm',    'intervalo': '[0, 200]'},
    'umidade_media':       {'descricao': 'Umidade relativa média diária',      'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'interpolação linear',  'unidade': '%',     'intervalo': '[10, 100]'},
    'umidade_max':         {'descricao': 'Umidade relativa máxima diária',     'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'interpolação linear',  'unidade': '%',     'intervalo': '[10, 100]'},
    'umidade_min':         {'descricao': 'Umidade relativa mínima diária',     'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'interpolação linear',  'unidade': '%',     'intervalo': '[10, 100]'},
    'amplitude_termica':   {'descricao': 'Amplitude térmica diária (max-min)', 'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'calculado',            'unidade': '°C',    'intervalo': '[0, 30]'},
    'dias_sem_chuva':      {'descricao': 'Dias consecutivos sem precipitação', 'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'calculado',            'unidade': 'dias',  'intervalo': '[0, 365]'},

    # ── Radiação NASA POWER ──────────────────────────────────
    'radiacao_mj':         {'descricao': 'Radiação solar superficial diária',  'fonte': 'NASA POWER API', 'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'interpolação linear',  'unidade': 'MJ/m²', 'intervalo': '[0, 35]'},

    # ── NDVI/NDWI/NDBI — GEE ────────────────────────────────
    'ndvi':                {'descricao': 'Índice de vegetação (Sentinel-2+MODIS blend)', 'fonte': 'GEE Sentinel-2/MODIS', 'frequencia': 'mensal', 'lag_dias': 0,  'imputacao': 'média sazonal',        'unidade': '[-1,1]', 'intervalo': '[-1, 1]'},
    'ndwi':                {'descricao': 'Índice de água (Sentinel-2+MODIS blend)',      'fonte': 'GEE Sentinel-2/MODIS', 'frequencia': 'mensal', 'lag_dias': 0,  'imputacao': 'média sazonal',        'unidade': '[-1,1]', 'intervalo': '[-1, 1]'},
    'ndbi_gee':            {'descricao': 'Índice de urbanização (Sentinel-2)',           'fonte': 'GEE Sentinel-2',       'frequencia': 'mensal', 'lag_dias': 0,  'imputacao': 'interpolação linear',  'unidade': '[-1,1]', 'intervalo': '[-1, 1]'},

    # ── ONI Index ────────────────────────────────────────────
    'oni_index':           {'descricao': 'Índice Oceânico El Niño (ENSO)',      'fonte': 'NOAA ONI',       'frequencia': 'mensal',  'lag_dias': 0,  'imputacao': 'forward fill',         'unidade': '°C',    'intervalo': '[-3, 3]'},
    'fase_enso_num':       {'descricao': 'Fase ENSO codificada numericamente',  'fonte': 'NOAA ONI',       'frequencia': 'mensal',  'lag_dias': 0,  'imputacao': 'forward fill',         'unidade': '{-1,0,1}', 'intervalo': '[-1, 1]'},

    # ── Google Trends ────────────────────────────────────────
    'trends_lag_7d':       {'descricao': 'Interesse "dengue" Google Trends lag 7d',  'fonte': 'Google Trends', 'frequencia': 'semanal', 'lag_dias': 7,  'imputacao': 'forward fill', 'unidade': '[0,100]', 'intervalo': '[0, 100]'},
    'trends_lag_14d':      {'descricao': 'Interesse "dengue" Google Trends lag 14d', 'fonte': 'Google Trends', 'frequencia': 'semanal', 'lag_dias': 14, 'imputacao': 'forward fill', 'unidade': '[0,100]', 'intervalo': '[0, 100]'},
    'trends_lag_21d':      {'descricao': 'Interesse "dengue" Google Trends lag 21d', 'fonte': 'Google Trends', 'frequencia': 'semanal', 'lag_dias': 21, 'imputacao': 'forward fill', 'unidade': '[0,100]', 'intervalo': '[0, 100]'},

    # ── Lags de casos ────────────────────────────────────────
    'casos_lag_7d':        {'descricao': 'Casos confirmados lag 7 dias',       'fonte': 'SINAN/DATASUS',  'frequencia': 'diário',  'lag_dias': 7,  'imputacao': 'zero',                 'unidade': 'casos', 'intervalo': '[0, 1000]'},
    'casos_lag_14d':       {'descricao': 'Casos confirmados lag 14 dias',      'fonte': 'SINAN/DATASUS',  'frequencia': 'diário',  'lag_dias': 14, 'imputacao': 'zero',                 'unidade': 'casos', 'intervalo': '[0, 1000]'},
    'casos_lag_21d':       {'descricao': 'Casos confirmados lag 21 dias',      'fonte': 'SINAN/DATASUS',  'frequencia': 'diário',  'lag_dias': 21, 'imputacao': 'zero',                 'unidade': 'casos', 'intervalo': '[0, 1000]'},
    'casos_lag_28d':       {'descricao': 'Casos confirmados lag 28 dias',      'fonte': 'SINAN/DATASUS',  'frequencia': 'diário',  'lag_dias': 28, 'imputacao': 'zero',                 'unidade': 'casos', 'intervalo': '[0, 1000]'},

    # ── Médias móveis de casos ───────────────────────────────
    'casos_mm_7d':         {'descricao': 'Média móvel casos 7 dias',           'fonte': 'SINAN/DATASUS',  'frequencia': 'diário',  'lag_dias': 7,  'imputacao': 'zero',                 'unidade': 'casos', 'intervalo': '[0, 1000]'},
    'casos_mm_14d':        {'descricao': 'Média móvel casos 14 dias',          'fonte': 'SINAN/DATASUS',  'frequencia': 'diário',  'lag_dias': 14, 'imputacao': 'zero',                 'unidade': 'casos', 'intervalo': '[0, 1000]'},
    'casos_mm_28d':        {'descricao': 'Média móvel casos 28 dias',          'fonte': 'SINAN/DATASUS',  'frequencia': 'diário',  'lag_dias': 28, 'imputacao': 'zero',                 'unidade': 'casos', 'intervalo': '[0, 1000]'},
    'casos_acum_ano':      {'descricao': 'Casos acumulados no ano corrente',   'fonte': 'SINAN/DATASUS',  'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'calculado',            'unidade': 'casos', 'intervalo': '[0, 50000]'},

    # ── Sazonalidade ─────────────────────────────────────────
    'ano':                 {'descricao': 'Ano calendário',                      'fonte': 'calendário',     'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'N/A',                  'unidade': 'ano',   'intervalo': '[2018, 2030]'},
    'mes':                 {'descricao': 'Mês calendário (1-12)',               'fonte': 'calendário',     'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'N/A',                  'unidade': 'mês',   'intervalo': '[1, 12]'},
    'semana_ano':          {'descricao': 'Semana epidemiológica (1-53)',        'fonte': 'calendário',     'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'N/A',                  'unidade': 'semana','intervalo': '[1, 53]'},
    'dia_ano':             {'descricao': 'Dia do ano (1-366)',                  'fonte': 'calendário',     'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'N/A',                  'unidade': 'dia',   'intervalo': '[1, 366]'},
    'trimestre':           {'descricao': 'Trimestre do ano (1-4)',              'fonte': 'calendário',     'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'N/A',                  'unidade': 'trim',  'intervalo': '[1, 4]'},
    'mes_seno':            {'descricao': 'Codificação cíclica seno do mês',    'fonte': 'calendário',     'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'calculado',            'unidade': '[-1,1]','intervalo': '[-1, 1]'},
    'mes_cosseno':         {'descricao': 'Codificação cíclica cosseno do mês', 'fonte': 'calendário',     'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'calculado',            'unidade': '[-1,1]','intervalo': '[-1, 1]'},
    'semana_seno':         {'descricao': 'Codificação cíclica seno da semana', 'fonte': 'calendário',     'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'calculado',            'unidade': '[-1,1]','intervalo': '[-1, 1]'},
    'semana_cosseno':      {'descricao': 'Codificação cíclica cosseno da semana','fonte': 'calendário',   'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'calculado',            'unidade': '[-1,1]','intervalo': '[-1, 1]'},

    # ── Ciclo epidêmico ──────────────────────────────────────
    'anos_desde_pico':     {'descricao': 'Anos desde o último pico epidêmico', 'fonte': 'SINAN/DATASUS',  'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'calculado',            'unidade': 'anos',  'intervalo': '[0, 10]'},
    'ciclo_epidemico':     {'descricao': 'Indicador de ano de pico (0/1)',      'fonte': 'SINAN/DATASUS',  'frequencia': 'diário',  'lag_dias': 0,  'imputacao': 'calculado',            'unidade': '{0,1}', 'intervalo': '[0, 1]'},

    # ── Lags climáticos ──────────────────────────────────────
    'precip_lag_28d':      {'descricao': 'Precipitação total lag 28 dias',     'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 28, 'imputacao': 'zero',                 'unidade': 'mm',    'intervalo': '[0, 200]'},
    'precip_lag_35d':      {'descricao': 'Precipitação total lag 35 dias',     'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 35, 'imputacao': 'zero',                 'unidade': 'mm',    'intervalo': '[0, 200]'},
    'precip_lag_42d':      {'descricao': 'Precipitação total lag 42 dias',     'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 42, 'imputacao': 'zero',                 'unidade': 'mm',    'intervalo': '[0, 200]'},
    'umidade_lag_28d':     {'descricao': 'Umidade relativa média lag 28 dias', 'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 28, 'imputacao': 'interpolação linear',  'unidade': '%',     'intervalo': '[10, 100]'},
    'umidade_lag_35d':     {'descricao': 'Umidade relativa média lag 35 dias', 'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 35, 'imputacao': 'interpolação linear',  'unidade': '%',     'intervalo': '[10, 100]'},
    'umidade_lag_42d':     {'descricao': 'Umidade relativa média lag 42 dias', 'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 42, 'imputacao': 'interpolação linear',  'unidade': '%',     'intervalo': '[10, 100]'},
    'temp_lag_28d':        {'descricao': 'Temperatura média lag 28 dias',      'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 28, 'imputacao': 'interpolação linear',  'unidade': '°C',    'intervalo': '[10, 45]'},
    'temp_lag_35d':        {'descricao': 'Temperatura média lag 35 dias',      'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 35, 'imputacao': 'interpolação linear',  'unidade': '°C',    'intervalo': '[10, 45]'},
    'temp_lag_42d':        {'descricao': 'Temperatura média lag 42 dias',      'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 42, 'imputacao': 'interpolação linear',  'unidade': '°C',    'intervalo': '[10, 45]'},
    'radiacao_lag_28d':    {'descricao': 'Radiação solar lag 28 dias',         'fonte': 'NASA POWER API', 'frequencia': 'diário',  'lag_dias': 28, 'imputacao': 'interpolação linear',  'unidade': 'MJ/m²', 'intervalo': '[0, 35]'},

    # ── Médias móveis climáticas ─────────────────────────────
    'precip_mm_7d':        {'descricao': 'Média móvel precipitação 7 dias',    'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 7,  'imputacao': 'zero',                 'unidade': 'mm',    'intervalo': '[0, 200]'},
    'precip_mm_14d':       {'descricao': 'Média móvel precipitação 14 dias',   'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 14, 'imputacao': 'zero',                 'unidade': 'mm',    'intervalo': '[0, 200]'},
    'precip_mm_28d':       {'descricao': 'Média móvel precipitação 28 dias',   'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 28, 'imputacao': 'zero',                 'unidade': 'mm',    'intervalo': '[0, 200]'},
    'umidade_mm_7d':       {'descricao': 'Média móvel umidade 7 dias',         'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 7,  'imputacao': 'interpolação linear',  'unidade': '%',     'intervalo': '[10, 100]'},
    'umidade_mm_14d':      {'descricao': 'Média móvel umidade 14 dias',        'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 14, 'imputacao': 'interpolação linear',  'unidade': '%',     'intervalo': '[10, 100]'},
    'umidade_mm_28d':      {'descricao': 'Média móvel umidade 28 dias',        'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 28, 'imputacao': 'interpolação linear',  'unidade': '%',     'intervalo': '[10, 100]'},
    'radiacao_mm_14d':     {'descricao': 'Média móvel radiação 14 dias',       'fonte': 'NASA POWER API', 'frequencia': 'diário',  'lag_dias': 14, 'imputacao': 'interpolação linear',  'unidade': 'MJ/m²', 'intervalo': '[0, 35]'},

    # ── Acumulados ───────────────────────────────────────────
    'precip_acum_7d':      {'descricao': 'Precipitação acumulada 7 dias',      'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 7,  'imputacao': 'zero',                 'unidade': 'mm',    'intervalo': '[0, 500]'},
    'precip_acum_14d':     {'descricao': 'Precipitação acumulada 14 dias',     'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 14, 'imputacao': 'zero',                 'unidade': 'mm',    'intervalo': '[0, 800]'},
    'precip_acum_28d':     {'descricao': 'Precipitação acumulada 28 dias',     'fonte': 'INMET A901',     'frequencia': 'diário',  'lag_dias': 28, 'imputacao': 'zero',                 'unidade': 'mm',    'intervalo': '[0, 1500]'},

    # ── NDBI lags ────────────────────────────────────────────
    'ndbi_lag_30d':        {'descricao': 'Índice de urbanização lag 30 dias',  'fonte': 'GEE Sentinel-2', 'frequencia': 'mensal',  'lag_dias': 30, 'imputacao': 'interpolação linear',  'unidade': '[-1,1]','intervalo': '[-1, 1]'},
    'ndbi_lag_60d':        {'descricao': 'Índice de urbanização lag 60 dias',  'fonte': 'GEE Sentinel-2', 'frequencia': 'mensal',  'lag_dias': 60, 'imputacao': 'interpolação linear',  'unidade': '[-1,1]','intervalo': '[-1, 1]'},
}

# Features que NÃO entram no modelo (target + identificadores)
NAO_MODELO = {
    'casos':               {'descricao': 'Casos confirmados de dengue (TARGET)', 'fonte': 'SINAN/DATASUS', 'frequencia': 'diário', 'lag_dias': 0, 'imputacao': 'N/A', 'unidade': 'casos', 'intervalo': '[0, 1000]', 'no_modelo': 'não', 'motivo': 'variável alvo (target)'},
    'casos_nowcast':       {'descricao': 'Casos corrigidos pelo fator nowcasting', 'fonte': 'SINAN/DATASUS', 'frequencia': 'diário', 'lag_dias': 0, 'imputacao': 'calculado', 'unidade': 'casos', 'intervalo': '[0, 3000]', 'no_modelo': 'não', 'motivo': 'derivado do target'},
    'municipio_id':        {'descricao': 'Identificador do município', 'fonte': 'IBGE', 'frequencia': 'estático', 'lag_dias': 0, 'imputacao': 'N/A', 'unidade': 'código', 'intervalo': 'N/A', 'no_modelo': 'não', 'motivo': 'identificador — sem valor preditivo'},
    'fator_nowcasting':    {'descricao': 'Fator de correção subnotificação SINAN', 'fonte': 'SINAN/DATASUS', 'frequencia': 'semanal', 'lag_dias': 0, 'imputacao': 'média histórica', 'unidade': 'fator', 'intervalo': '[1, 3]', 'no_modelo': 'não', 'motivo': 'usado para corrigir target, não como feature'},
    'casos_por_100k':      {'descricao': 'Incidência por 100k habitantes', 'fonte': 'SINAN/IBGE', 'frequencia': 'diário', 'lag_dias': 0, 'imputacao': 'calculado', 'unidade': 'casos/100k', 'intervalo': '[0, 500]', 'no_modelo': 'não', 'motivo': 'derivado do target'},
    'casos_nowcast_por_100k': {'descricao': 'Incidência nowcast por 100k', 'fonte': 'SINAN/IBGE', 'frequencia': 'diário', 'lag_dias': 0, 'imputacao': 'calculado', 'unidade': 'casos/100k', 'intervalo': '[0, 1500]', 'no_modelo': 'não', 'motivo': 'derivado do target nowcast'},
}


def gerar_dicionario():
    """Gera data_dictionary.md e data_dictionary.csv."""

    # Carregar schema
    schema_path = MODELS_DIR / 'lgbm_v4_feature_schema.json'
    with open(schema_path) as f:
        schema = json.load(f)
    features_modelo = set(schema['feature_names'])

    # Montar DataFrame
    rows = []

    # Features do modelo
    for feat, meta in FEATURES_META.items():
        rows.append({
            'feature':      feat,
            'descricao':    meta['descricao'],
            'fonte':        meta['fonte'],
            'frequencia':   meta['frequencia'],
            'lag_dias':     meta['lag_dias'],
            'imputacao':    meta['imputacao'],
            'unidade':      meta['unidade'],
            'intervalo':    meta['intervalo'],
            'no_modelo':    'sim' if feat in features_modelo else 'não',
            'motivo':       'feature preditiva selecionada' if feat in features_modelo else 'não selecionada',
        })

    # Features fora do modelo
    for feat, meta in NAO_MODELO.items():
        rows.append({
            'feature':      feat,
            'descricao':    meta['descricao'],
            'fonte':        meta['fonte'],
            'frequencia':   meta['frequencia'],
            'lag_dias':     meta['lag_dias'],
            'imputacao':    meta['imputacao'],
            'unidade':      meta['unidade'],
            'intervalo':    meta['intervalo'],
            'no_modelo':    meta['no_modelo'],
            'motivo':       meta['motivo'],
        })

    df = pd.DataFrame(rows)

    # ── Gerar CSV ────────────────────────────────────────────
    csv_path = REPORTS_DIR / 'data_dictionary.csv'
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"CSV gerado: {csv_path}")

    # ── Gerar Markdown ───────────────────────────────────────
    md_lines = [
        "# Dicionário de Dados — Dengue MT",
        "",
        "> Documento gerado automaticamente a partir do Feature Schema e metadados do pipeline.",
        f"> Dataset: `gold/dataset_features_v4.parquet` — {len(features_modelo)} features no modelo",
        "",
        "---",
        "",
    ]

    # Agrupar por fonte
    for fonte in df['fonte'].unique():
        df_fonte = df[df['fonte'] == fonte].sort_values('feature')
        md_lines.append(f"## {fonte}")
        md_lines.append("")
        md_lines.append("| Feature | Descrição | Frequência | Lag (dias) | Unidade | Intervalo válido | Imputação | No modelo |")
        md_lines.append("|---|---|---|---|---|---|---|---|")
        for _, row in df_fonte.iterrows():
            no_modelo = "✅ sim" if row['no_modelo'] == 'sim' else "❌ não"
            md_lines.append(
                f"| `{row['feature']}` | {row['descricao']} | {row['frequencia']} | "
                f"{row['lag_dias']} | {row['unidade']} | {row['intervalo']} | "
                f"{row['imputacao']} | {no_modelo} |"
            )
        md_lines.append("")

    # Resumo
    n_modelo   = df[df['no_modelo'] == 'sim'].shape[0]
    n_fora     = df[df['no_modelo'] == 'não'].shape[0]
    n_total    = len(df)
    md_lines += [
        "---",
        "",
        "## Resumo",
        "",
        f"| Item | Valor |",
        f"|---|---|",
        f"| Total de variáveis documentadas | {n_total} |",
        f"| Features no modelo | {n_modelo} |",
        f"| Variáveis fora do modelo | {n_fora} |",
        f"| Dataset version | v4 |",
        f"| Modelo | LightGBM v4 — R²=0.820 \\| MAE=17.6 \\| sMAPE=31.5% |",
        f"| Validação | TimeSeriesSplit 5 folds |",
        "",
        "---",
        "*Gerado automaticamente — Dengue MT — IFMT 2026*",
    ]

    md_path = REPORTS_DIR / 'data_dictionary.md'
    md_path.write_text('\n'.join(md_lines), encoding='utf-8')
    print(f"Markdown gerado: {md_path}")
    print(f"\nResumo: {n_total} variáveis | {n_modelo} no modelo | {n_fora} fora")


if __name__ == '__main__':
    gerar_dicionario()