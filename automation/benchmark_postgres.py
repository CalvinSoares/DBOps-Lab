#!/usr/bin/env python3
"""Benchmark reproduzível de tuning e locks para o PostgreSQL."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from automation import dbops


BENCHMARK_DIR = ROOT_DIR / "benchmarks" / "postgres" / "runs"


def as_json_document(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, str):
        raw = json.loads(raw)
    if isinstance(raw, dict):
        return [raw]
    if not isinstance(raw, list):
        raise ValueError("EXPLAIN não retornou JSON em lista ou objeto")
    return raw


def plan_metrics(document: list[dict[str, Any]]) -> dict[str, Any]:
    root = document[0]
    plan = root["Plan"]
    nodes: list[str] = []
    totals = {
        "actual_rows": 0,
        "actual_loops": 0,
        "rows_removed_by_filter": 0,
        "shared_hit_blocks": 0,
        "shared_read_blocks": 0,
    }

    def visit(node: dict[str, Any]) -> None:
        nodes.append(str(node.get("Node Type", "unknown")))
        for key in totals:
            totals[key] += int(node.get({
                "actual_rows": "Actual Rows",
                "actual_loops": "Actual Loops",
                "rows_removed_by_filter": "Rows Removed by Filter",
                "shared_hit_blocks": "Shared Hit Blocks",
                "shared_read_blocks": "Shared Read Blocks",
            }[key], 0) or 0)
        for child in node.get("Plans", []):
            visit(child)

    visit(plan)
    return {
        "planning_time_ms": root.get("Planning Time"),
        "execution_time_ms": root.get("Execution Time"),
        "node_types": nodes,
        **totals,
    }


def benchmark_query(schema: str) -> str:
    return (
        f'SELECT order_id, customer_id, status, created_at '
        f'FROM "{schema}"."orders" '
        "WHERE customer_id = 777 "
        "AND status = 'open' "
        "AND created_at >= TIMESTAMPTZ '2026-01-01' "
        "ORDER BY created_at DESC LIMIT 50"
    )


def explain(conn: Any, schema: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    query = benchmark_query(schema)
    raw = conn.execute(
        f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
    ).fetchone()[0]
    document = as_json_document(raw)
    return document, plan_metrics(document)


def run_lock_scenario(conn_kwargs: dict[str, Any], schema: str) -> dict[str, Any]:
    psycopg = dbops.import_psycopg()
    table = f'"{schema}"."orders"'
    holder = psycopg.connect(**conn_kwargs)
    waiter = psycopg.connect(**conn_kwargs)
    inspector = psycopg.connect(**conn_kwargs)
    holder.autocommit = False
    waiter.autocommit = True
    inspector.autocommit = True
    waiter_error: dict[str, str] = {}
    try:
        holder.execute(f"SELECT order_id FROM {table} WHERE order_id = 1 FOR UPDATE")
        holder_pid = holder.execute("SELECT pg_backend_pid()").fetchone()[0]
        waiter_pid = waiter.execute("SELECT pg_backend_pid()").fetchone()[0]
        waiter.execute("SET lock_timeout = '5s'")

        def blocked_update() -> None:
            try:
                waiter.execute(f"UPDATE {table} SET payload = payload || ' blocked' WHERE order_id = 1")
            except Exception as exc:  # noqa: BLE001 - o erro é a evidência esperada do cenário
                waiter_error["type"] = type(exc).__name__
                waiter_error["message"] = str(exc).splitlines()[0]

        thread = threading.Thread(target=blocked_update, daemon=True)
        thread.start()
        time.sleep(0.5)
        blocking_row = inspector.execute(
            """
            SELECT pid, wait_event_type, wait_event, pg_blocking_pids(pid)
            FROM pg_stat_activity
            WHERE pid = %s
            """,
            (waiter_pid,),
        ).fetchone()
        thread.join(timeout=7)
        if thread.is_alive():
            raise RuntimeError("sessão bloqueada não respeitou o lock_timeout")
        if not waiter_error:
            raise RuntimeError("UPDATE bloqueado terminou sem erro de lock")
        if not blocking_row:
            raise RuntimeError("sessão bloqueada não apareceu em pg_stat_activity")
        return {
            "holder_pid": holder_pid,
            "waiter_pid": waiter_pid,
            "wait_event_type": blocking_row[1],
            "wait_event": blocking_row[2],
            "blocking_pids": list(blocking_row[3] or []),
            "waiter_error_type": waiter_error["type"],
            "waiter_error": waiter_error["message"],
            "validated": holder_pid in list(blocking_row[3] or []) and waiter_error["type"] == "LockNotAvailable",
        }
    finally:
        try:
            holder.rollback()
        finally:
            holder.close()
            waiter.close()
            inspector.close()


def drop_schema(conn: Any, schema: str) -> None:
    conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


def run(rows: int, cleanup: bool) -> dict[str, Any]:
    if rows < 10_000:
        raise ValueError("--rows deve ser pelo menos 10000 para produzir um plano comparável")
    settings = dbops.Settings.from_environment()
    psycopg = dbops.import_psycopg()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    schema = f"benchmark_{run_id.lower().replace('-', '_')}"
    output_dir = BENCHMARK_DIR / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    conn_kwargs = settings.connection_kwargs()
    created = False
    try:
        with psycopg.connect(**conn_kwargs) as conn:
            conn.autocommit = True
            conn.execute(f'CREATE SCHEMA "{schema}"')
            conn.execute(
                f"""
                CREATE TABLE "{schema}"."orders" (
                    order_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    customer_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                f"""
                INSERT INTO "{schema}"."orders" (customer_id, status, created_at, payload)
                SELECT (g %% 1000) + 1,
                       CASE WHEN g %% 10 < 8 THEN 'open' ELSE 'closed' END,
                       TIMESTAMPTZ '2026-01-01' + ((g %% 365) * INTERVAL '1 day'),
                       repeat('synthetic-order-', 6)
                FROM generate_series(1, %s::bigint) AS series(g)
                """,
                (rows,),
            )
            conn.execute(f'ANALYZE "{schema}"."orders"')
            created = True
            before_document, before_metrics = explain(conn, schema)
            conn.execute(
                f'CREATE INDEX "idx_{schema}_customer_status_created" '
                f'ON "{schema}"."orders" (customer_id, status, created_at DESC) INCLUDE (order_id)'
            )
            conn.execute(f'ANALYZE "{schema}"."orders"')
            after_document, after_metrics = explain(conn, schema)
            lock_result = run_lock_scenario(conn_kwargs, schema)

        duration = round(time.monotonic() - started, 3)
        result = {
            "run_id": run_id,
            "schema": schema,
            "rows": rows,
            "query": benchmark_query(schema),
            "index": f'idx_{schema}_customer_status_created',
            "before": before_metrics,
            "after": after_metrics,
            "lock": lock_result,
            "duration_seconds": duration,
            "cleanup_requested": cleanup,
            "validated": (
                "Seq Scan" in before_metrics["node_types"]
                and any("Index" in node for node in after_metrics["node_types"])
                and lock_result["validated"]
            ),
        }
        (output_dir / "plan-before.json").write_text(json.dumps(before_document, indent=2) + "\n", encoding="utf-8")
        (output_dir / "plan-after.json").write_text(json.dumps(after_document, indent=2) + "\n", encoding="utf-8")
        (output_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result
    finally:
        if cleanup and created:
            with psycopg.connect(**conn_kwargs) as cleanup_conn:
                cleanup_conn.autocommit = True
                drop_schema(cleanup_conn, schema)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark de tuning e locks PostgreSQL")
    parser.add_argument("--rows", type=int, default=200_000)
    parser.add_argument("--cleanup", action="store_true", help="remove o schema sintético após gerar evidências")
    args = parser.parse_args(argv)
    try:
        dbops.load_env_file(ROOT_DIR / ".env")
        result = run(args.rows, args.cleanup)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0 if result["validated"] else 4
    except Exception as exc:  # noqa: BLE001 - fronteira da CLI
        print(json.dumps({"level": "ERROR", "message": str(exc), "error_type": type(exc).__name__}))
        return 3


if __name__ == "__main__":
    sys.exit(main())
