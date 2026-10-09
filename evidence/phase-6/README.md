# Evidências da Fase 6 — MariaDB secundário

Esta pasta registra o primeiro ciclo operacional do banco secundário MariaDB.

## Resultado

- provisionamento e health check validados;
- schema e dados sintéticos criados de forma idempotente;
- backup lógico comprimido gerado;
- manifesto com tamanho e SHA-256 validado;
- integridade do gzip validada;
- restore executado em banco separado;
- tabelas e contagens pós-restore conferidas.
- diagnóstico com Performance Schema, plano antes/depois e índice composto;
- game day de indisponibilidade executado em Compose descartável.

## Artefatos

- `round-016.md`: relatório reproduzível da rodada;
- `round-017.md`: benchmark e diagnóstico de performance;
- `round-018.md`: incidente MariaDB indisponível;
- `round-019.md`: exporter, Prometheus, Grafana e alertas MariaDB;
- `mariadb-result-20261008T224545Z.json`: resumo sem credenciais da execução;
- `mariadb-monitoring-20261008T225343Z.json`: coleta real no Prometheus;
- `incident-mariadb-down-20261008T224958Z.json`: game day validado;
- `../../mysql/backup/secondary_db_20261008T224540Z.sql.gz.manifest.json`: manifesto do backup.

O dump `.sql.gz` é artefato local de laboratório e permanece fora do commit conforme as regras do projeto. O manifesto e o resumo da validação são suficientes para rastrear o resultado sem versionar dados de banco.
