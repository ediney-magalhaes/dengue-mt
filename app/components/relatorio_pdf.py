# ============================================================
# Dengue MT — Relatório PDF para Gestores v1.1
# ============================================================
# Gera boletim epidemiológico semanal em PDF com:
#   - KPIs de previsão por município
#   - Distribuição de risco por bairro
#   - Top 10 bairros em risco
#   - Situação atual determinística (sem LLM)
#   - Recomendações operacionais via LLM (Groq/LLaMA 3.3)
# Referências:
#   - EpiPlanAgent (arxiv 2512.10313, 2025)
#   - PandemicLLM (Du et al., 2025)
# ============================================================

import os
import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY


# ── Cores institucionais ──────────────────────────────────────
COR_PRIMARIA   = colors.HexColor('#1a5276')
COR_SECUNDARIA = colors.HexColor('#c0392b')
COR_ALERTA     = colors.HexColor('#e67e22')
COR_OK         = colors.HexColor('#27ae60')
COR_CINZA      = colors.HexColor('#f2f3f4')

CORES_NIVEL = {
    'Muito Alto':  colors.HexColor('#c0392b'),
    'Alto':        colors.HexColor('#e67e22'),
    'Moderado':    colors.HexColor('#f1c40f'),
    'Baixo':       colors.HexColor('#2980b9'),
    'Muito Baixo': colors.HexColor('#1a5276'),
}

MUNICIPIOS = {'5103403': 'Cuiabá', '5108402': 'Várzea Grande'}


# ── Recomendações via Groq/LLaMA ──────────────────────────────
def gerar_recomendacoes_llm(dados_resumo: dict) -> str:
    """
    Gera APENAS as recomendações operacionais via Groq/LLaMA 3.3.
    A seção descritiva é gerada deterministicamente pelo código.
    Referências: EpiPlanAgent (2025), PandemicLLM (Du et al., 2025).
    """
    try:
        from groq import Groq
        client = Groq(api_key=os.getenv('GROQ_API_KEY'))

        prompt = f"""Você é um técnico de vigilância epidemiológica da Secretaria Municipal de Saúde com 15 anos de experiência em campo.

Sua tarefa é escrever APENAS as recomendações operacionais para os gestores municipais com base nos dados abaixo.

CONTEXTO:
- Municípios: {dados_resumo['municipios']}
- Semana: {dados_resumo['data']}
- Tendência calculada pelo sistema: {dados_resumo['tendencia_explicada']}

TOP 5 BAIRROS MAIS CRÍTICOS (SE+{dados_resumo['horizonte']}):
{dados_resumo['top_bairros']}

DISTRIBUIÇÃO DE RISCO:
{dados_resumo['distribuicao_risco']}

REGRAS:
- Escreva exatamente 4 recomendações em parágrafos separados por linha em branco
- Cada recomendação deve ter: O QUE fazer + ONDE (cite o bairro pelo nome) + POR QUÊ em linguagem simples
- PROIBIDO usar jargão sem explicar: se usar "larvicida", explique que é um produto que mata larvas do mosquito na água
- Escreva para um secretário de saúde que não é da área técnica
- Sem títulos, sem numeração, sem asteriscos, sem markdown
- Seja direto e prático — o gestor precisa saber o que fazer amanhã cedo

Escreva apenas as 4 recomendações, nada mais."""

        resp = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=600,
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()

    except Exception as e:
        return (
            f"Não foi possível gerar as recomendações automáticas nesta sessão "
            f"(erro: {str(e)}). Consulte o técnico de vigilância epidemiológica municipal."
        )


# ── Geração do PDF ────────────────────────────────────────────
def gerar_pdf_boletim(
    gdf,
    limiares: dict,
    horizonte: int,
    mun_sel: str,
    semana_ref: str,
) -> bytes:
    """
    Gera boletim epidemiológico em PDF.

    Parâmetros:
        gdf: GeoDataFrame com previsão por bairro
        limiares: dict com limiares adaptativos por município
        horizonte: int (1, 2, 4 ou 8)
        mun_sel: 'Todos', 'Cuiabá' ou 'Várzea Grande'
        semana_ref: string da semana ('Semana atual' ou 'YYYY-MM-DD')

    Retorna bytes do PDF para st.download_button.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        'Titulo', parent=styles['Title'],
        fontSize=16, textColor=COR_PRIMARIA,
        spaceAfter=4, alignment=TA_CENTER,
    )
    estilo_subtitulo = ParagraphStyle(
        'Subtitulo', parent=styles['Normal'],
        fontSize=10, textColor=colors.grey,
        spaceAfter=2, alignment=TA_CENTER,
    )
    estilo_secao = ParagraphStyle(
        'Secao', parent=styles['Heading2'],
        fontSize=12, textColor=COR_PRIMARIA,
        spaceBefore=12, spaceAfter=4,
    )
    estilo_corpo = ParagraphStyle(
        'Corpo', parent=styles['Normal'],
        fontSize=9, leading=14,
        spaceAfter=6, alignment=TA_JUSTIFY,
    )
    estilo_nota = ParagraphStyle(
        'Nota', parent=styles['Normal'],
        fontSize=7, textColor=colors.grey,
        leading=10, alignment=TA_CENTER,
    )

    elementos = []
    col_casos = f'casos_se{horizonte}'
    col_nivel = f'nivel_risco_se{horizonte}'

    # ── Filtro município ──────────────────────────────────────
    if mun_sel != 'Todos':
        cd_mun = [k for k, v in MUNICIPIOS.items() if v == mun_sel]
        gdf_pdf = gdf[gdf['CD_MUN'].isin(cd_mun)].copy() if cd_mun else gdf.copy()
    else:
        gdf_pdf = gdf.copy()

    # ── Cabeçalho ─────────────────────────────────────────────
    elementos.append(Paragraph("BOLETIM EPIDEMIOLÓGICO — DENGUE MT", estilo_titulo))
    elementos.append(Paragraph(
        "Sistema Preditivo de Surtos | Cuiabá e Várzea Grande — IFMT",
        estilo_subtitulo
    ))
    data_geracao = datetime.now().strftime('%d/%m/%Y às %H:%M')
    label_semana = semana_ref if semana_ref != 'Semana atual' else 'Semana atual (latest)'
    elementos.append(Paragraph(
        f"Gerado em: {data_geracao} | Semana de referência: {label_semana} | "
        f"Horizonte: SE+{horizonte} | Município: {mun_sel}",
        estilo_nota
    ))
    elementos.append(HRFlowable(width='100%', thickness=2, color=COR_PRIMARIA, spaceAfter=8))

    # ── KPIs por município ────────────────────────────────────
    elementos.append(Paragraph("1. PREVISÃO DE CASOS", estilo_secao))

    muns_dados = []
    previsao_mun = []
    for cd, nome in MUNICIPIOS.items():
        if mun_sel != 'Todos' and nome != mun_sel:
            continue
        gdf_m = gdf[gdf['CD_MUN'] == cd]
        if gdf_m.empty:
            continue
        for h in [1, 2, 4, 8]:
            col = f'casos_se{h}'
            if col in gdf_m.columns:
                total = gdf_m[col].sum()
                lower = gdf_m[f'lower_se{h}'].sum() if f'lower_se{h}' in gdf_m.columns else 0
                upper = gdf_m[f'upper_se{h}'].sum() if f'upper_se{h}' in gdf_m.columns else 0
                previsao_mun.append(f"  {nome} SE+{h}: {total:.0f} casos")
                if h == horizonte:
                    muns_dados.append([
                        nome,
                        f"SE+{h}",
                        f"{total:.0f} casos",
                        f"[{lower:.0f} – {upper:.0f}]",
                    ])

    tabela_kpi = Table(
        [['Município', 'Horizonte', 'Previsão (mediana)', 'Intervalo CQR 90%']] + muns_dados,
        colWidths=[4.5*cm, 3*cm, 4.5*cm, 4.5*cm],
    )
    tabela_kpi.setStyle(TableStyle([
        ('BACKGROUND',     (0, 0), (-1, 0),  COR_PRIMARIA),
        ('TEXTCOLOR',      (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',       (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',       (0, 0), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COR_CINZA]),
        ('GRID',           (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('ALIGN',          (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',     (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 4),
    ]))
    elementos.append(tabela_kpi)
    elementos.append(Spacer(1, 8))

    # ── Distribuição de risco ─────────────────────────────────
    elementos.append(Paragraph("2. DISTRIBUIÇÃO DE RISCO POR BAIRROS", estilo_secao))

    dist = gdf_pdf[col_nivel].value_counts().to_dict()
    niveis = ['Muito Alto', 'Alto', 'Moderado', 'Baixo', 'Muito Baixo']
    total_bairros = len(gdf_pdf)
    dados_dist = [['Classificação', 'Nº de Bairros', '% do Total']]
    for n in niveis:
        qtd = dist.get(n, 0)
        pct = (qtd / total_bairros * 100) if total_bairros > 0 else 0
        dados_dist.append([n, str(qtd), f"{pct:.1f}%"])
    dados_dist.append(['TOTAL', str(total_bairros), '100%'])

    tabela_dist = Table(dados_dist, colWidths=[5*cm, 4*cm, 4*cm])
    style_dist = [
        ('BACKGROUND',    (0, 0),  (-1, 0),  COR_PRIMARIA),
        ('TEXTCOLOR',     (0, 0),  (-1, 0),  colors.white),
        ('FONTNAME',      (0, 0),  (-1, 0),  'Helvetica-Bold'),
        ('FONTNAME',      (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND',    (0, -1), (-1, -1), COR_CINZA),
        ('FONTSIZE',      (0, 0),  (-1, -1), 9),
        ('GRID',          (0, 0),  (-1, -1), 0.5, colors.lightgrey),
        ('ALIGN',         (1, 0),  (-1, -1), 'CENTER'),
        ('VALIGN',        (0, 0),  (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0),  (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0),  (-1, -1), 4),
    ]
    for i, n in enumerate(niveis, start=1):
        cor = CORES_NIVEL.get(n)
        if cor:
            style_dist.append(('TEXTCOLOR', (0, i), (0, i), cor))
            style_dist.append(('FONTNAME',  (0, i), (0, i), 'Helvetica-Bold'))
    tabela_dist.setStyle(TableStyle(style_dist))
    elementos.append(tabela_dist)
    elementos.append(Spacer(1, 8))

    # ── Top 10 bairros ────────────────────────────────────────
    elementos.append(Paragraph("3. TOP 10 BAIRROS — MAIOR CONCENTRAÇÃO PREVISTA", estilo_secao))

    df_top = (
        gdf_pdf[['NM_BAIRRO', 'NM_MUN', col_casos, col_nivel]]
        .sort_values(col_casos, ascending=False)
        .head(10)
    )
    dados_top = [['Bairro', 'Município', f'Casos SE+{horizonte}', 'Classificação']]
    for _, row in df_top.iterrows():
        dados_top.append([
            row['NM_BAIRRO'],
            row['NM_MUN'],
            f"{row[col_casos]:.2f}",
            row[col_nivel],
        ])

    tabela_top = Table(dados_top, colWidths=[5.5*cm, 3.5*cm, 3.5*cm, 4*cm])
    style_top = [
        ('BACKGROUND',     (0, 0), (-1, 0),  COR_PRIMARIA),
        ('TEXTCOLOR',      (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',       (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',       (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COR_CINZA]),
        ('GRID',           (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('ALIGN',          (2, 0), (3, -1),  'CENTER'),
        ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',     (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 3),
    ]
    for i, row in enumerate(df_top.itertuples(), start=1):
        cor = CORES_NIVEL.get(getattr(row, col_nivel.replace('casos_', 'nivel_risco_')), colors.black)
        style_top.append(('TEXTCOLOR', (3, i), (3, i), cor))
        style_top.append(('FONTNAME',  (3, i), (3, i), 'Helvetica-Bold'))
    tabela_top.setStyle(TableStyle(style_top))
    elementos.append(tabela_top)
    elementos.append(Spacer(1, 12))

    # ── Seção 4: Situação + Recomendações ─────────────────────
    elementos.append(HRFlowable(width='100%', thickness=1, color=COR_ALERTA, spaceAfter=6))
    elementos.append(Paragraph("4. INTERPRETAÇÃO E RECOMENDAÇÕES", estilo_secao))

    # Calcula tendência a partir dos dados (determinístico)
    soma_se1 = gdf_pdf['casos_se1'].sum() if 'casos_se1' in gdf_pdf.columns else 0
    soma_se8 = gdf_pdf['casos_se8'].sum() if 'casos_se8' in gdf_pdf.columns else 0
    variacao = ((soma_se8 - soma_se1) / max(soma_se1, 1)) * 100

    if variacao > 15:
        tendencia_explicada = (
            f"ELEVAÇÃO PREVISTA — o sistema prevê {variacao:.0f}% mais casos em 8 semanas "
            f"comparado à próxima semana ({soma_se1:.0f} → {soma_se8:.0f} casos totais). "
            "Atenção redobrada é necessária."
        )
    elif variacao < -15:
        tendencia_explicada = (
            f"QUEDA PREVISTA — o sistema prevê {abs(variacao):.0f}% menos casos em 8 semanas "
            f"comparado à próxima semana ({soma_se1:.0f} → {soma_se8:.0f} casos totais). "
            "Manter as ações para consolidar a melhora."
        )
    else:
        tendencia_explicada = (
            f"CENÁRIO ESTÁVEL — variação menor que 15% entre próxima semana e 8 semanas "
            f"({soma_se1:.0f} → {soma_se8:.0f} casos totais). "
            "Manter vigilância no patamar atual."
        )

    # Situação atual — texto determinístico (sem LLM)
    n_criticos = dist.get('Muito Alto', 0) + dist.get('Alto', 0)
    top3 = ', '.join([
        f"{row['NM_BAIRRO']} ({row['NM_MUN']})"
        for _, row in df_top.head(3).iterrows()
    ])
    texto_situacao = (
        f"Na semana de referência analisada, {n_criticos} bairros de {mun_sel} estão "
        f"classificados em situação crítica (Alto ou Muito Alto risco): "
        f"{dist.get('Muito Alto', 0)} em Muito Alto e {dist.get('Alto', 0)} em Alto. "
        f"Os bairros com maior concentração prevista de casos para SE+{horizonte} são: {top3}. "
        f"Tendência: {tendencia_explicada}"
    )
    elementos.append(Paragraph(texto_situacao, estilo_corpo))
    elementos.append(Spacer(1, 8))

    # Recomendações via LLM
    elementos.append(Paragraph("RECOMENDAÇÕES OPERACIONAIS PARA ESTA SEMANA", estilo_secao))
    elementos.append(Paragraph(
        "Geradas por IA (LLaMA 3.3 70B via Groq) — validar com o técnico de vigilância epidemiológica.",
        estilo_nota
    ))
    elementos.append(Spacer(1, 4))

    dist_texto = ' | '.join([f"{n}: {dist.get(n, 0)} bairros" for n in niveis])
    top5_texto = '\n'.join([
        f"  {i+1}. {row['NM_BAIRRO']} ({row['NM_MUN']}): {row[col_casos]:.1f} casos — {row[col_nivel]}"
        for i, (_, row) in enumerate(df_top.head(5).iterrows())
    ])

    dados_resumo = {
        'data':               datetime.now().strftime('%d/%m/%Y'),
        'municipios':         mun_sel,
        'horizonte':          horizonte,
        'previsao_municipal': '\n'.join(previsao_mun),
        'distribuicao_risco': dist_texto,
        'top_bairros':        top5_texto,
        'tendencia_explicada': tendencia_explicada,
    }

    recomendacoes = gerar_recomendacoes_llm(dados_resumo)

    for paragrafo in recomendacoes.split('\n\n'):
        paragrafo = paragrafo.strip()
        if paragrafo:
            elementos.append(Paragraph(paragrafo, estilo_corpo))
            elementos.append(Spacer(1, 4))

    # ── Rodapé metodológico ───────────────────────────────────
    elementos.append(Spacer(1, 12))
    elementos.append(HRFlowable(width='100%', thickness=1, color=colors.lightgrey, spaceAfter=4))
    elementos.append(Paragraph(
        "Metodologia: Previsão via LightGBM Direct Multi-Step CQR (4 horizontes × 3 quantis, cobertura 90% calibrada). "
        "Distribuição espacial por IDW mass-preserving (Shepard, 1968). "
        "Limiares adaptativos por percentis (P60/P75/P85/P95) recalculados semanalmente. "
        "Recomendações por LLaMA 3.3 70B (Groq) com prompt baseado em EpiPlanAgent (2025) e PandemicLLM (Du et al., 2025). "
        "Sistema desenvolvido pelo Instituto Federal de Mato Grosso (IFMT) — Projeto de Extensão 2026.",
        estilo_nota
    ))

    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()