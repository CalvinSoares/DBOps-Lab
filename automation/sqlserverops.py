#!/usr/bin/env python3
"""CLI operacional inicial do SQL Server em Windows."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from automation import dbops


EXIT_OK = 0
EXIT_CONFIG = 2
EXIT_DATABASE = 3
EXIT_VALIDATION = 4
EXIT_UNEXPECTED = 5


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def settings() -> dict[str, str]:
    sqlcmd = env("SQLSERVER_SQLCMD", "sqlcmd")
    if not shutil.which(sqlcmd) and not Path(sqlcmd).exists():
        raise dbops.ConfigError(f"sqlcmd não encontrado: {sqlcmd}")
    instance = env("SQLSERVER_INSTANCE")
    database = env("SQLSERVER_DATABASE")
    backup_dir = env("SQLSERVER_BACKUP_DIR")
    restore_dir = env("SQLSERVER_RESTORE_DIR", backup_dir)
    if not instance or not database or not backup_dir or not restore_dir:
        raise dbops.ConfigError("SQLSERVER_INSTANCE, SQLSERVER_DATABASE, SQLSERVER_BACKUP_DIR e SQLSERVER_RESTORE_DIR são obrigatórios")
    return {"sqlcmd": sqlcmd, "instance": instance, "database": database, "backup_dir": backup_dir, "restore_dir": restore_dir}


def quote_identifier(value: str) -> str:
    return "[" + value.replace("]", "]]") + "]"


def quote_path(value: str) -> str:
    return "N'" + value.replace("'", "''") + "'"


def run_sql(config: dict[str, str], sql: str, *, database: str = "master", timeout: int = 120) -> str:
    result = subprocess.run(
        [config["sqlcmd"], "-S", config["instance"], "-E", "-C", "-b", "-d", database, "-Q", sql, "-W", "-s", "|"],
        cwd=ROOT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise dbops.DatabaseError(result.stderr.strip() or result.stdout.strip() or "sqlcmd retornou erro")
    return result.stdout.strip()


def run_environment_check(config: dict[str, str]) -> dict[str, Any]:
    output = run_sql(
        config,
        "SELECT SERVERPROPERTY('ProductVersion') AS version, SERVERPROPERTY('Edition') AS edition, SERVERPROPERTY('ProductLevel') AS product_level;",
    )
    return {"instance": config["instance"], "output": output, "validated": bool(output)}


def provision(config: dict[str, str]) -> dict[str, Any]:
    database = quote_identifier(config["database"])
    run_sql(config, f"IF DB_ID(N'{config['database']}') IS NULL CREATE DATABASE {database};")
    run_sql(
        config,
        "IF OBJECT_ID(N'dbo.lab_probe') IS NULL "
        "BEGIN CREATE TABLE dbo.lab_probe (id int NOT NULL PRIMARY KEY, created_at datetime2 NOT NULL DEFAULT SYSUTCDATETIME()); "
        "INSERT INTO dbo.lab_probe(id) VALUES (1); END;",
        database=config["database"],
    )
    return {"database": config["database"], "validated": True}


def backup_one(config: dict[str, str], backup_type: str, *, compression: bool) -> dict[str, Any]:
    backup_dir = Path(config["backup_dir"])
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    extension = {"full": "bak", "differential": "bak", "log": "trn"}[backup_type]
    artifact = backup_dir / f"{config['database']}_{backup_type}_{stamp}.{extension}"
    options = ["INIT", "CHECKSUM"]
    if compression:
        options.append("COMPRESSION")
    if backup_type == "differential":
        options.append("DIFFERENTIAL")
    started = time.monotonic()
    database = quote_identifier(config["database"])
    if backup_type == "log":
        run_sql(config, f"ALTER DATABASE {database} SET RECOVERY FULL;")
        statement = f"BACKUP LOG {database} TO DISK={quote_path(str(artifact))} WITH {', '.join(options)}, STATS=10;"
    else:
        statement = f"BACKUP DATABASE {database} TO DISK={quote_path(str(artifact))} WITH {', '.join(options)}, STATS=10;"
    output = run_sql(config, statement)
    verify = run_sql(config, f"RESTORE VERIFYONLY FROM DISK={quote_path(str(artifact))} WITH CHECKSUM;")
    return {
        "type": backup_type,
        "artifact": str(artifact),
        "compression_requested": compression,
        "duration_seconds": round(time.monotonic() - started, 3),
        "backup_output": output,
        "verify_output": verify,
        "validated": True,
    }


def restore_chain(config: dict[str, str], full: str, differential: str, log: str, target: str, *, execute: bool) -> dict[str, Any]:
    target_identifier = quote_identifier(target)
    data_path = Path(config["restore_dir"]) / f"{target}.mdf"
    log_path = Path(config["restore_dir"]) / f"{target}_log.ldf"
    plan = {
        "target": target,
        "full": full,
        "differential": differential,
        "log": log,
        "data_path": str(data_path),
        "log_path": str(log_path),
        "steps": ["substituir somente o banco-alvo", "RESTORE DATABASE full WITH NORECOVERY", "RESTORE DATABASE differential WITH NORECOVERY", "RESTORE LOG WITH RECOVERY", "DBCC CHECKDB e leitura de validação"],
    }
    if not execute:
        return {"mode": "dry-run", "validated": False, **plan}
    started = time.monotonic()
    database = quote_identifier(config["database"])
    sql = f"""
    IF DB_ID(N'{target}') IS NOT NULL
    BEGIN
        ALTER DATABASE {target_identifier} SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
        DROP DATABASE {target_identifier};
    END;
    RESTORE DATABASE {target_identifier}
      FROM DISK={quote_path(full)}
      WITH MOVE N'{config['database']}' TO {quote_path(str(data_path))},
           MOVE N'{config['database']}_log' TO {quote_path(str(log_path))},
           NORECOVERY, CHECKSUM, REPLACE, STATS=10;
    RESTORE DATABASE {target_identifier}
      FROM DISK={quote_path(differential)}
      WITH NORECOVERY, CHECKSUM, STATS=10;
    RESTORE LOG {target_identifier}
      FROM DISK={quote_path(log)}
      WITH RECOVERY, CHECKSUM, STATS=10;
    DBCC CHECKDB ({target_identifier}) WITH NO_INFOMSGS;
    SELECT DB_NAME(database_id) AS database_name, state_desc FROM sys.databases WHERE name=N'{target}';
    SELECT COUNT(*) AS lab_probe_rows FROM {target_identifier}.dbo.lab_probe;
    """
    output = run_sql(config, sql)
    return {"mode": "execute", **plan, "duration_seconds": round(time.monotonic() - started, 3), "output": output, "validated": True}


def performance_check(config: dict[str, str], repetitions: int) -> dict[str, Any]:
    database = quote_identifier(config["database"])
    run_sql(config, f"ALTER DATABASE {database} SET QUERY_STORE = ON (OPERATION_MODE = READ_WRITE, QUERY_CAPTURE_MODE = ALL);")
    started = time.monotonic()
    for _ in range(repetitions):
        run_sql(config, "SELECT COUNT(*) AS row_count FROM dbo.lab_probe WHERE id = 1;", database=config["database"])
    elapsed = time.monotonic() - started
    time.sleep(2)
    query_store = run_sql(
        config,
        "SELECT TOP (10) q.query_id, rs.count_executions, "
        "CAST(rs.avg_duration / 1000.0 AS decimal(18,3)) AS avg_duration_ms, "
        "CAST(rs.avg_cpu_time / 1000.0 AS decimal(18,3)) AS avg_cpu_ms, "
        "rs.avg_logical_io_reads, rs.last_execution_time, qt.query_sql_text "
        "FROM sys.query_store_query AS q "
        "JOIN sys.query_store_query_text AS qt ON qt.query_text_id = q.query_text_id "
        "JOIN sys.query_store_plan AS p ON p.query_id = q.query_id "
        "JOIN sys.query_store_runtime_stats AS rs ON rs.plan_id = p.plan_id "
        "WHERE qt.query_sql_text LIKE N'%lab_probe%' "
        "ORDER BY rs.last_execution_time DESC;",
        database=config["database"],
    )
    waits = run_sql(
        config,
        "SELECT TOP (10) wait_type, waiting_tasks_count, wait_time_ms, signal_wait_time_ms "
        "FROM sys.dm_os_wait_stats "
        "WHERE wait_time_ms > 0 AND wait_type NOT IN "
        "(N'SOS_WORK_DISPATCHER',N'SLEEP_TASK',N'LAZYWRITER_SLEEP',N'LOGMGR_QUEUE',"
        "N'XE_TIMER_EVENT',N'REQUEST_FOR_DEADLOCK_SEARCH',N'QDS_PERSIST_TASK_MAIN_LOOP_SLEEP',"
        "N'BROKER_EVENTHANDLER',N'HADR_FILESTREAM_IOMGR_IOCOMPLETION',N'CLR_AUTO_EVENT',"
        "N'QDS_ASYNC_QUEUE',N'ONDEMAND_TASK_QUEUE',N'XE_DISPATCHER_WAIT',N'CHECKPOINT_QUEUE',"
        "N'BROKER_TO_FLUSH',N'BROKER_TASK_STOP',N'DIRTY_PAGE_POLL',N'SERVER_IDLE_CHECK',"
        "N'SQLTRACE_INCREMENTAL_FLUSH_SLEEP',N'PWAIT_ALL_COMPONENTS_INITIALIZED',N'PREEMPTIVE_OS_FLUSHFILEBUFFERS',"
        "N'PREEMPTIVE_XE_CALLBACKEXECUTE',N'SLEEP_SYSTEMTASK',N'CHKPT') "
        "ORDER BY wait_time_ms DESC;",
        database=config["database"],
    )
    return {
        "query_store_state": run_sql(config, "SELECT actual_state_desc FROM sys.database_query_store_options;", database=config["database"]),
        "repetitions": repetitions,
        "elapsed_seconds": round(elapsed, 3),
        "query_store": query_store,
        "waits": waits,
        "validated": "READ_WRITE" in run_sql(config, "SELECT actual_state_desc FROM sys.database_query_store_options;", database=config["database"]) and "lab_probe" in query_store,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CLI operacional do SQL Server Windows")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("environment-check")
    sub.add_parser("provision")
    backup = sub.add_parser("backup")
    backup.add_argument("--type", choices=["full", "differential", "log", "all"], default="all")
    backup.add_argument("--compression", action="store_true", help="solicita compressão; Express deve rejeitar explicitamente")
    restore = sub.add_parser("restore")
    restore.add_argument("--full", required=True)
    restore.add_argument("--differential", required=True)
    restore.add_argument("--log", required=True)
    restore.add_argument("--target", default="DBOpsLabSqlServer_Restore")
    restore.add_argument("--execute", action="store_true", help="executa o restore destrutivo somente no banco-alvo")
    performance = sub.add_parser("performance-check")
    performance.add_argument("--repetitions", type=int, default=20)
    args = parser.parse_args(argv)
    dbops.configure_logging()
    try:
        dbops.load_env_file(ROOT_DIR / ".env")
        config = settings()
        if args.command == "environment-check":
            result = run_environment_check(config)
        elif args.command == "provision":
            result = provision(config)
        elif args.command == "backup":
            types = ["full", "differential", "log"] if args.type == "all" else [args.type]
            result = {"database": config["database"], "backups": [backup_one(config, item, compression=args.compression) for item in types], "validated": True}
        elif args.command == "restore":
            result = restore_chain(config, args.full, args.differential, args.log, args.target, execute=args.execute)
        else:
            if args.repetitions < 5:
                parser.error("--repetitions deve ser >= 5")
            result = performance_check(config, args.repetitions)
        dbops.log_event(20, "operação SQL Server concluída", **result)
        return EXIT_OK
    except dbops.ConfigError as exc:
        dbops.log_event(40, str(exc))
        return EXIT_CONFIG
    except dbops.DatabaseError as exc:
        dbops.log_event(40, str(exc))
        return EXIT_DATABASE
    except dbops.ValidationError as exc:
        dbops.log_event(40, str(exc))
        return EXIT_VALIDATION
    except Exception as exc:  # noqa: BLE001 - fronteira controlada da CLI
        dbops.log_event(40, "erro inesperado na CLI SQL Server", error_type=type(exc).__name__)
        return EXIT_UNEXPECTED


if __name__ == "__main__":
    raise SystemExit(main())
