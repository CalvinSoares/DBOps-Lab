# Observabilidade do DB Operations Lab

## Subida do stack

```powershell
docker compose --profile monitoring up -d
python automation/check_monitoring.py
```

Serviços e portas padrão:

- PostgreSQL: `15432` neste ambiente local;
- Prometheus: `9090`;
- Grafana: `3000`;
- PostgreSQL exporter: `9187`;
- node-exporter: `19100` no host local, `9100` dentro da rede Compose.

O `postgres-exporter` usa a role `dbops_monitor`, que recebe `pg_monitor` durante o provisionamento. O `node-exporter` coleta métricas do ambiente Linux do Docker; no Docker Desktop/Windows isso representa a VM Linux do Docker, não todos os contadores nativos do Windows.

## Métricas cobertas

O dashboard `DBOps Lab — PostgreSQL Overview` é provisionado automaticamente e consulta:

- disponibilidade (`pg_up` e targets `up`);
- conexões (`pg_stat_database_numbackends`);
- tamanho do banco (`pg_database_size_bytes`);
- transações e rollback;
- deadlocks;
- queries ativas e idade máxima através da consulta customizada em `postgres_exporter_queries.yaml`;
- sessões aguardando lock;
- idade, duração, tamanho e falha do último backup lógico/físico;
- CPU e memória do ambiente Linux monitorado.

As regras em `alerts.yml` cobrem indisponibilidade do exporter, excesso de conexões, deadlocks, query longa, backup falho/atrasado e filesystem com pouco espaço. Cada regra possui severidade, condição e ação operacional na anotação.

O provisionamento aplica `migrations/002_backup_status.sql`. A CLI registra cada tentativa em `public.dbops_backup_status`; o exporter publica os nomes prefixados `dbops_backup_status_age_seconds`, `dbops_backup_status_failed`, `dbops_backup_status_duration_seconds` e `dbops_backup_status_size_bytes`.

## Evidência

`automation/check_monitoring.py` valida os endpoints reais, os targets `postgresql` e `node`, `pg_up`, as séries de CPU, idade de query, lock waits e status de backup, as regras carregadas, a saúde do Grafana e o dashboard provisionado pela API. O resultado JSON é salvo em `evidence/phase-0/`.

O aceite completo da Fase 4 exige exercitar os dashboards durante três incidentes. Dois game days controlados já capturam mudança de métrica antes/durante/depois; o terceiro incidente de disponibilidade permanece pendente por exigir interrupção autorizada ou ambiente descartável.
