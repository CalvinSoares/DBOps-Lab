#!/usr/bin/env python3
"""CLI operacional do MariaDB secundário do DB Operations Lab."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
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
SERVICE = "mariadb"
CONTAINER_BACKUP_DIR = "/var/lib/mysql/backups"


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise dbops.ConfigError(f"Variável obrigatória ausente: {name}")
    return value


def settings() -> dict[str, str]:
    return {
        "database": required_env("MYSQL_DATABASE"),
        "root_password": required_env("MYSQL_ROOT_PASSWORD"),
        "user": required_env("MYSQL_USER"),
        "password": required_env("MYSQL_PASSWORD"),
        "backup_dir": str((ROOT_DIR / os.getenv("MYSQL_BACKUP_DIR", "mysql/backup")).resolve()),
    }


def compose_exec(command: str, *, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "--profile", "secondary", "exec", "-T", SERVICE, "sh", "-lc", command],
        cwd=ROOT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
        env=os.environ.copy(),
    )


def run_compose(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "--profile", "secondary", *args],
        cwd=ROOT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
        env=os.environ.copy(),
    )


def mariadb_sql(sql: str, *, database: str | None = None, timeout: int = 60) -> str:
    target = f" --database={database}" if database else ""
    command = f'''mariadb --protocol=socket --user=root --password="$MARIADB_ROOT_PASSWORD"{target} --batch --skip-column-names --execute={json.dumps(sql)}'''
    result = compose_exec(command, timeout=timeout)
    if result.returncode != 0:
        raise dbops.DatabaseError(f"MariaDB rejeitou SQL ({result.returncode})")
    return result.stdout.strip()


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_path(artifact: Path) -> Path:
    return artifact.with_name(f"{artifact.name}.manifest.json")


def write_manifest(artifact: Path, duration_seconds: float) -> Path:
    manifest = {
        "artifact": artifact.name,
        "artifact_type": "mariadb_logical",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "database": os.environ["MYSQL_DATABASE"],
        "engine": "mariadb",
        "sha256": hash_file(artifact),
        "size_bytes": artifact.stat().st_size,
        "duration_seconds": round(duration_seconds, 3),
    }
    output = manifest_path(artifact)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def run_provision(config: dict[str, str]) -> dict[str, Any]:
    result = run_compose("up", "-d", SERVICE)
    if result.returncode != 0:
        raise dbops.DatabaseError("não foi possível iniciar o serviço MariaDB")
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        probe = run_compose("exec", "-T", SERVICE, "healthcheck.sh", "--connect", "--innodb_initialized")
        if probe.returncode == 0:
            break
        time.sleep(2)
    else:
        raise dbops.DatabaseError("MariaDB não ficou saudável em 90 segundos")
    schema = (ROOT_DIR / "mysql/init/001_schema.sql").read_text(encoding="utf-8")
    command = 'mariadb --protocol=socket --user=root --password="$MARIADB_ROOT_PASSWORD"'
    apply = subprocess.run(
        ["docker", "compose", "--profile", "secondary", "exec", "-T", SERVICE, "sh", "-lc", command],
        cwd=ROOT_DIR,
        input=schema,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
        check=False,
    )
    if apply.returncode != 0:
        raise dbops.DatabaseError("migration MariaDB falhou")
    return {"service": SERVICE, "database": config["database"], "validated": True}


def run_health_check(config: dict[str, str]) -> dict[str, Any]:
    version = mariadb_sql("SELECT VERSION();")
    database = mariadb_sql("SELECT DATABASE();", database=config["database"])
    tables = mariadb_sql("SHOW TABLES;", database=config["database"]).splitlines()
    expected = {"customers", "tickets", "ticket_events"}
    missing = sorted(expected - set(tables))
    if missing:
        raise dbops.ValidationError(f"tabelas MariaDB ausentes: {', '.join(missing)}")
    return {
        "version": version,
        "database": database,
        "tables": sorted(tables),
        "validated": True,
    }


def run_seed(config: dict[str, str]) -> dict[str, Any]:
    """Insere dados sintéticos idempotentes para validar backup e restore."""

    database = config["database"]
    mariadb_sql(
        "INSERT INTO customers (full_name, email) "
        "VALUES ('MariaDB Lab', 'mariadb-lab@example.invalid') "
        "ON DUPLICATE KEY UPDATE full_name = VALUES(full_name);",
        database=database,
    )
    mariadb_sql(
        "INSERT INTO tickets (customer_id, subject, status, priority) "
        "SELECT customer_id, 'MariaDB restore test', 'open', 2 FROM customers "
        "WHERE email = 'mariadb-lab@example.invalid' "
        "AND NOT EXISTS (SELECT 1 FROM tickets WHERE subject = 'MariaDB restore test');",
        database=database,
    )
    mariadb_sql(
        "INSERT INTO ticket_events (ticket_id, event_type, event_payload) "
        "SELECT ticket_id, 'created', '{}' FROM tickets "
        "WHERE subject = 'MariaDB restore test' "
        "AND NOT EXISTS (SELECT 1 FROM ticket_events WHERE event_type = 'created' AND ticket_id = tickets.ticket_id);",
        database=database,
    )
    counts = {
        table: int(mariadb_sql(f"SELECT COUNT(*) FROM {table};", database=database) or 0)
        for table in ("customers", "tickets", "ticket_events")
    }
    return {"database": database, "counts": counts, "validated": all(value >= 1 for value in counts.values())}


def run_backup(config: dict[str, str]) -> dict[str, Any]:
    backup_dir = Path(config["backup_dir"])
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifact = backup_dir / f"{config['database']}_{timestamp}.sql.gz"
    container_path = f"{CONTAINER_BACKUP_DIR}/{artifact.name}"
    command = (
        'mariadb-dump --protocol=socket --user=root --password="$MARIADB_ROOT_PASSWORD" '
        f"--single-transaction --routines --triggers {config['database']} | gzip > {container_path}"
    )
    started = time.monotonic()
    result = compose_exec(command, timeout=120)
    if result.returncode != 0:
        artifact.unlink(missing_ok=True)
        raise dbops.DatabaseError("mariadb-dump falhou")
    if not artifact.exists() or artifact.stat().st_size == 0:
        raise dbops.ValidationError("backup MariaDB vazio ou ausente")
    manifest = write_manifest(artifact, time.monotonic() - started)
    return {
        "artifact": artifact.name,
        "manifest": manifest.name,
        "size_bytes": artifact.stat().st_size,
        "sha256": hash_file(artifact),
        "validated": True,
    }


def resolve_artifact(raw: str, config: dict[str, str]) -> Path:
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = Path(config["backup_dir"]) / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(Path(config["backup_dir"]).resolve())
    except ValueError as exc:
        raise dbops.ValidationError("artefato deve estar dentro de MYSQL_BACKUP_DIR") from exc
    if not candidate.exists():
        raise dbops.ValidationError(f"artefato MariaDB não encontrado: {candidate}")
    return candidate


def verify_backup(artifact: Path) -> dict[str, Any]:
    manifest_file = manifest_path(artifact)
    if not manifest_file.exists():
        raise dbops.ValidationError("manifesto MariaDB ausente")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    actual_hash = hash_file(artifact)
    if manifest.get("sha256") != actual_hash or manifest.get("size_bytes") != artifact.stat().st_size:
        raise dbops.ValidationError("checksum ou tamanho do backup MariaDB não corresponde ao manifesto")
    result = run_compose("exec", "-T", SERVICE, "sh", "-lc", f"gzip -t {CONTAINER_BACKUP_DIR}/{artifact.name}")
    if result.returncode != 0:
        raise dbops.ValidationError("gzip -t rejeitou o backup MariaDB")
    return {"artifact": artifact.name, "sha256": actual_hash, "size_bytes": artifact.stat().st_size, "validated": True}


def run_restore(artifact: Path, config: dict[str, str]) -> dict[str, Any]:
    verify_backup(artifact)
    restore_db = "secondary_restore_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    mariadb_sql(f"CREATE DATABASE {restore_db};")
    command = (
        f"gzip -dc {CONTAINER_BACKUP_DIR}/{artifact.name} | "
        f'mariadb --protocol=socket --user=root --password="$MARIADB_ROOT_PASSWORD" {restore_db}'
    )
    result = compose_exec(command, timeout=120)
    if result.returncode != 0:
        raise dbops.DatabaseError("restore MariaDB falhou")
    tables = mariadb_sql("SHOW TABLES;", database=restore_db).splitlines()
    expected = {"customers", "tickets", "ticket_events"}
    missing = sorted(expected - set(tables))
    if missing:
        raise dbops.ValidationError(f"tabelas ausentes após restore MariaDB: {', '.join(missing)}")
    counts = {}
    for table in sorted(expected):
        counts[table] = int(mariadb_sql(f"SELECT COUNT(*) FROM {table};", database=restore_db) or 0)
    return {"artifact": artifact.name, "target_database": restore_db, "tables": sorted(tables), "counts": counts, "validated": True}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI operacional do MariaDB secundário")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("provision")
    sub.add_parser("health-check")
    sub.add_parser("seed")
    sub.add_parser("backup")
    verify = sub.add_parser("verify-backup")
    verify.add_argument("artifact")
    restore = sub.add_parser("restore")
    restore.add_argument("artifact")
    return parser


def main(argv: list[str] | None = None) -> int:
    dbops.configure_logging()
    try:
        dbops.load_env_file(ROOT_DIR / ".env")
        config = settings()
        args = build_parser().parse_args(argv)
        if args.command == "provision":
            result = run_provision(config)
        elif args.command == "health-check":
            result = run_health_check(config)
        elif args.command == "seed":
            result = run_seed(config)
        elif args.command == "backup":
            result = run_backup(config)
        elif args.command == "verify-backup":
            result = verify_backup(resolve_artifact(args.artifact, config))
        else:
            result = run_restore(resolve_artifact(args.artifact, config), config)
        dbops.log_event(20, "operação MariaDB concluída", **result)
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
        dbops.log_event(40, "erro inesperado na CLI MariaDB", error_type=type(exc).__name__)
        return EXIT_UNEXPECTED


if __name__ == "__main__":
    raise SystemExit(main())
