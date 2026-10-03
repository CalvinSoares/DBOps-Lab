# Rodada 001 — Fundação e contrato operacional

## Identificação

- **Projeto:** DB Operations Lab — Resilient Multi-Database Platform
- **Fase:** 0 — Fundação e contrato operacional
- **Rodada:** 001
- **Agente:** Codex — orquestrador, DevOps/Automação e documentação
- **Data/hora:** 2026-10-03 19:25:32 -03:00 (America/Sao_Paulo)
- **Repositório oficial:** https://github.com/CalvinSoares/DBOps-Lab
- **Status:** concluída para a fundação; implementação de provisionamento, backup, restore e observabilidade do banco ainda está pendente das próximas fases.

## Objetivo

Preparar uma base segura e reproduzível para começar o laboratório, estabelecer a política de colaboração com GitHub e criar o primeiro Compose executável com PostgreSQL. A rodada não implementa a CLI, migrations, exporters, backup, PITR ou tuning.

## Estado antes da rodada

- Existiam apenas documentação de planejamento, checks, matriz de evidências e README inicial.
- Não existiam `.gitignore`, `.env.example`, `docker-compose.yml`, configuração do Prometheus ou estrutura de diretórios operacionais.
- A tentativa de `git status --short` indicou que a pasta local ainda não estava inicializada como repositório Git.
- Não havia diretório `evidence/phase-0/` para registrar a rodada.

## Alterações realizadas

### 1. Contrato de agentes — `AGENTS.md`

Adicionados:

- nome oficial, slug sugerido e descrição do GitHub;
- URL oficial do repositório;
- política explícita proibindo `git add`, `git commit`, `git push`, tags, releases, PRs e escritas remotas pelo agente;
- permissão limitada a leitura e `git pull` quando necessário;
- obrigação de enviar ao usuário comandos granulares de salvamento/commit ao fim de cada rodada;
- formato obrigatório do relatório de cada rodada, incluindo objetivo, estado anterior, arquivos, comandos, checks, evidências, limitações e próximo passo.

### 2. Identidade e apresentação — `README.md`

- título atualizado para o nome oficial;
- descrição sugerida para o GitHub adicionada;
- link do repositório oficial adicionado;
- pré-requisitos da Fase 0, caminho Linux, Windows/SQL Server futuro e portas previstas adicionados.

### 3. Segurança local — `.gitignore` e `.env.example`

- `.gitignore` passou a bloquear `.env`, dados persistentes, dumps, backups, logs, caches Python e estado local do Grafana;
- `.env.example` documenta variáveis necessárias sem conter credenciais reais;
- imagens de PostgreSQL, Prometheus e Grafana foram definidas como baseline pinada, sem afirmar que são as versões mais recentes.

### 4. Compose inicial — `docker-compose.yml`

- criado serviço PostgreSQL com volume persistente `postgres_data`;
- configurado `healthcheck` com `pg_isready`;
- montado `postgres/init` como diretório de inicialização futuro;
- adicionados perfis opcionais `monitoring` para Prometheus e Grafana;
- configurados volumes separados para Prometheus e Grafana;
- exporters não foram adicionados ainda porque a role de monitoramento e suas permissões mínimas serão implementadas na Fase 1/4.

### 5. Arquitetura — `architecture/README.md` e `monitoring/prometheus.yml`

- documentado o fluxo atual e o fluxo futuro;
- registradas as portas `5432`, `9090` e `3000`;
- registrado que volume persistente não é backup;
- Prometheus foi configurado apenas para auto-scrape nesta fase, sem alegar monitoramento do PostgreSQL.

### 6. Estrutura de trabalho

Criados placeholders `.gitkeep` para:

`automation/`, `postgres/init/`, `postgres/backup/`, `postgres/recovery/`, `mysql/`, `sqlserver/`, `kubernetes/`, `migrations/`, `incidents/`, `benchmarks/`, `tests/` e `monitoring/grafana/dashboards/`.

### 7. Planejamento e checks

- `docs/PROJECT_PLAN.md` agora exige o relatório da rodada em `evidence/phase-0/`;
- o Check 0 de `docs/CHECKS.md` foi marcado como concluído porque os seis critérios possuem arquivos e validação nesta rodada;
- a matriz recebeu a competência de fundação e reprodutibilidade com status `validated`.

## Comandos executados e resultados

### Verificação estrutural

Foi verificada a presença dos arquivos principais e dos placeholders. Resultado: arquivos esperados presentes, exceto o diretório de evidência antes de este relatório ser criado.

### Validação do Compose

```powershell
docker compose --env-file .env.example config --quiet
```

Resultado: código `0`. A configuração foi aceita pelo Docker Compose usando somente o arquivo de exemplo.

Observação: o Docker exibiu um aviso de permissão ao ler `C:\Users\Calvo\.docker\config.json`, mas a validação do Compose terminou com sucesso. Isso deve ser investigado se afetar comandos que precisem autenticar ou baixar imagens.

### Versão do ambiente

```powershell
docker --version
python --version
```

Resultado observado:

- Docker `29.1.3`;
- Python `3.12.1`.

### Varredura básica de segredos

Foi feita uma busca por padrões comuns de chaves/tokens nos arquivos do projeto. Resultado: nenhum padrão conhecido foi encontrado. Isso não substitui revisão manual antes de um commit.

## Checks concluídos

- Check 0 — Segurança e reprodutibilidade: concluído.
- Checks 1 a 8: ainda não iniciados; permanecem desmarcados.
- Check final de portfólio: ainda não iniciado.

## Limitações e decisões

- O banco ainda não foi iniciado com `docker compose up`, porque esta rodada valida a configuração e não inicia serviços persistentes.
- Não foi criado `.env` local, deliberadamente, para evitar persistir credenciais de laboratório.
- A pasta local não está reconhecida como repositório Git nesta execução; nenhum comando de commit ou push foi executado.
- A validação não prova que as imagens serão baixadas nem que o PostgreSQL está operacional; isso pertence à Fase 1.
- Não há exporter PostgreSQL ainda; o comentário no arquivo de Prometheus deixa essa ausência explícita.

## Próximo passo

Fase 1 — PostgreSQL provisionável: criar a CLI `automation/dbops.py`, migrations, roles com privilégios separados, role mínima para monitoramento, health check, logs e teste idempotente de provisionamento.

## Comandos granulares para o usuário salvar e commitar

Estes comandos são apenas para execução manual pelo usuário; o agente não os executou:

```powershell
git add AGENTS.md README.md docs/PROJECT_PLAN.md docs/CHECKS.md docs/EVIDENCE_MATRIX.md
git commit -m "docs: define project identity and agent workflow"

git add .gitignore .env.example docker-compose.yml monitoring/prometheus.yml architecture/README.md
git commit -m "chore: add phase 0 compose foundation"

git add automation postgres mysql sqlserver kubernetes migrations incidents benchmarks tests monitoring/grafana
git commit -m "chore: scaffold db operations directories"

git add evidence/phase-0/round-001.md
git commit -m "docs: record round 001 evidence"

git push origin main
```

Antes do `git push`, revisar o branch atual com `git branch --show-current`, confirmar que não há segredos e ajustar `main` caso o branch local tenha outro nome.
