# MariaDB secundário

O MariaDB é o banco secundário do laboratório. Ele usa o profile `secondary` do Docker Compose e possui um ciclo operacional próprio, separado do PostgreSQL.

## Subida

```powershell
docker compose --profile secondary up -d mariadb
python automation/mysqlops.py provision
python automation/mysqlops.py health-check
```

Porta local padrão: `13306`.

## Operações

```powershell
python automation/mysqlops.py backup
python automation/mysqlops.py verify-backup <arquivo.sql.gz>
python automation/mysqlops.py restore <arquivo.sql.gz>
```

## Diagnóstico de performance

O MariaDB é iniciado com o `performance_schema` habilitado. O benchmark cria uma tabela exclusiva do laboratório, mede a consulta sem índice, aplica o índice composto `(region, status)`, executa `ANALYZE TABLE`, mede novamente e coleta o digest em `events_statements_summary_by_digest`:

```powershell
python automation/benchmark_mysql.py --rows 50000 --repetitions 20
```

Os artefatos ficam em `benchmarks/mysql/runs/<timestamp>/`, incluindo `EXPLAIN` antes/depois, digest do Performance Schema e `result.json`. Os números são específicos da execução e não devem ser tratados como garantia de produção.

O backup é lógico, comprimido com gzip e acompanhado por manifesto SHA-256. O restore cria uma base `secondary_restore_<timestamp>` e valida tabelas e contagens.

## Escopo

Esta primeira implementação cobre provisionamento, health check, backup lógico, restore e consistência. Performance Schema, exporter, dashboard e incidente MariaDB serão adicionados após o primeiro ciclo de restore validado.
