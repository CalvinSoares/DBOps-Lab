# DB Operations Lab — Resilient Multi-Database Platform

Projeto de portfólio para DBA/Database Infrastructure com viés DevOps.

**Descrição sugerida para o GitHub:**

> Laboratório reproduzível de DBA/DevOps para PostgreSQL, MySQL/MariaDB e SQL Server: provisionamento, backup/restauração, PITR, performance, observabilidade e resposta a incidentes.

**Repositório:** [github.com/CalvinSoares/DBOps-Lab](https://github.com/CalvinSoares/DBOps-Lab)

## Pré-requisitos da Fase 0

- Docker Engine ou Docker Desktop com Docker Compose;
- Python 3.12 ou compatível para as fases de automação;
- Linux como caminho principal de execução;
- Windows documentado posteriormente para SQL Server Developer;
- pelo menos as portas `5432` (PostgreSQL), `9090` (Prometheus) e `3000` (Grafana) livres quando os perfis correspondentes forem usados.

Plataforma de laboratório multi-banco para demonstrar administração de bancos em produção, recuperação de dados, investigação de performance, automação e observabilidade.

## Evidências de competência

O README final deverá começar com evidências verificáveis de:

- instalação e provisionamento automatizados;
- backup lógico, físico e restauração;
- PITR no PostgreSQL;
- tuning com planos antes/depois e medições reais;
- monitoramento com Prometheus/Grafana;
- automação operacional em Python;
- incidentes simulados e resolvidos.

Nenhuma métrica será inventada. Tempos, RPO, RTO e ganhos de performance só entram aqui depois de serem gerados e armazenados em `benchmarks/` ou `evidence/`.

## Fluxo PostgreSQL validado até aqui

O núcleo PostgreSQL já possui provisionamento idempotente, health check, backup lógico, backup físico com `pg_basebackup`, arquivamento de WAL, verificação com `pg_verifybackup`, restore lógico isolado, PITR em container separado, benchmark de tuning com plano antes/depois e locks, stack de observabilidade com Prometheus/Grafana e três game days controlados de incidentes. As evidências estão em [`evidence/phase-0/round-007.md`](evidence/phase-0/round-007.md), [`evidence/phase-0/round-009.md`](evidence/phase-0/round-009.md), [`evidence/phase-0/round-010.md`](evidence/phase-0/round-010.md) e [`benchmarks/postgres/runs/20261004T000351Z_a48486b9/result.json`](benchmarks/postgres/runs/20261004T000351Z_a48486b9/result.json).

Comandos principais:

```powershell
python automation/dbops.py provision
python automation/dbops.py health-check
python automation/dbops.py backup --type both
python automation/dbops.py verify-backup <artefato>
python automation/dbops.py pitr --base-artifact <backup-fisico> --cleanup
```

Os cenários destrutivos de disco cheio e indisponibilidade, as métricas de idade/falha de backup, MySQL/MariaDB e SQL Server permanecem nas próximas fases. Os game days controlados de query lenta, lock e backup inválido foram medidos; isso não é apresentado como alta disponibilidade ou experiência de produção.

## Ordem de execução

1. PostgreSQL, Docker Compose, Linux, CLI Python e documentação operacional.
2. Backup/restore, PITR e teste automático de recuperação.
3. Tuning, locks, queries lentas e evidências comparáveis.
4. Prometheus/Grafana, exporters e alertas operacionais.
5. MySQL/MariaDB como banco secundário.
6. SQL Server Developer com runbook para Windows.
7. Kubernetes como etapa opcional e explicitamente limitada.

O plano detalhado está em [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md). As regras para agentes estão em [`AGENTS.md`](AGENTS.md), os checks em [`docs/CHECKS.md`](docs/CHECKS.md) e a matriz de evidências em [`docs/EVIDENCE_MATRIX.md`](docs/EVIDENCE_MATRIX.md).

## Estrutura prevista

```text
dbops-lab/
├── AGENTS.md
├── docker-compose.yml
├── README.md
├── architecture/
├── automation/
├── postgres/
├── mysql/
├── sqlserver/
├── monitoring/
├── kubernetes/
├── migrations/
├── incidents/
├── benchmarks/
├── evidence/
└── tests/
```

## Escopo inicial

O primeiro incremento deve provar um fluxo completo no PostgreSQL: provisionar, aplicar migration, verificar saúde, executar backup, restaurar em ambiente separado, validar dados e registrar evidências. Os demais bancos entram depois, sem bloquear a entrega do núcleo.
