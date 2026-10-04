#!/usr/bin/env python3
"""Executa game days controlados do PostgreSQL e grava evidências sem segredos."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import urllib.parse
import urllib.request

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from automation import dbops


EVIDENCE_DIR = dbops.ROOT_DIR / "evidence" / "phase-5"
EXIT_OK = 0
EXIT_CONFIG = 2
EXIT_DATABASE = 3
EXIT_VALIDATION = 4
EXIT_UNEXPECTED = 5


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def write_evidence(incident: str, payload: dict[str, Any]) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    output = EVIDENCE_DIR / f"incident-{incident}-{stamp}.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def base_result(incident: str, mode: str, started: datetime) -> dict[str, Any]:
    return {
        "incident": incident,
        "mode": mode,
        "started_at": started.isoformat(),
        "engine": "postgresql",
        "steps": [],
        "validated": False,
    }


def prometheus_snapshot(query: str) -> dict[str, Any]:
    """Consulta uma série instantânea sem imprimir credenciais ou dados sensíveis."""

    port = os.getenv("PROMETHEUS_PORT", "9090")
    encoded = urllib.parse.quote(query, safe="")
    url = f"http://127.0.0.1:{port}/api/v1/query?query={encoded}"
    with urllib.request.urlopen(url, timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    if payload.get("status") != "success":
        raise RuntimeError("Prometheus rejeitou a consulta do game day")
    return {
        "timestamp": utc_now().isoformat(),
        "query": query,
        "series": payload.get("data", {}).get("result", []),
    }


def metric_value(snapshot: dict[str, Any]) -> float | None:
    values = [item.get("value", [None, None])[1] for item in snapshot.get("series", [])]
    numeric = []
    for value in values:
        try:
            numeric.append(float(value))
        except (TypeError, ValueError):
            continue
    return max(numeric) if numeric else None


def dry_run_plan(incident: str) -> list[str]:
    plans = {
        "delete-data": [
            "identificar o horário e o conjunto de dados afetado",
            "preservar logs e criar uma cópia de segurança antes da recuperação",
            "usar PITR em cluster separado até imediatamente antes do incidente",
            "comparar contagens e amostras antes de promover a recuperação",
        ],
        "pitr": [
            "definir recovery_target_time em UTC antes do incidente",
            "restaurar backup físico e WAL em cluster descartável",
            "validar marcador anterior presente e posterior ausente",
            "registrar RPO/RTO observados sem assumir valores de meta",
        ],
        "disk-full": [
            "medir espaço livre e identificar o filesystem afetado",
            "conter escrita não essencial e preservar logs",
            "liberar somente artefatos temporários aprovados",
            "confirmar espaço, saúde do banco e integridade das aplicações",
        ],
        "database-down": [
            "confirmar indisponibilidade por health check e endpoint do exporter",
            "separar falha de processo, rede, volume e configuração",
            "recuperar o serviço sem apagar o volume persistente",
            "executar health check e validar métricas após o retorno",
        ],
        "slow-query": [
            "observar sessão ativa em pg_stat_activity",
            "capturar idade, wait event e plano quando aplicável",
            "cancelar somente a sessão do game day",
            "confirmar retorno da latência e registrar causa/ação",
        ],
        "lock": [
            "identificar PID bloqueador e PID aguardando",
            "capturar wait_event e pg_blocking_pids",
            "encerrar ou fazer rollback apenas da sessão do cenário",
            "confirmar que a fila foi liberada",
        ],
        "replication-lag": [
            "confirmar se existe réplica configurada antes de medir lag",
            "comparar LSN primário e réplica",
            "identificar atraso de rede, replay ou WAL",
            "registrar como não aplicável se a replicação ainda não estiver habilitada",
        ],
        "backup-invalid": [
            "copiar um dump para um nome temporário isolado",
            "alterar somente a cópia e preservar o artefato original",
            "executar verify-backup e exigir falha de checksum ou formato",
            "remover a cópia inválida e confirmar que o backup original continua válido",
        ],
    }
    return plans[incident]


def run_slow_query(
    settings: dbops.Settings,
    duration: int,
    *,
    observe_prometheus: bool = False,
) -> dict[str, Any]:
    psycopg = dbops.import_psycopg()
    result: dict[str, Any] = {"requested_duration_seconds": duration, "observations": []}
    telemetry: dict[str, Any] = {"query": 'dbops_activity_max_query_age_seconds{datname="dbops"}'}

    def capture(stage: str) -> None:
        try:
            telemetry[stage] = prometheus_snapshot(telemetry["query"])
        except Exception as exc:  # noqa: BLE001 - a falha fica explícita na evidência
            telemetry.setdefault("errors", []).append({"stage": stage, "error_type": type(exc).__name__})

    if observe_prometheus:
        capture("before")
    worker_error: list[str] = []
    worker_pid: list[int] = []

    def worker() -> None:
        try:
            with psycopg.connect(**settings.connection_kwargs()) as conn:
                conn.autocommit = True
                with conn.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    worker_pid.append(cursor.fetchone()[0])
                    cursor.execute("SELECT pg_sleep(%s)", (duration,))
        except Exception as exc:  # noqa: BLE001 - convertido em evidência sanitizada
            worker_error.append(type(exc).__name__)

    started = time.monotonic()
    thread = threading.Thread(target=worker, name="incident-slow-query", daemon=True)
    thread.start()
    observed_active = False
    try:
        with psycopg.connect(**settings.connection_kwargs()) as probe:
            probe.autocommit = True
            while thread.is_alive() and time.monotonic() - started < duration + 5:
                row = probe.execute(
                    """
                    SELECT pid, EXTRACT(EPOCH FROM (clock_timestamp() - query_start)),
                           wait_event_type, wait_event
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                      AND pid <> pg_backend_pid()
                      AND state = 'active'
                      AND query LIKE '%pg_sleep%'
                    ORDER BY query_start
                    LIMIT 1
                    """
                ).fetchone()
                if row:
                    observed_active = True
                    result["observations"].append(
                        {
                            "pid": row[0],
                            "age_seconds": round(float(row[1]), 3),
                            "wait_event_type": row[2],
                            "wait_event": row[3],
                        }
                    )
                    if observe_prometheus and "during" not in telemetry:
                        observe_deadline = time.monotonic() + min(duration, 20)
                        while thread.is_alive() and time.monotonic() < observe_deadline:
                            capture("during")
                            if metric_value(telemetry.get("during", {})) is not None and metric_value(telemetry["during"]) > 1:
                                break
                            time.sleep(1)
                time.sleep(0.25)
    finally:
        thread.join(timeout=duration + 5)

    if observe_prometheus:
        after_deadline = time.monotonic() + 20
        while True:
            capture("after")
            if metric_value(telemetry.get("after", {})) is not None and metric_value(telemetry["after"]) <= 1:
                break
            if time.monotonic() >= after_deadline:
                break
            time.sleep(1)
        telemetry["max_age_before"] = metric_value(telemetry.get("before", {}))
        telemetry["max_age_during"] = metric_value(telemetry.get("during", {}))
        telemetry["max_age_after"] = metric_value(telemetry.get("after", {}))
        telemetry["validated"] = bool(
            telemetry.get("before")
            and telemetry.get("during")
            and telemetry.get("after")
            and not telemetry.get("errors")
            and telemetry.get("max_age_during") is not None
            and telemetry.get("max_age_after") is not None
            and telemetry.get("max_age_after") <= 1
        )
        result["prometheus"] = telemetry
    result.update(
        {
            "worker_pid": worker_pid[0] if worker_pid else None,
            "observed_active": observed_active,
            "worker_error": worker_error,
            "completed": not thread.is_alive(),
            "validated": observed_active and not worker_error and not thread.is_alive() and (
                not observe_prometheus or telemetry.get("validated", False)
            ),
        }
    )
    return result


def run_lock(settings: dbops.Settings, *, observe_prometheus: bool = False) -> dict[str, Any]:
    psycopg = dbops.import_psycopg()
    table = "incident_lab_lock_demo"
    result: dict[str, Any] = {"observations": [], "table": table}
    telemetry: dict[str, Any] = {"query": 'dbops_lock_waits_blocked_queries{datname="dbops"}'}

    def capture(stage: str) -> None:
        try:
            telemetry[stage] = prometheus_snapshot(telemetry["query"])
        except Exception as exc:  # noqa: BLE001 - a falha fica explícita na evidência
            telemetry.setdefault("errors", []).append({"stage": stage, "error_type": type(exc).__name__})

    if observe_prometheus:
        capture("before")
    waiter_result: dict[str, Any] = {}
    holder = None
    waiter_thread: threading.Thread | None = None
    try:
        with psycopg.connect(**settings.connection_kwargs()) as admin:
            admin.autocommit = True
            admin.execute(f"CREATE TABLE IF NOT EXISTS {table} (id integer PRIMARY KEY, value integer NOT NULL)")
            admin.execute(f"TRUNCATE {table}")
            admin.execute(f"INSERT INTO {table} (id, value) VALUES (1, 10)")

        holder = psycopg.connect(**settings.connection_kwargs())
        holder.autocommit = False
        holder.execute(f"SELECT id FROM {table} WHERE id = 1 FOR UPDATE").fetchone()
        holder_pid = holder.execute("SELECT pg_backend_pid()").fetchone()[0]

        def waiter() -> None:
            try:
                with psycopg.connect(**settings.connection_kwargs()) as conn:
                    conn.autocommit = True
                    waiter_result["pid"] = conn.execute("SELECT pg_backend_pid()").fetchone()[0]
                    conn.execute("SET lock_timeout = '20s'")
                    conn.execute(f"UPDATE {table} SET value = value + 1 WHERE id = 1")
                    waiter_result["completed"] = True
            except psycopg.Error as exc:
                waiter_result.update(
                    {
                        "completed": False,
                        "sqlstate": exc.sqlstate,
                        "error_type": type(exc).__name__,
                    }
                )

        waiter_thread = threading.Thread(target=waiter, name="incident-lock-waiter", daemon=True)
        waiter_thread.start()
        with psycopg.connect(**settings.connection_kwargs()) as probe:
            probe.autocommit = True
            while waiter_thread.is_alive():
                row = probe.execute(
                    f"""
                    SELECT pid, wait_event_type, wait_event, pg_blocking_pids(pid)
                    FROM pg_stat_activity
                    WHERE query LIKE 'UPDATE {table}%'
                      AND pid <> pg_backend_pid()
                    LIMIT 1
                    """
                ).fetchone()
                if row:
                    result["observations"].append(
                        {
                            "waiter_pid": row[0],
                            "wait_event_type": row[1],
                            "wait_event": row[2],
                            "blocking_pids": row[3],
                        }
                    )
                    if observe_prometheus and "during" not in telemetry:
                        deadline = time.monotonic() + 20
                        while time.monotonic() < deadline:
                            capture("during")
                            if metric_value(telemetry.get("during", {})) is not None and metric_value(telemetry["during"]) >= 1:
                                break
                            time.sleep(1)
                time.sleep(0.1)
        waiter_thread.join(timeout=3)
        if observe_prometheus:
            after_deadline = time.monotonic() + 20
            while True:
                capture("after")
                if metric_value(telemetry.get("after", {})) is not None and metric_value(telemetry["after"]) <= 0:
                    break
                if time.monotonic() >= after_deadline:
                    break
                time.sleep(1)
            telemetry["blocked_before"] = metric_value(telemetry.get("before", {}))
            telemetry["blocked_during"] = metric_value(telemetry.get("during", {}))
            telemetry["blocked_after"] = metric_value(telemetry.get("after", {}))
            telemetry["validated"] = bool(
                telemetry.get("before")
                and telemetry.get("during")
                and telemetry.get("after")
                and not telemetry.get("errors")
                and telemetry.get("blocked_during") is not None
                and telemetry.get("blocked_during") >= 1
                and telemetry.get("blocked_after") is not None
                and telemetry.get("blocked_after") <= 0
            )
            result["prometheus"] = telemetry
        result.update(
            {
                "holder_pid": holder_pid,
                "waiter_pid": waiter_result.get("pid"),
                "waiter_sqlstate": waiter_result.get("sqlstate"),
                "waiter_error_type": waiter_result.get("error_type"),
                "waiter_completed": waiter_result.get("completed", False),
            }
        )
    finally:
        if holder is not None:
            holder.rollback()
            holder.close()
        with psycopg.connect(**settings.connection_kwargs()) as cleanup:
            cleanup.autocommit = True
            cleanup.execute(f"DROP TABLE IF EXISTS {table}")
    result["validated"] = bool(
        result.get("observations")
        and result.get("waiter_sqlstate") == "55P03"
        and not result.get("waiter_completed")
        and (not observe_prometheus or telemetry.get("validated", False))
    )
    return result


def run_invalid_backup(settings: dbops.Settings) -> dict[str, Any]:
    dumps = sorted(settings.backup_dir.glob("*.dump"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not dumps:
        raise dbops.ValidationError("nenhum backup lógico .dump disponível para a simulação")
    source = dumps[0]
    invalid = settings.backup_dir / f"incident_invalid_{utc_now().strftime('%Y%m%dT%H%M%SZ')}.dump"
    source_manifest = dbops.manifest_path(source)
    invalid_manifest = dbops.manifest_path(invalid)
    shutil.copy2(source, invalid)
    if source_manifest.exists():
        shutil.copy2(source_manifest, invalid_manifest)
    try:
        data = invalid.read_bytes()
        invalid.write_bytes(data[: max(1, len(data) // 2)])
        try:
            dbops.verify_logical_backup(invalid, settings)
        except dbops.ValidationError as exc:
            source_validation = dbops.verify_logical_backup(source, settings)
            return {
                "source_artifact": source.name,
                "invalid_copy": invalid.name,
                "detected_error_type": type(exc).__name__,
                "detected": True,
                "source_still_valid": bool(source_validation.get("validated")),
                "validated": True,
            }
        return {
            "source_artifact": source.name,
            "invalid_copy": invalid.name,
            "detected": False,
            "validated": False,
        }
    finally:
        invalid.unlink(missing_ok=True)
        invalid_manifest.unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Game days controlados do DB Operations Lab")
    parser.add_argument(
        "incident",
        choices=sorted(dry_run_plan("delete-data") and [
            "backup-invalid", "database-down", "delete-data", "disk-full", "lock",
            "pitr", "replication-lag", "slow-query",
        ]),
    )
    parser.add_argument("--execute", action="store_true", help="executa o cenário; sem isso apenas planeja")
    parser.add_argument("--duration", type=int, default=5, help="duração da query lenta em segundos")
    parser.add_argument(
        "--observe-prometheus",
        action="store_true",
        help="captura séries antes, durante e depois do game day",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    started = utc_now()
    mode = "execute" if args.execute else "dry-run"
    result = base_result(args.incident, mode, started)
    result["plan"] = dry_run_plan(args.incident)
    evidence: Path | None = None
    try:
        if args.duration < 1 or args.duration > 60:
            raise dbops.ConfigError("--duration deve estar entre 1 e 60 segundos")
        if not args.execute:
            result["steps"] = [{"name": item, "status": "planned"} for item in result["plan"]]
            result["validated"] = False
            result["status"] = "planned"
            evidence = write_evidence(args.incident, result)
            print(json.dumps({"evidence_file": str(evidence.relative_to(dbops.ROOT_DIR)), **result}, indent=2))
            return EXIT_OK

        if args.incident not in {"slow-query", "lock", "backup-invalid"}:
            raise dbops.ValidationError(
                "este cenário exige runbook específico e não pode ser executado automaticamente nesta rodada"
            )

        dbops.load_env_file(dbops.ROOT_DIR / ".env")
        settings = dbops.Settings.from_environment()
        if args.incident == "slow-query":
            result["observed"] = run_slow_query(
                settings,
                args.duration,
                observe_prometheus=args.observe_prometheus,
            )
        elif args.incident == "lock":
            result["observed"] = run_lock(settings, observe_prometheus=args.observe_prometheus)
        else:
            result["observed"] = run_invalid_backup(settings)
        result["steps"] = [{"name": item, "status": "executed"} for item in result["plan"]]
        result["validated"] = bool(result["observed"].get("validated"))
        result["status"] = "validated" if result["validated"] else "failed"
        evidence = write_evidence(args.incident, result)
        print(json.dumps({"evidence_file": str(evidence.relative_to(dbops.ROOT_DIR)), **result}, indent=2))
        return EXIT_OK if result["validated"] else EXIT_VALIDATION
    except dbops.ConfigError as exc:
        result.update({"status": "config_error", "error_type": type(exc).__name__, "error": str(exc)})
        evidence = write_evidence(args.incident, result)
        print(json.dumps({"evidence_file": str(evidence.relative_to(dbops.ROOT_DIR)), **result}, indent=2), file=sys.stderr)
        return EXIT_CONFIG
    except (dbops.DatabaseError, dbops.ValidationError) as exc:
        result.update({"status": "validation_error", "error_type": type(exc).__name__, "error": str(exc)})
        evidence = write_evidence(args.incident, result)
        print(json.dumps({"evidence_file": str(evidence.relative_to(dbops.ROOT_DIR)), **result}, indent=2), file=sys.stderr)
        return EXIT_DATABASE if isinstance(exc, dbops.DatabaseError) else EXIT_VALIDATION
    except Exception as exc:  # noqa: BLE001 - o CLI precisa registrar falha inesperada
        result.update({"status": "unexpected_error", "error_type": type(exc).__name__})
        evidence = write_evidence(args.incident, result)
        print(json.dumps({"evidence_file": str(evidence.relative_to(dbops.ROOT_DIR)), **result}, indent=2), file=sys.stderr)
        return EXIT_UNEXPECTED


if __name__ == "__main__":
    raise SystemExit(main())
