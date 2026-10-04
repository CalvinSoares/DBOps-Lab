# Rodada 014 — README orientado ao projeto e à execução

## Identificação

- **Projeto:** DB Operations Lab — Resilient Multi-Database Platform
- **Fase de trabalho:** documentação operacional após a validação do núcleo PostgreSQL
- **Rodada:** 014
- **Agentes:** documentação/currículo e orquestrador
- **Data/hora:** 2026-10-04, America/Sao_Paulo
- **Status:** concluído

## Objetivo

Reescrever o README principal para explicar o que é o projeto, como executá-lo e quais capacidades operacionais já estão demonstradas. O README deixou de funcionar como um histórico de fases; os detalhes de execução continuam nas pastas `automation/`, `incidents/`, `monitoring/`, `benchmarks/` e `evidence/`.

## Estado anterior

O README misturava:

- descrição do projeto;
- ordem das fases;
- pendências do plano;
- evidências de execução;
- comandos operacionais.

Isso dificultava a leitura de alguém avaliando o projeto no GitHub e não deixava claro como iniciar o laboratório.

## Alteração realizada

O `README.md` foi reorganizado para conter:

1. descrição do laboratório e objetivo profissional;
2. diagrama textual da arquitetura;
3. evidências de competência com links;
4. pré-requisitos e portas;
5. instalação rápida;
6. execução do PostgreSQL;
7. provisionamento, health check, backup, restore, WAL e PITR;
8. benchmark de performance;
9. Prometheus, Grafana e exporters;
10. comandos dos game days;
11. status operacional atual;
12. estrutura do repositório;
13. segurança e limitações.

As fases não são apresentadas como conteúdo principal. Os links para `evidence/phase-*` existem apenas para apontar a prova reproduzível de cada capacidade.

## Comandos de validação

```powershell
git diff --check
```

Resultado: nenhuma falha de whitespace foi encontrada na alteração do README. Nenhum check técnico foi alterado nesta rodada; os estados continuam registrados em `docs/CHECKS.md` e `docs/EVIDENCE_MATRIX.md`.

## Decisões de documentação

- O README usa português, mantendo nomes de ferramentas e comandos originais.
- O quick start não exige que o leitor conheça o plano interno de execução.
- O `.env` é tratado como arquivo local e nunca como artefato de publicação.
- RPO, RTO e métricas de performance são apresentados somente quando existe evidência correspondente.
- MySQL/MariaDB, SQL Server e Kubernetes aparecem como extensões de escopo, sem fingir que já estão validados.

## Pendências

Nenhuma pendência de código foi criada por esta rodada. A próxima alteração funcional continua sendo a implementação do MySQL/MariaDB, conforme o estado operacional registrado após o game day isolado de indisponibilidade.

## Comandos granulares para o usuário salvar e commitar

Estes comandos não foram executados pelo agente:

```powershell
git add README.md
git commit -m "docs: rewrite project README"

git add evidence/phase-5/round-014.md
git commit -m "docs: record README documentation update"
```

As alterações em `AGENTS.md` e `docs/` continuam ignoradas pela política do projeto.
