# 📓 Diário de Bordo — Dengue MT

> Registro pessoal de progresso, decisões técnicas e aprendizados do projeto.

---

## 📅 Semana 1 — Configuração do Ambiente

### 09/03/2026

**✅ O que foi feito hoje:**
- Instalação e configuração do Miniconda (conda 26.1.1)
- Criação do ambiente isolado `dengue-mt` com Python 3.11
- Criação da estrutura de pastas do projeto no OneDrive
- Instalação das bibliotecas da Semana 1 (Pandas, NumPy, Matplotlib, Seaborn, Jupyter)
- Registro do kernel "Dengue MT" no Jupyter
- Teste do ambiente com notebook `00_teste_ambiente.ipynb` — todas as libs OK
- Configuração do repositório GitHub com branches `main` e `dev`
- Registro no Google Earth Engine (plano Comunidade — IFMT)
- Criação do README completo com contexto, arquitetura, escolhas técnicas e roadmap

**🔧 Decisões técnicas tomadas:**
- Pasta do projeto no OneDrive para backup automático — ambiente Conda fora do OneDrive para evitar conflitos de sincronização
- Adotada convenção **Conventional Commits** para versionamento (`feat:`, `docs:`, `fix:`, etc.)
- Estratégia de branches: `dev` para desenvolvimento, `main` para entregas estáveis

**💡 Aprendizados:**
- Conda requer aceitação de Terms of Service nos canais antes do primeiro uso (`conda tos accept`)
- `conda init powershell` é necessário para integração com o terminal do VSCode no Windows
- Primeira execução do Jupyter demora mais — kernel inicializa na primeira célula

**⚠️ Dificuldades encontradas:**
- Terminal do VSCode não mostrava `(dengue-mt)` após ativação — resolvido com `conda init powershell` + reinício do VSCode

**⏭️ Próximos passos (Semana 1 — continuação):**
- [x] Baixar dados SINAN/MT (2018–2024) no DATASUS ✅
- [x] Baixar dados climáticos do INMET para MT ✅
- [ ] Criar notebook `01_coleta_dados.ipynb`

---

## 📅 Semana 2 — Engenharia de Dados I

### 11/03/2026

**✅ O que foi feito hoje:**
- Retorno ao ambiente — verificação de que conda, git e branch `dev` estavam ativos e corretos
- Tentativa de instalação do `pySUS` para download dos dados SINAN — falhou por incompatibilidade do `pyreaddbc` com Windows (ausência do `unistd.h`)
- Instalação do `Microsoft C++ Build Tools` para resolver dependência de compilação
- Descoberta e instalação do `datasus-fetcher` como solução alternativa ao pySUS
- Download bem-sucedido dos dados SINAN/Dengue 2018–2024 (~624 MB) via `datasus-fetcher`
- Criação do script `src/download_sinan.py` para reprodutibilidade do pipeline
- Download bem-sucedido dos dados climáticos INMET 2018–2024 (todas estações automáticas) via script Python com header customizado
- Criação do script `src/download_inmet.py` para reprodutibilidade do pipeline
- Preenchimento completo do questionário de planejamento do projeto para o orientador

**🔧 Decisões técnicas tomadas:**
- Abandonado o `pySUS` no Windows — substituído pelo `datasus-fetcher` que não requer compilação
- Dados SINAN baixados em escala nacional (BR) — filtro por MT será aplicado no Python durante a limpeza
- Dados INMET baixados como pacote anual completo — filtro por estações do MT na Semana 2
- Scripts de download salvos em `src/` para garantir reprodutibilidade do pipeline de coleta

**💡 Aprendizados:**
- Portais do governo (DATASUS, INMET) bloqueiam downloads diretos via navegadores modernos e requisições sem `User-Agent`
- O `datasus-fetcher` é a forma mais confiável de acessar dados do DATASUS via Python no Windows
- Adicionar `User-Agent: Mozilla/5.0` nas requisições HTTP resolve bloqueios 403 em portais públicos
- Arquivos `.dbc` são o formato nativo do DATASUS — precisarão de conversão para CSV/Parquet na Semana 2

**⚠️ Dificuldades encontradas:**
- `pySUS` incompatível com Windows — requer `unistd.h` que não existe no sistema
- FTP do DATASUS e URLs do S3 bloqueados para acesso direto — resolvido com `datasus-fetcher`
- Portal INMET retornava erro 403 sem header `User-Agent` — resolvido com requisição customizada

**⏭️ Próximos passos (Semana 2):**
- [ ] Converter arquivos `.dbc` do SINAN para CSV/Parquet
- [ ] Filtrar dados por estado MT e municípios Cuiabá e Várzea Grande
- [ ] Descompactar e explorar os ZIPs do INMET — filtrar estações do MT
- [ ] Fazer merge das bases epidemiológica e climática por data
- [ ] Criar notebook `01_eda_exploratoria.ipynb` com primeiras visualizações


### 11/03/2026 — Sessão noturna

**✅ O que foi feito:**
- Início da Semana 2 — Engenharia de Dados
- Tentativa de instalação do `pyreaddbc` no Windows — falhou novamente (unistd.h)
- Estratégia alternativa: uso do Google Colab para conversão dos .dbc para Parquet
- Instalação do `pySUS` no Colab (Linux) — funcionou perfeitamente
- Conversão e filtro por MT bem-sucedidos para 2018–2023:
  - 2018: 10.131 registros
  - 2019: 17.855 registros
  - 2020: 47.631 registros
  - 2021: 34.174 registros
  - 2022: 35.341 registros
  - 2023: 28.605 registros
  - **Total parcial: 173.737 registros do MT**
- 2024 falhou por limite de RAM do Colab gratuito (arquivo de 274MB)

**🔧 Decisões técnicas:**
- Conversão .dbc → Parquet será feita via Google Colab (Linux)
- Dados nacionais são baixados e filtrados por `SG_UF_NOT == '51'` (código MT)
- 2024 será processado separadamente com leitura em chunks para economizar RAM

**⚠️ Dificuldades:**
- Colab gratuito tem limite de RAM (~12GB) — arquivo de 2024 com 274MB excedeu ao ser carregado em memória
- Solução: processar 2024 em chunks e salvar incrementalmente

**⏭️ Próximos passos:**
- [ ] Processar 2024 em chunks no Colab
- [ ] Salvar dataset consolidado MT em Parquet
- [ ] Baixar arquivo para o OneDrive
- [ ] Explorar colunas e qualidade dos dados

---

## 📅 Semana 3 — Dados Geoespaciais e Satélite
> *A preencher*

---

## 📅 Semana 4 — EDA e Feature Engineering
> *A preencher*

---

## 📅 Semana 5 — Modelo Baseline
> *A preencher*

---

## 📅 Semana 6 — Modelos Avançados
> *A preencher*

---

## 📅 Semana 7 — CNN para Imagens de Satélite
> *A preencher*

---

## 📅 Semana 8 — Ensemble e Validação Final
> *A preencher*

---

## 📅 Semana 9 — Dashboard Streamlit
> *A preencher*

---

## 📅 Semana 10 — App Mobile MVP
> *A preencher*

---

## 📅 Semana 11 — Integração e Polimento
> *A preencher*

---

## 📅 Semana 12 — Entrega e Publicação
> *A preencher*

---

*Instituto Federal de Mato Grosso (IFMT)*
*Projeto Extensionista — Dengue MT*