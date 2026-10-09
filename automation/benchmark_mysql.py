#!/usr/bin/env python3
"""Benchmark controlado do MariaDB usando EXPLAIN e Performance Schema."""

from __future__ import annotations

import argparse
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


SERVICE = "mariadb"
DATABASE = os.getenv("MYSQL_DATABASE", "secondary_db")
TABLE = "performance_orders"
QUERY = f"SELECT COUNT(*) FROM {TABLE} WHERE region='north' AND status='open'"


def run_sql(sql: str, *, database: str | None = DATABASE, timeout: int = 180) -> str:
    args = [
        "docker",
        "compose",
        "--profile",
        "secondary",
        "exec",
        "-T",
        SERVICE,
        "sh",
        "-lc",
        'mariadb --protocol=socket --user=root --password="$MARIADB_ROOT_PASSWORD"'
        + (f" --database={database}" if database else "")
        + " --batch --raw --skip-column-names",
    ]
    result = subprocess.run(
        args,
        cwd=ROOT_DIR,
        input=sql,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        raise dbops.DatabaseError(f"MariaDB rejeitou benchmark SQL ({result.returncode})")
    return result.stdout.strip()


def configure_performance_schema() -> None:
    status = run_sql("SELECT @@performance_schema;", database=None)
    if status.strip() != "1":
        raise dbops.ValidationError("Performance Schema está desabilitado no MariaDB")
    run_sql(
        "UPDATE performance_schema.setup_consumers "
        "SET ENABLED='YES' "
        "WHERE NAME IN ('events_statements_current','events_statements_history','events_statements_history_long');",
        database=None,
    )
    run_sql(
        "UPDATE performance_schema.setup_instruments "
        "SET ENABLED='YES', TIMED='YES' "
        "WHERE NAME LIKE 'statement/sql/%';",
        database=None,
    )


def prepare_dataset(rows: int) -> None:
    run_sql(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            order_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            region VARCHAR(16) NOT NULL,
            status VARCHAR(16) NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            created_at DATETIME NOT NULL,
            PRIMARY KEY (order_id)
        ) ENGINE=InnoDB;
        TRUNCATE TABLE {TABLE};
        SET max_recursive_iterations={rows + 10};
        INSERT INTO {TABLE} (region, status, amount, created_at)
        WITH RECURSIVE sequence_numbers (n) AS (
            SELECT 1
            UNION ALL
            SELECT n + 1 FROM sequence_numbers WHERE n < {rows}
        )
        SELECT
            ELT(MOD(n, 4) + 1, 'north', 'south', 'east', 'west'),
            ELT(MOD(n, 3) + 1, 'open', 'closed', 'pending'),
            MOD(n * 37, 100000) / 100,
            NOW() - INTERVAL MOD(n, 365) DAY
        FROM sequence_numbers;
        """,
        timeout=240,
    )


def explain() -> str:
    return run_sql(f"EXPLAIN {QUERY};")


def timed_query(repetitions: int) -> dict[str, Any]:
    started = time.monotonic()
    output = run_sql("\n".join(f"{QUERY};" for _ in range(repetitions)), timeout=240)
    duration = time.monotonic() - started
    values = [line for line in output.splitlines() if line.strip()]
    return {
        "duration_seconds": round(duration, 6),
        "repetitions": repetitions,
        "result_samples": values[:3],
        "result_count": len(values),
    }


def digest_snapshot() -> str:
    return run_sql(
        "SELECT DIGEST_TEXT, COUNT_STAR, ROUND(SUM_TIMER_WAIT / 1000000000, 3), "
        "SUM_ROWS_EXAMINED, SUM_ROWS_AFFECTED "
        "FROM performance_schema.events_statements_summary_by_digest "
        "WHERE DIGEST_TEXT LIKE '%PERFORMANCE_ORDERS%' "
        "ORDER BY SUM_TIMER_WAIT DESC LIMIT 10;",
        database=None,
    )


def save_run(before_explain: str, after_explain: str, before: dict[str, Any], after: dict[str, Any], digest: str, rows: int) -> Path:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = ROOT_DIR / "benchmarks" / "mysql" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "explain-before.tsv").write_text(before_explain + "\n", encoding="utf-8")
    (run_dir / "explain-after.tsv").write_text(after_explain + "\n", encoding="utf-8")
    (run_dir / "performance-schema.tsv").write_text(digest + "\n", encoding="utf-8")
    result = {
        "database": DATABASE,
        "engine": "mariadb",
        "index": "idx_performance_orders_region_status",
        "query": QUERY,
        "rows": rows,
        "before": before,
        "after": after,
        "duration_ratio_before_over_after": round(before["duration_seconds"] / after["duration_seconds"], 3)
        if after["duration_seconds"] > 0
        else None,
        "artifacts": ["explain-before.tsv", "explain-after.tsv", "performance-schema.tsv", "result.json"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "validated": before["result_count"] == after["result_count"] == before["repetitions"],
    }
    (run_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return run_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark MariaDB com Performance Schema")
    parser.add_argument("--rows", type=int, default=50000)
    parser.add_argument("--repetitions", type=int, default=20)
    args = parser.parse_args(argv)
    if args.rows < 1000 or args.repetitions < 5:
        parser.error("--rows deve ser >= 1000 e --repetitions deve ser >= 5")
    dbops.configure_logging()
    try:
        dbops.load_env_file(ROOT_DIR / ".env")
        configure_performance_schema()
        prepare_dataset(args.rows)
        before_explain = explain()
        before = timed_query(args.repetitions)
        run_sql(f"CREATE INDEX idx_performance_orders_region_status ON {TABLE} (region, status); ANALYZE TABLE {TABLE};")
        after_explain = explain()
        after = timed_query(args.repetitions)
        digest = digest_snapshot()
        run_dir = save_run(before_explain, after_explain, before, after, digest, args.rows)
        dbops.log_event(20, "benchmark MariaDB concluído", run=str(run_dir.relative_to(ROOT_DIR)), **{"before": before, "after": after})
        return 0
    except dbops.ConfigError as exc:
        dbops.log_event(40, str(exc))
        return 2
    except dbops.DatabaseError as exc:
        dbops.log_event(40, str(exc))
        return 3
    except dbops.ValidationError as exc:
        dbops.log_event(40, str(exc))
        return 4
    except Exception as exc:  # noqa: BLE001 - fronteira controlada da CLI
        dbops.log_event(40, "erro inesperado no benchmark MariaDB", error_type=type(exc).__name__)
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
