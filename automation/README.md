# Automação das Fases 1–5

## Preparação

Na raiz do projeto, crie o arquivo local de ambiente a partir do exemplo:

```powershell
Copy-Item .env.example .env
```

O arquivo `.env` é ignorado pelo Git. Troque as senhas de laboratório antes de usar o ambiente fora da máquina local.

Instale a dependência Python em um ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r automation/requirements.txt
```

## Uso

Suba o PostgreSQL:

```powershell
docker compose up -d postgres
```

Execute o provisionamento e o health check:

```powershell
python automation/dbops.py provision
python automation/dbops.py health-check
python automation/dbops.py backup
python automation/dbops.py backup --type physical
python automation/dbops.py backup --type both
python automation/dbops.py wal-status
python automation/dbops.py pitr --base-artifact <backup-fisico> --cleanup
python automation/benchmark_postgres.py --rows 200000 --cleanup
python automation/check_monitoring.py
python automation/run_incident.py slow-query
python automation/run_incident.py slow-query --execute --duration 20 --observe-prometheus
python automation/run_incident.py lock --execute --observe-prometheus
python automation/run_incident.py backup-invalid --execute
```

O backup lógico é gravado em `postgres/backup/artifacts/` com formato custom do PostgreSQL e manifesto contendo tamanho e SHA-256. Para verificar e restaurar um artefato:

```powershell
python automation/dbops.py verify-backup <nome-do-arquivo>.dump
python automation/dbops.py restore <nome-do-arquivo>.dump
```

O restore cria um banco novo com prefixo `dbops_restore_` e valida schema, migrations e dados básicos. Nesta primeira subetapa, o banco isolado ainda pertence ao mesmo servidor PostgreSQL; o restore em ambiente separado será validado junto com o backup físico.

O backup físico usa `pg_basebackup` com uma role de replicação dedicada (`POSTGRES_BACKUP_USER`) e fica em `postgres/backup/physical/`. O comando `wal-status` força uma troca de WAL, consulta `pg_stat_archiver` e confirma a existência de segmentos no diretório `postgres/backup/wal/`.

O comando `pitr` cria marcadores sintéticos antes e depois de um horário-alvo, inicia o backup físico em um container PostgreSQL separado com `recovery.signal`, `restore_command` e `recovery_target_time`, e valida que o marcador anterior existe enquanto o posterior não existe. A opção `--cleanup` remove apenas os registros sintéticos criados pelo próprio teste no banco principal. Use `--keep-recovery` para preservar o cluster recuperado para inspeção. Cada execução aprovada grava um resultado JSON em `evidence/phase-0/`.

O benchmark PostgreSQL cria um schema sintético, coleta planos antes/depois com `EXPLAIN (ANALYZE, BUFFERS)`, cria um índice composto, executa `ANALYZE` e reproduz um lock com `pg_blocking_pids`. Os planos e métricas ficam em `benchmarks/postgres/runs/`; `--cleanup` remove somente o schema criado pelo benchmark.

O check de observabilidade consulta Grafana, Prometheus e os exporters em execução. Ele valida o dashboard provisionado, as séries de disponibilidade, conexões, atividade, CPU e memória, as regras de alerta e a conectividade do exporter PostgreSQL. Cada execução aprovada grava um JSON em `evidence/phase-0/`.

O executor de incidentes opera em `dry-run` por padrão. Query lenta e lock usam sessões temporárias com rollback/timeout; `--observe-prometheus` registra a série antes/durante/depois; `backup-invalid` altera apenas uma cópia temporária de um dump e revalida o original. Cenários de indisponibilidade, disco cheio, exclusão acidental e réplica ficam protegidos por runbooks e não são executados automaticamente.

## Códigos de saída

- `0`: operação concluída;
- `2`: configuração ausente ou inválida;
- `3`: falha de conexão ou do banco;
- `4`: validação operacional falhou;
- `5`: erro inesperado.

Os logs são emitidos em JSON no stderr e não incluem senhas.
