# ADR-001 — Conventional Commits + GitFlow dev→main
 
**Status:** Aceito  
**Data:** 09/03/2026  
**Tema:** Infraestrutura / Versionamento
 
---
 
## Contexto
 
Projeto iniciado do zero com necessidade de rastreabilidade desde o primeiro commit.
Sem uma convenção formal, o histórico do repositório se tornaria ilegível ao longo
das semanas — impossibilitando auditorias, apresentações e reprodução dos experimentos.
 
## Decisão
 
Adotar **Conventional Commits** como padrão de mensagens de commit e **GitFlow
simplificado** com duas branches permanentes:
 
**Prefixos de commit:**
| Prefixo | Uso |
|---------|-----|
| `feat:` | Nova funcionalidade ou dado |
| `fix:` | Correção de bug ou dado incorreto |
| `docs:` | Documentação |
| `refactor:` | Reestruturação sem mudança de comportamento |
| `test:` | Testes automatizados |
| `chore:` | Manutenção, dependências |
 
**Estratégia de branches:**
- `dev` — desenvolvimento ativo, commits frequentes
- `main` — entregas estáveis, merge apenas ao final de sessões validadas
- `feature/nome` — branches temporárias para mudanças maiores
**Numeração sequencial:** cada commit inclui número incremental entre parênteses
no final da mensagem — ex: `feat: ingestão InfoDengue completa (12)`.
Facilita referência cruzada entre documentação e histórico git.
 
## Consequências
 
- Histórico do repositório legível e auditável por período/tipo de mudança
- `git log --oneline` funciona como changelog navegável
- Apresentações acadêmicas podem referenciar commits específicos por número
- Branches `dev` e `main` sincronizadas ao final de cada sessão de trabalho
## Alternativas consideradas
 
- Commits livres sem convenção — descartado por ilegibilidade a longo prazo
- GitFlow completo com `release/` e `hotfix/` — descartado por overhead
  desnecessário para projeto de 1-2 desenvolvedores