# Bullets de currículo — DB Operations Lab

Use este material como projeto de portfólio ou laboratório. Não apresentar as atividades como experiência profissional.

## Descrição curta

**DB Operations Lab — Projeto de portfólio**

Laboratório reproduzível de DBA/DevOps com PostgreSQL, MariaDB e SQL Server em Windows, usando Docker Compose, Linux/WSL2, Python, Prometheus e Grafana. O projeto cobre provisionamento, backup/restore, PITR, tuning, observabilidade, automação e resposta a incidentes.

## Bullets baseados em evidências

- Desenvolvi uma CLI operacional em Python para provisionamento, health checks, backup, restore e validação de PostgreSQL, MariaDB e SQL Server, com logs estruturados, códigos de saída e testes automatizados.
- Validei backup lógico, físico, arquivamento de WAL e PITR no PostgreSQL, com restauração em cluster separado e evidências reproduzíveis.
- Implementei ciclo MariaDB de provisionamento, backup lógico comprimido, checksum, restore separado e consistência pós-restore; o artefato validado teve 1.281 bytes e SHA-256 registrado em manifesto.
- Investiguei uma consulta MariaDB com 50.000 linhas usando `EXPLAIN` e Performance Schema; a execução medida caiu de 0,657 s para 0,531 s em 20 repetições após índice composto — resultado específico do ambiente de laboratório.
- Configurei exporter MariaDB, Prometheus, Grafana e alertas para disponibilidade, conexões, threads, queries lentas e uptime; target e `mysql_up` foram validados com coleta real.
- Executei game day isolado de indisponibilidade MariaDB, validando estado saudável, falha `exited/unhealthy`, recuperação `running/healthy` e consulta pós-recuperação sem interromper o banco principal.
- Operei SQL Server Express no Windows com backups full, differential e transaction log, `CHECKSUM`, `RESTORE VERIFYONLY` e restore separado com `DBCC CHECKDB` sem erros.
- Habilitei Query Store e analisei waits do SQL Server; a consulta de laboratório registrou 0,032 ms de duração média e 2 leituras lógicas no snapshot mais recente.

## Limitações que devem acompanhar a apresentação

- SQL Server validado localmente foi Express 2019, não Developer; compressão de backup foi testada e rejeitada pela edição.
- Tempos, throughput, waits e contagens são evidências do ambiente local e não garantias de produção.
- RPO/RTO ainda não devem ser apresentados como números medidos sem um teste dedicado.
- Kubernetes permanece opcional e não é tratado como alta disponibilidade automática.

## Referências de evidência

- PostgreSQL: `evidence/phase-0/` e `benchmarks/postgres/`;
- MariaDB: `evidence/phase-6/` e `benchmarks/mysql/`;
- SQL Server: `evidence/phase-7/`;
- incidentes: `incidents/` e `evidence/phase-5/`;
- matriz: `docs/EVIDENCE_MATRIX.md` no ambiente local de agentes.
