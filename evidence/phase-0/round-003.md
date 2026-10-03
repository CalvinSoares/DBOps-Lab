# Rodada 003 — Ignorar documentação local e AGENTS.md

## Identificação

- **Projeto:** DB Operations Lab — Resilient Multi-Database Platform
- **Fase:** 0 — Fundação e contrato operacional
- **Rodada:** 003
- **Agente:** Codex — configuração e documentação
- **Data:** 2026-10-03 (America/Sao_Paulo)
- **Status:** concluída

## Objetivo

Adicionar a pasta `docs/` e o arquivo raiz `AGENTS.md` ao `.gitignore`, conforme solicitado pelo usuário, mantendo esses arquivos disponíveis localmente para orientar o trabalho sem incluí-los em commits normais.

## Estado antes da alteração

- `.gitignore` ignorava segredos, dados persistentes, dumps, logs e caches locais.
- `docs/` e `AGENTS.md` ainda não possuíam regras de ignore.
- A política de Git já proibia o agente de executar `git add`, `git commit` e `git push`.

## Alterações realizadas

### `.gitignore`

Adicionadas as regras:

```gitignore
# Documentação e instruções mantidas somente no ambiente local
/docs/
/AGENTS.md
```

O prefixo `/` limita o comportamento ao diretório raiz do projeto:

- `/docs/` ignora somente a pasta `docs` do projeto;
- `/AGENTS.md` ignora somente o `AGENTS.md` da raiz.

Os arquivos continuam existindo no workspace e continuam disponíveis para os agentes. Eles apenas deixam de ser selecionados por um `git add .` normal.

## Comandos executados

Antes da alteração foram lidos `AGENTS.md`, `docs/PROJECT_PLAN.md`, `docs/CHECKS.md` e `.gitignore`, conforme as regras do projeto.

Foi aplicado um patch somente em `.gitignore` e criado este registro em `evidence/phase-0/`. Não foi executado nenhum comando Git de escrita.

## Resultado dos checks

- Regra `/docs/` presente no `.gitignore`.
- Regra `/AGENTS.md` presente no `.gitignore`.
- `docs/` e `AGENTS.md` continuam presentes localmente.
- Nenhum código, Compose, credencial ou configuração operacional foi alterado.
- Check 0 continua válido; nenhum novo check foi concluído nesta rodada.
- Nenhum commit ou push foi executado.

## Impacto e limitação importante

Como consequência intencional, `docs/` e `AGENTS.md` não serão enviados ao GitHub por comandos normais. Isso reduz a documentação disponível para quem clonar o repositório. Se posteriormente for necessário versionar algum desses arquivos, o usuário deverá usar `git add -f` conscientemente.

## Próximo passo

Iniciar a Fase 1 — PostgreSQL provisionável. A documentação de planejamento continuará sendo mantida localmente e os resultados da implementação continuarão sendo registrados em `evidence/`.

## Comandos granulares para o usuário salvar e commitar

Como `docs/` e `AGENTS.md` agora estão ignorados, os comandos abaixo adicionam somente a alteração de configuração e a evidência da rodada:

```powershell
git add .gitignore
git commit -m "chore: ignore local agent instructions and docs"

git add evidence/phase-0/round-003.md
git commit -m "docs: record round 003 gitignore change"
```

Não usar `git add -f` para `docs/` ou `AGENTS.md` sem uma decisão explícita de versioná-los.
