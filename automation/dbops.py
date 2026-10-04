#!/usr/bin/env python3
"""CLI operacional do DB Operations Lab.

Fases 1 e 2: provisionamento, health check, backup, restore, WAL e PITR do PostgreSQL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT_DIR = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT_DIR / "migrations"

EXIT_OK = 0
EXIT_CONFIG = 2
EXIT_DATABASE = 3
EXIT_VALIDATION = 4
EXIT_UNEXPECTED = 5


class ConfigError(Exception):
    """Indica que a configuração local está incompleta ou inválida."""


class ValidationError(Exception):
    """Indica que o banco respondeu, mas não atende aos checks esperados."""


class DatabaseError(Exception):
    """Indica uma falha de conexão ou operação no PostgreSQL."""


class JsonFormatter(logging.Formatter):
    """Formata cada evento de log como uma linha JSON sem dados sensíveis."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if hasattr(record, "details"):
            payload["details"] = getattr(record, "details")
        return json.dumps(payload, ensure_ascii=True, sort_keys=True)


LOGGER = logging.getLogger("dbops")


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    LOGGER.handlers.clear()
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False


def log_event(level: int, message: str, **details: Any) -> None:
    LOGGER.log(level, message, extra={"details": details})


def load_env_file(path: Path) -> None:
    """Carrega um .env simples sem sobrescrever variáveis já exportadas."""

    if not path.exists():
        return

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ConfigError(f"Linha inválida no arquivo de ambiente: {path}:{line_number}")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"Variável obrigatória ausente: {name}")
    return value


def integer_env(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ConfigError(f"Variável {name} deve ser um inteiro") from exc
    if value < 0:
        raise ConfigError(f"Variável {name} não pode ser negativa")
    return value


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    database: str
    admin_user: str
    admin_password: str
    app_user: str
    app_password: str
    operator_user: str
    operator_password: str
    readonly_user: str
    readonly_password: str
    monitor_user: str
    monitor_password: str
    data_path: Path
    min_free_mb: int
    backup_dir: Path
    backup_user: str
    backup_password: str
    physical_backup_dir: Path

    @classmethod
    def from_environment(cls) -> "Settings":
        port = integer_env("POSTGRES_PORT", 5432)
        if not 1 <= port <= 65535:
            raise ConfigError("POSTGRES_PORT deve estar entre 1 e 65535")
        return cls(
            host=os.getenv("POSTGRES_HOST", "127.0.0.1").strip(),
            port=port,
            database=required_env("POSTGRES_DB"),
            admin_user=required_env("POSTGRES_USER"),
            admin_password=required_env("POSTGRES_PASSWORD"),
            app_user=required_env("POSTGRES_APP_USER"),
            app_password=required_env("POSTGRES_APP_PASSWORD"),
            operator_user=required_env("POSTGRES_OPERATOR_USER"),
            operator_password=required_env("POSTGRES_OPERATOR_PASSWORD"),
            readonly_user=required_env("POSTGRES_READONLY_USER"),
            readonly_password=required_env("POSTGRES_READONLY_PASSWORD"),
            monitor_user=required_env("POSTGRES_MONITOR_USER"),
            monitor_password=required_env("POSTGRES_MONITOR_PASSWORD"),
            data_path=Path(os.getenv("DBOPS_DATA_PATH", ".")).resolve(),
            min_free_mb=integer_env("DBOPS_MIN_FREE_MB", 512),
            backup_dir=resolve_project_path(
                os.getenv("POSTGRES_BACKUP_DIR", "postgres/backup/artifacts")
            ),
            backup_user=required_env("POSTGRES_BACKUP_USER"),
            backup_password=required_env("POSTGRES_BACKUP_PASSWORD"),
            physical_backup_dir=resolve_project_path(
                os.getenv("POSTGRES_PHYSICAL_BACKUP_DIR", "postgres/backup/physical")
            ),
        )

    def connection_kwargs(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.admin_user,
            "password": self.admin_password,
            "connect_timeout": 5,
        }

    def roles(self) -> list[tuple[str, str]]:
        return [
            (self.app_user, self.app_password),
            (self.operator_user, self.operator_password),
            (self.readonly_user, self.readonly_password),
            (self.monitor_user, self.monitor_password),
            (self.backup_user, self.backup_password),
        ]


def import_psycopg() -> Any:
    try:
        import psycopg
    except ImportError as exc:
        raise ConfigError(
            "Dependência ausente: instale automation/requirements.txt em um ambiente virtual"
        ) from exc
    return psycopg


def resolve_project_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path.resolve()


def sql_identifier(sql_module: Any, value: str) -> Any:
    return sql_module.Identifier(value)


def ensure_role(
    conn: Any,
    sql_module: Any,
    role_name: str,
    password: str,
    *,
    replication: bool = False,
) -> None:
    role_exists = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s)", (role_name,)
    ).fetchone()[0]
    role_identifier = sql_identifier(sql_module, role_name)
    password_literal = sql_module.Literal(password)
    replication_attribute = "REPLICATION" if replication else "NOREPLICATION"
    if role_exists:
        conn.execute(
            sql_module.SQL(
                "ALTER ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE {} PASSWORD {}"
            ).format(role_identifier, sql_module.SQL(replication_attribute), password_literal)
        )
        return
    conn.execute(
        sql_module.SQL(
            "CREATE ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE {} PASSWORD {}"
        ).format(role_identifier, sql_module.SQL(replication_attribute), password_literal)
    )


def grant_permissions(conn: Any, sql_module: Any, settings: Settings) -> None:
    database_identifier = sql_identifier(sql_module, settings.database)
    app_identifier = sql_identifier(sql_module, settings.app_user)
    operator_identifier = sql_identifier(sql_module, settings.operator_user)
    readonly_identifier = sql_identifier(sql_module, settings.readonly_user)
    monitor_identifier = sql_identifier(sql_module, settings.monitor_user)

    conn.execute(sql_module.SQL("GRANT CONNECT ON DATABASE {} TO {}, {}, {}, {}").format(
        database_identifier,
        app_identifier,
        operator_identifier,
        readonly_identifier,
        monitor_identifier,
    ))
    conn.execute(sql_module.SQL("GRANT USAGE ON SCHEMA public TO {}, {}, {}, {}").format(
        app_identifier,
        operator_identifier,
        readonly_identifier,
        monitor_identifier,
    ))
    conn.execute(sql_module.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(app_identifier))
    conn.execute(sql_module.SQL("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {}").format(operator_identifier))
    conn.execute(sql_module.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(readonly_identifier))
    conn.execute(sql_module.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}, {}").format(app_identifier, operator_identifier))
    conn.execute(sql_module.SQL("GRANT pg_monitor TO {}").format(monitor_identifier))

    conn.execute(sql_module.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}").format(app_identifier))
    conn.execute(sql_module.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO {}").format(operator_identifier))
    conn.execute(sql_module.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {}").format(readonly_identifier))
    conn.execute(sql_module.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {}, {}").format(app_identifier, operator_identifier))


CONTAINER_BACKUP_DIR = "/var/lib/postgresql/backups"
EXPECTED_RESTORE_TABLES = {"customers", "tickets", "ticket_events", "schema_migrations"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_path(artifact: Path) -> Path:
    return artifact.with_name(f"{artifact.name}.manifest.json")


def write_manifest(artifact: Path, artifact_type: str, settings: Settings) -> Path:
    manifest = {
        "artifact": artifact.name,
        "artifact_type": artifact_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "database": settings.database,
        "engine": "postgresql",
        "sha256": sha256_file(artifact),
        "size_bytes": artifact.stat().st_size,
    }
    output = manifest_path(artifact)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def directory_sha256(root: Path) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    file_count = 0
    total_bytes = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(relative)
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
                total_bytes += len(chunk)
        file_count += 1
    return digest.hexdigest(), file_count, total_bytes


def directory_manifest_path(artifact_dir: Path) -> Path:
    return artifact_dir.with_name(f"{artifact_dir.name}.manifest.json")


def write_directory_manifest(artifact_dir: Path, settings: Settings) -> Path:
    tree_sha256, file_count, total_bytes = directory_sha256(artifact_dir)
    manifest = {
        "artifact": artifact_dir.name,
        "artifact_type": "physical",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "database": settings.database,
        "engine": "postgresql",
        "file_count": file_count,
        "sha256": tree_sha256,
        "size_bytes": total_bytes,
    }
    output = directory_manifest_path(artifact_dir)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def resolve_artifact(raw_path: str, settings: Settings) -> Path:
    raw = Path(raw_path)
    if raw.is_absolute():
        candidate = raw.resolve()
    elif len(raw.parts) == 1:
        candidate = (settings.backup_dir / raw).resolve()
    else:
        candidate = (ROOT_DIR / raw).resolve()
    try:
        candidate.relative_to(settings.backup_dir)
    except ValueError as exc:
        raise ValidationError("O artefato deve estar dentro de POSTGRES_BACKUP_DIR") from exc
    if not candidate.exists():
        raise ValidationError(f"Artefato não encontrado: {candidate}")
    return candidate


def resolve_physical_artifact(raw_path: str, settings: Settings) -> Path:
    raw = Path(raw_path)
    if raw.is_absolute():
        candidate = raw.resolve()
    elif len(raw.parts) == 1:
        candidate = (settings.physical_backup_dir / raw).resolve()
    else:
        candidate = (ROOT_DIR / raw).resolve()
    try:
        candidate.relative_to(settings.physical_backup_dir)
    except ValueError as exc:
        raise ValidationError("O backup físico deve estar dentro de POSTGRES_PHYSICAL_BACKUP_DIR") from exc
    if not candidate.exists() or not candidate.is_dir():
        raise ValidationError(f"Diretório de backup físico não encontrado: {candidate}")
    return candidate


def container_artifact_path(artifact: Path, settings: Settings) -> str:
    relative = artifact.relative_to(settings.backup_dir).as_posix()
    return f"{CONTAINER_BACKUP_DIR}/{relative}"


def docker_exec_command(inner_command: str) -> list[str]:
    return ["docker", "compose", "exec", "-T", "postgres", "sh", "-lc", inner_command]


def run_external(
    command: list[str],
    *,
    stdout: Any = subprocess.PIPE,
    environment: dict[str, str] | None = None,
    timeout_seconds: float | None = None,
) -> subprocess.CompletedProcess[Any]:
    try:
        return subprocess.run(
            command,
            cwd=ROOT_DIR,
            stdout=stdout,
            stderr=subprocess.PIPE,
            check=False,
            env=environment,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(command, 124, stdout=b"", stderr=b"timeout")
    except OSError as exc:
        raise DatabaseError(f"não foi possível executar ferramenta externa ({type(exc).__name__})") from exc


def run_logical_backup(settings: Settings) -> Path:
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifact = settings.backup_dir / f"{settings.database}_{timestamp}.dump"
    host_pg_dump = shutil.which(os.getenv("PG_DUMP_BIN", "pg_dump"))
    if host_pg_dump:
        command = [
            host_pg_dump,
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--file=-",
            "--host",
            settings.host,
            "--port",
            str(settings.port),
            "--username",
            settings.admin_user,
            "--dbname",
            settings.database,
        ]
        environment = os.environ.copy()
        environment["PGPASSWORD"] = settings.admin_password
    else:
        container_artifact = f"{CONTAINER_BACKUP_DIR}/{artifact.name}"
        inner = (
            "PGPASSWORD=\"$POSTGRES_PASSWORD\" pg_dump --format=custom "
            f"--no-owner --no-privileges --file={shlex.quote(str(container_artifact))} "
            f"--username=\"$POSTGRES_USER\" --dbname={shlex.quote(settings.database)}"
        )
        command = docker_exec_command(inner)
        environment = os.environ.copy()

    if host_pg_dump:
        with artifact.open("wb") as output:
            result = run_external(command, stdout=output, environment=environment)
    else:
        result = run_external(command, environment=environment)
    if result.returncode != 0:
        artifact.unlink(missing_ok=True)
        raise DatabaseError(f"pg_dump falhou com código {result.returncode}")
    if not artifact.exists() or artifact.stat().st_size == 0:
        artifact.unlink(missing_ok=True)
        raise DatabaseError("pg_dump produziu um artefato vazio")
    write_manifest(artifact, "logical", settings)
    return artifact


def run_physical_backup(settings: Settings) -> Path:
    settings.physical_backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifact_dir = settings.physical_backup_dir / f"{settings.database}_{timestamp}"
    artifact_dir.mkdir(parents=True, exist_ok=False)
    host_pg_basebackup = shutil.which(os.getenv("PG_BASEBACKUP_BIN", "pg_basebackup"))
    if host_pg_basebackup:
        command = [
            host_pg_basebackup,
            "--host",
            settings.host,
            "--port",
            str(settings.port),
            "--username",
            settings.backup_user,
            "--pgdata",
            str(artifact_dir),
            "--format=plain",
            "--wal-method=stream",
            "--progress",
        ]
        environment = os.environ.copy()
        environment["PGPASSWORD"] = settings.backup_password
    else:
        container_target = f"/var/lib/postgresql/physical_backups/{artifact_dir.name}"
        inner = (
            "PGPASSWORD=\"$POSTGRES_BACKUP_PASSWORD\" pg_basebackup "
            "--host=127.0.0.1 --port=5432 --username=\"$POSTGRES_BACKUP_USER\" "
            f"--pgdata={shlex.quote(container_target)} --format=plain --wal-method=stream --progress"
        )
        command = docker_exec_command(inner)
        environment = os.environ.copy()

    result = run_external(command, environment=environment)
    if result.returncode != 0:
        shutil.rmtree(artifact_dir, ignore_errors=True)
        raise DatabaseError(f"pg_basebackup falhou com código {result.returncode}")
    backup_manifest = artifact_dir / "backup_manifest"
    if not backup_manifest.exists() or backup_manifest.stat().st_size == 0:
        shutil.rmtree(artifact_dir, ignore_errors=True)
        raise DatabaseError("pg_basebackup não produziu backup_manifest válido")
    write_directory_manifest(artifact_dir, settings)
    return artifact_dir


def record_backup_status(
    settings: Settings,
    backup_type: str,
    *,
    success: bool,
    artifact: str | None,
    duration_seconds: float,
    size_bytes: int | None,
    error_type: str | None = None,
) -> None:
    """Registra a última tentativa para observabilidade sem mascarar a falha original."""

    if backup_type not in {"logical", "physical"}:
        raise ValidationError(f"tipo de backup inválido para telemetria: {backup_type}")
    psycopg = import_psycopg()
    try:
        with psycopg.connect(**settings.connection_kwargs()) as conn:
            conn.autocommit = True
            conn.execute(
                """
                INSERT INTO public.dbops_backup_status (backup_type, last_attempt_at)
                VALUES (%s, clock_timestamp())
                ON CONFLICT (backup_type) DO NOTHING
                """,
                (backup_type,),
            )
            if success:
                conn.execute(
                    """
                    UPDATE public.dbops_backup_status
                    SET last_attempt_at = clock_timestamp(),
                        last_success_at = clock_timestamp(),
                        last_artifact = %s,
                        last_duration_seconds = %s,
                        last_size_bytes = %s,
                        last_error_type = NULL
                    WHERE backup_type = %s
                    """,
                    (artifact, duration_seconds, size_bytes, backup_type),
                )
            else:
                conn.execute(
                    """
                    UPDATE public.dbops_backup_status
                    SET last_attempt_at = clock_timestamp(),
                        last_failure_at = clock_timestamp(),
                        last_artifact = %s,
                        last_duration_seconds = %s,
                        last_size_bytes = %s,
                        failure_count = failure_count + 1,
                        last_error_type = %s
                    WHERE backup_type = %s
                    """,
                    (artifact, duration_seconds, size_bytes, error_type, backup_type),
                )
    except Exception as exc:  # noqa: BLE001 - telemetria não pode esconder falha do backup
        log_event(
            logging.WARNING,
            "não foi possível registrar status do backup",
            backup_type=backup_type,
            status_error_type=type(exc).__name__,
        )


def verify_logical_backup(artifact: Path, settings: Settings) -> dict[str, Any]:
    manifest_file = manifest_path(artifact)
    if not manifest_file.exists():
        raise ValidationError(f"Manifesto ausente: {manifest_file}")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    actual_size = artifact.stat().st_size
    actual_sha256 = sha256_file(artifact)
    if manifest.get("size_bytes") != actual_size:
        raise ValidationError("Tamanho do artefato não corresponde ao manifesto")
    if manifest.get("sha256") != actual_sha256:
        raise ValidationError("SHA-256 do artefato não corresponde ao manifesto")

    host_pg_restore = shutil.which(os.getenv("PG_RESTORE_BIN", "pg_restore"))
    if host_pg_restore:
        command = [host_pg_restore, "--list", str(artifact)]
    else:
        command = docker_exec_command(
            f"pg_restore --list {shlex.quote(str(container_artifact_path(artifact, settings)))}"
        )
    result = run_external(command, environment=os.environ.copy())
    if result.returncode != 0:
        raise ValidationError(f"pg_restore --list falhou com código {result.returncode}")
    return {
        "artifact": artifact.name,
        "manifest": manifest_file.name,
        "sha256": actual_sha256,
        "size_bytes": actual_size,
        "validated": True,
    }


def verify_physical_backup(artifact_dir: Path, settings: Settings) -> dict[str, Any]:
    manifest_file = directory_manifest_path(artifact_dir)
    if not manifest_file.exists():
        raise ValidationError(f"Manifesto físico ausente: {manifest_file}")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    actual_sha256, actual_file_count, actual_size = directory_sha256(artifact_dir)
    if manifest.get("file_count") != actual_file_count:
        raise ValidationError("Quantidade de arquivos não corresponde ao manifesto físico")
    if manifest.get("size_bytes") != actual_size:
        raise ValidationError("Tamanho do backup físico não corresponde ao manifesto")
    if manifest.get("sha256") != actual_sha256:
        raise ValidationError("SHA-256 do backup físico não corresponde ao manifesto")

    command = docker_exec_command(
        f"pg_verifybackup {shlex.quote('/var/lib/postgresql/physical_backups/' + artifact_dir.name)}"
    )
    result = run_external(command, environment=os.environ.copy())
    if result.returncode != 0:
        raise ValidationError(f"pg_verifybackup falhou com código {result.returncode}")
    return {
        "artifact": artifact_dir.name,
        "manifest": manifest_file.name,
        "sha256": actual_sha256,
        "size_bytes": actual_size,
        "file_count": actual_file_count,
        "validated": True,
    }


def create_restore_database(settings: Settings, target_database: str) -> None:
    if target_database == settings.database or not target_database.startswith("dbops_restore_"):
        raise ValidationError("O banco de restore deve usar o prefixo dbops_restore_ e ser diferente do banco principal")
    psycopg = import_psycopg()
    try:
        with psycopg.connect(**settings.connection_kwargs()) as conn:
            conn.autocommit = True
            exists = conn.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = %s)",
                (target_database,),
            ).fetchone()[0]
            if exists:
                raise ValidationError(f"Banco de restore já existe: {target_database}")
            conn.execute(psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(target_database)))
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - normaliza erros do driver para a CLI
        raise DatabaseError(f"não foi possível criar banco de restore ({type(exc).__name__})") from exc


def restore_logical_backup(artifact: Path, settings: Settings, target_database: str) -> dict[str, Any]:
    verify_logical_backup(artifact, settings)
    create_restore_database(settings, target_database)
    host_pg_restore = shutil.which(os.getenv("PG_RESTORE_BIN", "pg_restore"))
    if host_pg_restore:
        command = [
            host_pg_restore,
            "--exit-on-error",
            "--no-owner",
            "--no-privileges",
            "--host",
            settings.host,
            "--port",
            str(settings.port),
            "--username",
            settings.admin_user,
            "--dbname",
            target_database,
            str(artifact),
        ]
        environment = os.environ.copy()
        environment["PGPASSWORD"] = settings.admin_password
    else:
        command = docker_exec_command(
            "PGPASSWORD=\"$POSTGRES_PASSWORD\" pg_restore --exit-on-error "
            "--no-owner --no-privileges --host=127.0.0.1 "
            f"--username=\"$POSTGRES_USER\" --dbname={shlex.quote(target_database)} "
            f"{shlex.quote(str(container_artifact_path(artifact, settings)))}"
        )
        environment = os.environ.copy()
    result = run_external(command, environment=environment)
    if result.returncode != 0:
        raise DatabaseError(f"pg_restore falhou com código {result.returncode}")

    psycopg = import_psycopg()
    target_kwargs = settings.connection_kwargs()
    target_kwargs["dbname"] = target_database
    try:
        with psycopg.connect(**target_kwargs) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                )
                tables = {row[0] for row in cursor.fetchall()}
                missing_tables = sorted(EXPECTED_RESTORE_TABLES - tables)
                if missing_tables:
                    raise ValidationError(f"Tabelas ausentes após restore: {', '.join(missing_tables)}")
                cursor.execute("SELECT COUNT(*) FROM public.schema_migrations")
                migrations = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM public.customers")
                customers = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM public.tickets")
                tickets = cursor.fetchone()[0]
    except ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - normaliza erros do driver para a CLI
        raise DatabaseError(f"não foi possível validar banco restaurado ({type(exc).__name__})") from exc
    return {
        "artifact": artifact.name,
        "target_database": target_database,
        "tables": sorted(EXPECTED_RESTORE_TABLES),
        "migrations": migrations,
        "customers": customers,
        "tickets": tickets,
        "validated": True,
    }


def apply_migrations(conn: Any, migration_paths: Iterable[Path]) -> list[str]:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS public.schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    applied: list[str] = []
    for migration_path in migration_paths:
        version = migration_path.name
        already_applied = conn.execute(
            "SELECT EXISTS (SELECT 1 FROM public.schema_migrations WHERE version = %s)",
            (version,),
        ).fetchone()[0]
        if already_applied:
            continue
        with conn.transaction():
            conn.execute(migration_path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO public.schema_migrations (version) VALUES (%s)", (version,))
        applied.append(version)
    return applied


def migration_paths() -> list[Path]:
    if not MIGRATIONS_DIR.exists():
        raise ValidationError(f"Diretório de migrations ausente: {MIGRATIONS_DIR}")
    paths = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not paths:
        raise ValidationError("Nenhuma migration .sql encontrada")
    return paths


def run_provision(settings: Settings) -> None:
    psycopg = import_psycopg()
    try:
        with psycopg.connect(**settings.connection_kwargs()) as conn:
            conn.autocommit = True
            for role_name, password in settings.roles():
                ensure_role(
                    conn,
                    psycopg.sql,
                    role_name,
                    password,
                    replication=role_name == settings.backup_user,
                )
            applied = apply_migrations(conn, migration_paths())
            grant_permissions(conn, psycopg.sql, settings)
    except (ConfigError, ValidationError):
        raise
    except Exception as exc:  # noqa: BLE001 - normaliza erros do driver para a CLI
        raise DatabaseError(
            f"falha durante o provisionamento PostgreSQL ({type(exc).__name__})"
        ) from exc
    log_event(logging.INFO, "provisionamento concluído", migrations_applied=applied, roles=len(settings.roles()))


def run_health_check(settings: Settings) -> None:
    if not settings.data_path.exists():
        raise ValidationError(f"Caminho de dados não existe: {settings.data_path}")
    disk = shutil.disk_usage(settings.data_path)
    free_mb = disk.free // (1024 * 1024)
    if free_mb < settings.min_free_mb:
        raise ValidationError(f"Espaço livre abaixo do mínimo: {free_mb} MB < {settings.min_free_mb} MB")

    psycopg = import_psycopg()
    try:
        with psycopg.connect(**settings.connection_kwargs()) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT version(), current_database(), current_user, pg_database_size(current_database())"
                )
                version, database, user, database_size = cursor.fetchone()
                cursor.execute(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                )
                table_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM public.schema_migrations")
                migration_count = cursor.fetchone()[0]
                cursor.execute(
                    "SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)",
                    ([role_name for role_name, _ in settings.roles()],),
                )
                existing_roles = {row[0] for row in cursor.fetchall()}
    except Exception as exc:  # noqa: BLE001 - normaliza erros do driver para a CLI
        raise DatabaseError(
            f"falha durante o health-check PostgreSQL ({type(exc).__name__})"
        ) from exc

    expected_roles = {role_name for role_name, _ in settings.roles()}
    missing_roles = sorted(expected_roles - existing_roles)
    if missing_roles:
        raise ValidationError(f"Roles ausentes: {', '.join(missing_roles)}")
    if migration_count == 0:
        raise ValidationError("Nenhuma migration registrada")

    log_event(
        logging.INFO,
        "health-check aprovado",
        database=database,
        database_size_bytes=database_size,
        database_user=user,
        free_disk_mb=free_mb,
        migrations=migration_count,
        tables=table_count,
        postgres_version=version.splitlines()[0],
    )


def run_wal_status(settings: Settings) -> None:
    psycopg = import_psycopg()
    try:
        with psycopg.connect(**settings.connection_kwargs()) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT pg_switch_wal()")
                switch_lsn = cursor.fetchone()[0]
                deadline = time.monotonic() + 10
                archive_row: tuple[Any, ...] | None = None
                while time.monotonic() < deadline:
                    cursor.execute(
                        "SELECT archived_count, failed_count, last_archived_wal, last_failed_wal FROM pg_stat_archiver"
                    )
                    archive_row = cursor.fetchone()
                    if archive_row and archive_row[2]:
                        break
                    time.sleep(1)
                cursor.execute(
                    "SELECT name, setting FROM pg_settings WHERE name IN ('archive_mode', 'archive_command', 'wal_level') ORDER BY name"
                )
                settings_rows = dict(cursor.fetchall())
    except Exception as exc:  # noqa: BLE001 - normaliza erros do driver para a CLI
        raise DatabaseError(f"falha ao consultar WAL/archiver ({type(exc).__name__})") from exc

    archived_count, failed_count, last_archived_wal, last_failed_wal = archive_row or (0, 0, None, None)
    wal_files = 0
    if Path(ROOT_DIR / "postgres/backup/wal").exists():
        wal_files = sum(1 for path in (ROOT_DIR / "postgres/backup/wal").iterdir() if path.is_file())
    if not settings_rows.get("archive_mode") == "on":
        raise ValidationError("archive_mode não está on")
    if not last_archived_wal or wal_files == 0:
        raise ValidationError("nenhum WAL foi arquivado após pg_switch_wal")
    log_event(
        logging.INFO,
        "WAL archiving validado",
        archive_command_configured=bool(settings_rows.get("archive_command")),
        archived_count=archived_count,
        failed_count=failed_count,
        last_archived_wal=last_archived_wal,
        last_failed_wal=last_failed_wal,
        wal_files=wal_files,
        wal_level=settings_rows.get("wal_level"),
        switch_lsn=str(switch_lsn),
    )


def latest_physical_backup(settings: Settings) -> Path:
    candidates = [
        path
        for path in settings.physical_backup_dir.iterdir()
        if path.is_dir() and (path / "backup_manifest").exists()
    ] if settings.physical_backup_dir.exists() else []
    if not candidates:
        raise ValidationError("Nenhum backup físico com backup_manifest foi encontrado")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def create_pitr_markers(settings: Settings) -> dict[str, Any]:
    """Cria dados sintéticos antes/depois do alvo temporal do PITR."""

    psycopg = import_psycopg()
    marker = uuid.uuid4().hex
    customer_email = f"pitr-{marker}@example.invalid"
    try:
        with psycopg.connect(**settings.connection_kwargs()) as conn:
            conn.autocommit = True
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO public.customers (full_name, email) VALUES (%s, %s) RETURNING customer_id",
                    (f"PITR Test {marker[:12]}", customer_email),
                )
                customer_id = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT INTO public.tickets (customer_id, subject) VALUES (%s, %s) RETURNING ticket_id",
                    (customer_id, f"PITR incident {marker[:12]}"),
                )
                ticket_id = cursor.fetchone()[0]
                cursor.execute(
                    """
                    INSERT INTO public.ticket_events (ticket_id, event_type, event_payload)
                    VALUES (%s, 'pitr_before_incident', jsonb_build_object('pitr_marker', %s::text, 'phase', 'before'))
                    RETURNING created_at
                    """,
                    (ticket_id, marker),
                )
                before_created_at = cursor.fetchone()[0]
                cursor.execute("SELECT clock_timestamp()")
                target_time = cursor.fetchone()[0]
                cursor.execute(
                    """
                    INSERT INTO public.ticket_events (ticket_id, event_type, event_payload)
                    VALUES (%s, 'pitr_after_incident', jsonb_build_object('pitr_marker', %s::text, 'phase', 'after'))
                    RETURNING created_at
                    """,
                    (ticket_id, marker),
                )
                incident_created_at = cursor.fetchone()[0]
                cursor.execute("SELECT pg_switch_wal()")
                switch_lsn = cursor.fetchone()[0]
    except Exception as exc:  # noqa: BLE001 - normaliza erros do driver para a CLI
        raise DatabaseError(f"falha ao criar marcadores sintéticos do PITR ({type(exc).__name__})") from exc

    return {
        "marker": marker,
        "customer_email": customer_email,
        "customer_id": customer_id,
        "ticket_id": ticket_id,
        "before_created_at": before_created_at,
        "target_time": target_time,
        "incident_created_at": incident_created_at,
        "switch_lsn": str(switch_lsn),
    }


def cleanup_pitr_markers(settings: Settings, marker_data: dict[str, Any]) -> None:
    psycopg = import_psycopg()
    try:
        with psycopg.connect(**settings.connection_kwargs()) as conn:
            conn.autocommit = True
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM public.ticket_events WHERE event_payload->>'pitr_marker' = %s",
                    (marker_data["marker"],),
                )
                cursor.execute("DELETE FROM public.tickets WHERE ticket_id = %s", (marker_data["ticket_id"],))
                cursor.execute("DELETE FROM public.customers WHERE customer_id = %s", (marker_data["customer_id"],))
    except Exception as exc:  # noqa: BLE001 - normaliza erros do driver para a CLI
        raise DatabaseError(f"falha ao limpar marcadores sintéticos do PITR ({type(exc).__name__})") from exc


def prepare_pitr_recovery_directory(
    settings: Settings,
    base_backup: Path,
    target_time: datetime,
    run_id: str,
) -> Path:
    recovery_root = ROOT_DIR / "postgres" / "recovery"
    recovery_root.mkdir(parents=True, exist_ok=True)
    recovery_dir = recovery_root / f"pitr_{run_id}"
    if recovery_dir.exists():
        raise ValidationError(f"Diretório de recuperação já existe: {recovery_dir}")
    shutil.copytree(base_backup, recovery_dir)
    target_value = target_time.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f+00")
    (recovery_dir / "postgresql.auto.conf").write_text(
        "# Gerado pela CLI dbops.py para teste PITR; não usar como configuração de produção.\n"
        "restore_command = 'cp /var/lib/postgresql/recovery_wal/%f %p'\n"
        f"recovery_target_time = '{target_value}'\n"
        "recovery_target_action = 'promote'\n"
        "recovery_target_inclusive = false\n",
        encoding="utf-8",
    )
    (recovery_dir / "recovery.signal").write_text("", encoding="utf-8")
    return recovery_dir


def recovery_container_logs(container_name: str) -> str:
    result = run_external(["docker", "logs", "--tail", "80", container_name])
    output = result.stdout or b""
    error = result.stderr or b""
    if isinstance(output, bytes):
        output = output.decode("utf-8", errors="replace")
    if isinstance(error, bytes):
        error = error.decode("utf-8", errors="replace")
    return f"{output}{error}"[-12000:]


def wait_for_recovery_container(container_name: str, settings: Settings, timeout_seconds: int = 45) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        recovery_state = run_external(
            [
                "docker",
                "exec",
                "-u",
                "postgres",
                container_name,
                "psql",
                f"--username={settings.admin_user}",
                f"--dbname={settings.database}",
                "--no-psqlrc",
                "--tuples-only",
                "--no-align",
                "--command=SELECT pg_is_in_recovery();",
            ],
            timeout_seconds=3,
        )
        state_output = (recovery_state.stdout or b"").decode("utf-8", errors="replace").strip()
        if recovery_state.returncode == 0 and state_output == "f":
            return
        state = run_external(["docker", "inspect", "--format={{.State.Running}}", container_name])
        state_output = (state.stdout or b"").decode("utf-8", errors="replace").strip()
        if state.returncode != 0 or state_output != "true":
            logs = recovery_container_logs(container_name)
            raise DatabaseError(f"container PITR encerrou antes de ficar pronto; logs: {logs}")
        time.sleep(1)
    logs = recovery_container_logs(container_name)
    raise DatabaseError(f"timeout aguardando container PITR; logs: {logs}")


def validate_pitr_recovery(container_name: str, settings: Settings, marker: str) -> dict[str, Any]:
    query = (
        "SELECT COUNT(*) FILTER (WHERE event_type = 'pitr_before_incident'), "
        "COUNT(*) FILTER (WHERE event_type = 'pitr_after_incident'), "
        "pg_is_in_recovery() "
        "FROM public.ticket_events "
        "WHERE event_payload->>'pitr_marker' = %s"
    )
    marker_sql = marker.replace("'", "''")
    command = [
        "docker",
        "exec",
        "-u",
        "postgres",
        container_name,
        "psql",
        f"--username={settings.admin_user}",
        f"--dbname={settings.database}",
        "--no-psqlrc",
        "--tuples-only",
        "--no-align",
        "--command",
        query.replace("%s", f"'{marker_sql}'"),
    ]
    result = run_external(command)
    if result.returncode != 0:
        error = (result.stderr or b"").decode("utf-8", errors="replace")
        raise DatabaseError(f"falha ao consultar banco recuperado ({error.strip()})")
    output = (result.stdout or b"").decode("utf-8", errors="replace").strip()
    parts = output.split("|")
    if len(parts) != 3:
        raise ValidationError(f"resposta inesperada na validação PITR: {output}")
    before_count, after_count, in_recovery = parts
    if before_count != "1" or after_count != "0":
        raise ValidationError(
            "PITR não parou no ponto esperado: "
            f"before_count={before_count}, after_count={after_count}"
        )
    if in_recovery.lower() != "f":
        raise ValidationError("cluster recuperado não foi promovido após atingir o alvo PITR")
    return {
        "before_marker_count": int(before_count),
        "after_marker_count": int(after_count),
        "recovery_in_progress": False,
        "validated": True,
    }


def run_pitr(
    settings: Settings,
    base_artifact: str | None = None,
    *,
    cleanup: bool = False,
    keep_recovery: bool = False,
) -> dict[str, Any]:
    base_backup = (
        resolve_physical_artifact(base_artifact, settings)
        if base_artifact
        else latest_physical_backup(settings)
    )
    verify_physical_backup(base_backup, settings)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    container_name = f"dbops_pitr_{run_id.lower()}"
    marker_data = create_pitr_markers(settings)
    recovery_dir: Path | None = None
    started_at = time.monotonic()
    success = False
    try:
        run_wal_status(settings)
        recovery_dir = prepare_pitr_recovery_directory(
            settings,
            base_backup,
            marker_data["target_time"],
            run_id,
        )
        wal_dir = ROOT_DIR / "postgres" / "backup" / "wal"
        image = os.getenv("POSTGRES_IMAGE", "postgres:16.4-alpine")
        command = [
            "docker",
            "run",
            "--detach",
            "--name",
            container_name,
            "--mount",
            f"type=bind,source={recovery_dir},target=/var/lib/postgresql/data",
            "--mount",
            f"type=bind,source={wal_dir.resolve()},target=/var/lib/postgresql/recovery_wal,readonly",
            image,
            "postgres",
        ]
        start_result = run_external(command)
        if start_result.returncode != 0:
            error = (start_result.stderr or b"").decode("utf-8", errors="replace")
            raise DatabaseError(f"não foi possível iniciar container PITR ({error.strip()})")
        wait_for_recovery_container(container_name, settings)
        validation = validate_pitr_recovery(container_name, settings, marker_data["marker"])
        duration_seconds = round(time.monotonic() - started_at, 3)
        result = {
            "base_backup": base_backup.name,
            "container": container_name,
            "target_time": marker_data["target_time"].isoformat(),
            "incident_time": marker_data["incident_created_at"].isoformat(),
            "marker": marker_data["marker"],
            "switch_lsn": marker_data["switch_lsn"],
            "duration_seconds": duration_seconds,
            "recovery_directory": str(recovery_dir.relative_to(ROOT_DIR)),
            **validation,
        }
        success = True
        if cleanup:
            cleanup_pitr_markers(settings, marker_data)
            result["source_markers_cleaned"] = True
        else:
            result["source_markers_cleaned"] = False
        evidence_dir = ROOT_DIR / "evidence" / "phase-0"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        result_path = evidence_dir / f"pitr-result-{run_id}.json"
        result["evidence_file"] = str(result_path.relative_to(ROOT_DIR))
        result_path.write_text(
            json.dumps(result, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return result
    finally:
        remove_result = run_external(["docker", "rm", "--force", container_name])
        if remove_result.returncode not in {0, 1}:
            log_event(logging.WARNING, "não foi possível remover container PITR", container=container_name)
        if success and recovery_dir and not keep_recovery:
            shutil.rmtree(recovery_dir, ignore_errors=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI operacional do DB Operations Lab")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("provision", help="cria roles, permissões e migrations")
    subparsers.add_parser("health-check", help="valida conectividade, roles, migrations e espaço")
    backup_parser = subparsers.add_parser("backup", help="gera backup PostgreSQL")
    backup_parser.add_argument(
        "--type",
        choices=("logical", "physical", "both"),
        default="logical",
        help="tipo de backup; o padrão é logical",
    )
    verify_parser = subparsers.add_parser("verify-backup", help="valida manifesto, checksum e conteúdo do backup")
    verify_parser.add_argument("artifact", help="nome ou caminho do arquivo .dump")
    subparsers.add_parser("wal-status", help="força troca de WAL e valida arquivamento")
    pitr_parser = subparsers.add_parser("pitr", help="executa PITR em container PostgreSQL separado")
    pitr_parser.add_argument(
        "--base-artifact",
        help="nome ou caminho do backup físico; por padrão usa o backup físico mais recente",
    )
    pitr_parser.add_argument(
        "--cleanup",
        action="store_true",
        help="remove os registros sintéticos criados no banco principal após a validação",
    )
    pitr_parser.add_argument(
        "--keep-recovery",
        action="store_true",
        help="preserva o diretório do cluster recuperado para inspeção",
    )
    restore_parser = subparsers.add_parser("restore", help="restaura backup em banco isolado")
    restore_parser.add_argument("artifact", help="nome ou caminho do arquivo .dump")
    restore_parser.add_argument(
        "--target-db",
        help="banco de destino; deve começar com dbops_restore_",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    try:
        args = build_parser().parse_args(argv)
        load_env_file(ROOT_DIR / ".env")
        settings = Settings.from_environment()
        if args.command == "provision":
            run_provision(settings)
        elif args.command == "health-check":
            run_health_check(settings)
        elif args.command == "backup":
            if args.type in {"logical", "both"}:
                started = time.monotonic()
                try:
                    artifact = run_logical_backup(settings)
                except Exception as exc:
                    record_backup_status(
                        settings,
                        "logical",
                        success=False,
                        artifact=None,
                        duration_seconds=time.monotonic() - started,
                        size_bytes=None,
                        error_type=type(exc).__name__,
                    )
                    raise
                record_backup_status(
                    settings,
                    "logical",
                    success=True,
                    artifact=artifact.name,
                    duration_seconds=time.monotonic() - started,
                    size_bytes=artifact.stat().st_size,
                )
                log_event(
                    logging.INFO,
                    "backup lógico concluído",
                    artifact=artifact.name,
                    manifest=manifest_path(artifact).name,
                    sha256=sha256_file(artifact),
                    size_bytes=artifact.stat().st_size,
                )
            if args.type in {"physical", "both"}:
                started = time.monotonic()
                try:
                    physical_artifact = run_physical_backup(settings)
                except Exception as exc:
                    record_backup_status(
                        settings,
                        "physical",
                        success=False,
                        artifact=None,
                        duration_seconds=time.monotonic() - started,
                        size_bytes=None,
                        error_type=type(exc).__name__,
                    )
                    raise
                record_backup_status(
                    settings,
                    "physical",
                    success=True,
                    artifact=physical_artifact.name,
                    duration_seconds=time.monotonic() - started,
                    size_bytes=directory_sha256(physical_artifact)[2],
                )
                log_event(
                    logging.INFO,
                    "backup físico concluído",
                    artifact=physical_artifact.name,
                    manifest=directory_manifest_path(physical_artifact).name,
                    sha256=directory_sha256(physical_artifact)[0],
                    size_bytes=directory_sha256(physical_artifact)[2],
                )
        elif args.command == "verify-backup":
            if args.artifact.endswith(".dump"):
                artifact = resolve_artifact(args.artifact, settings)
                result = verify_logical_backup(artifact, settings)
            else:
                physical_artifact = resolve_physical_artifact(args.artifact, settings)
                result = verify_physical_backup(physical_artifact, settings)
            log_event(logging.INFO, "backup verificado", **result)
        elif args.command == "wal-status":
            run_wal_status(settings)
        elif args.command == "pitr":
            result = run_pitr(
                settings,
                args.base_artifact,
                cleanup=args.cleanup,
                keep_recovery=args.keep_recovery,
            )
            log_event(logging.INFO, "PITR concluído", **result)
        elif args.command == "restore":
            artifact = resolve_artifact(args.artifact, settings)
            target_database = args.target_db or (
                "dbops_restore_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            )
            result = restore_logical_backup(artifact, settings, target_database)
            log_event(logging.INFO, "restore lógico concluído", **result)
        return EXIT_OK
    except ConfigError as exc:
        log_event(logging.ERROR, str(exc))
        return EXIT_CONFIG
    except ValidationError as exc:
        log_event(logging.ERROR, str(exc))
        return EXIT_VALIDATION
    except DatabaseError as exc:
        log_event(logging.ERROR, str(exc))
        return EXIT_DATABASE
    except Exception as exc:  # noqa: BLE001 - fronteira da CLI deve retornar código controlado
        log_event(logging.ERROR, "erro inesperado na CLI", error_type=type(exc).__name__)
        return EXIT_UNEXPECTED


if __name__ == "__main__":
    sys.exit(main())
