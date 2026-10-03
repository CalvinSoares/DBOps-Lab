# Rodada 002 — Tradução da descrição do projeto

## Identificação

- **Projeto:** DB Operations Lab — Resilient Multi-Database Platform
- **Fase:** 0 — Fundação e contrato operacional
- **Rodada:** 002
- **Agente:** Codex — documentação
- **Data/hora:** 2026-10-03 19:28:11 -03:00 (America/Sao_Paulo)
- **Status:** concluída

## Objetivo

Traduzir para português a descrição oficial do projeto usada no contrato de agentes e no README, preservando os termos técnicos consagrados como DBA/DevOps, PostgreSQL, MySQL/MariaDB, SQL Server e PITR.

## Estado antes da alteração

A descrição oficial ainda estava em inglês em dois locais:

- `AGENTS.md`, na seção de identidade do projeto;
- `README.md`, na descrição sugerida para o GitHub.

O histórico da Rodada 001 em `evidence/phase-0/round-001.md` não foi alterado, pois ele é um registro histórico do estado daquela rodada.

## Alterações realizadas

### `AGENTS.md`

Alterada a descrição do GitHub para:

> Laboratório reproduzível de DBA/DevOps para PostgreSQL, MySQL/MariaDB e SQL Server: provisionamento, backup/restauração, PITR, performance, observabilidade e resposta a incidentes.

Esse texto fica no contrato que orienta todas as próximas rodadas.

### `README.md`

Atualizada a descrição sugerida para o GitHub com o mesmo texto em português, evitando divergência entre o README e o contrato de agentes.

## Comandos executados

Antes da alteração, foram lidos `AGENTS.md`, `docs/PROJECT_PLAN.md`, `docs/CHECKS.md` e a lista atual de arquivos, conforme exigido pelo contrato do projeto.

Foi utilizado o patch de edição de arquivos para substituir somente as duas descrições. Nenhum arquivo de código, configuração, infraestrutura ou credencial foi alterado.

## Checks e resultado

- Check 0 permanece concluído.
- Checks 1 a 8 permanecem pendentes.
- A descrição em inglês foi removida dos documentos ativos `AGENTS.md` e `README.md`.
- O texto traduzido aparece nos dois documentos ativos.
- Nenhuma operação Git foi executada.
- Nenhum commit, push ou alteração remota foi realizado.

## Limitações

- A descrição no GitHub ainda não foi alterada remotamente, porque o agente não possui autorização para escrita remota. O usuário deverá copiar o texto para o campo de descrição do repositório.
- O registro histórico da Rodada 001 mantém o texto original em inglês de propósito; isso preserva a rastreabilidade da alteração.

## Próximo passo

Prosseguir para a Fase 1 — PostgreSQL provisionável, começando pela CLI Python, migrations, roles, permissões e health check.

## Comandos granulares para o usuário salvar e commitar

Estes comandos não foram executados pelo agente:

```powershell
git add AGENTS.md README.md
git commit -m "docs: translate project description to Portuguese"

git add evidence/phase-0/round-002.md
git commit -m "docs: record round 002 translation"
```

Descrição para copiar no campo do GitHub:

```text
Laboratório reproduzível de DBA/DevOps para PostgreSQL, MySQL/MariaDB e SQL Server: provisionamento, backup/restauração, PITR, performance, observabilidade e resposta a incidentes.
```
