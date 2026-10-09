#!/usr/bin/env python3
"""Valida coleta real do exporter MariaDB no Prometheus."""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from automation import dbops


ROOT_DIR = dbops.ROOT_DIR
PROMETHEUS_URL = "http://127.0.0.1:9090"
EXPORTER_URL = "http://127.0.0.1:9188/metrics"
EVIDENCE_DIR = ROOT_DIR / "evidence" / "phase-6"
QUERIES = {
    "target_up": 'up{job="mariadb"}',
    "database_up": 'mysql_up{job="mariadb"}',
    "connections": 'mysql_global_status_threads_connected{job="mariadb"}',
    "threads_running": 'mysql_global_status_threads_running{job="mariadb"}',
    "slow_queries": 'mysql_global_status_slow_queries{job="mariadb"}',
    "uptime": 'mysql_global_status_uptime{job="mariadb"}',
}


def get_url(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.read()


def query_prometheus(query: str) -> list[dict[str, Any]]:
    encoded = urllib.parse.quote(query, safe="")
    payload = json.loads(get_url(f"{PROMETHEUS_URL}/api/v1/query?query={encoded}"))
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus rejeitou a consulta: {query}")
    return payload.get("data", {}).get("result", [])


def wait_for_services(timeout_seconds: int = 90) -> bytes:
    deadline = time.monotonic() + timeout_seconds
    last_error: str | None = None
    while time.monotonic() < deadline:
        try:
            metrics = get_url(EXPORTER_URL)
            if b"mysql_up" in metrics:
                return metrics
        except Exception as exc:  # noqa: BLE001 - retry controlado de startup
            last_error = str(exc)
        time.sleep(3)
    raise RuntimeError(f"exporter MariaDB não ficou disponível: {last_error}")


def write_evidence(result: dict[str, Any]) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = EVIDENCE_DIR / f"mariadb-monitoring-{stamp}.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def main() -> int:
    dbops.configure_logging()
    started = datetime.now(timezone.utc)
    try:
        metrics = wait_for_services()
        snapshots = {name: query_prometheus(query) for name, query in QUERIES.items()}
        target_value = snapshots["target_up"][0]["value"][1] if snapshots["target_up"] else None
        database_value = snapshots["database_up"][0]["value"][1] if snapshots["database_up"] else None
        required_series = [name for name, values in snapshots.items() if not values]
        result = {
            "started_at": started.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "exporter": {
                "url": EXPORTER_URL,
                "contains_mysql_up": b"mysql_up" in metrics,
                "metrics_bytes": len(metrics),
            },
            "prometheus": {
                "url": PROMETHEUS_URL,
                "queries": snapshots,
                "target_value": target_value,
                "database_value": database_value,
            },
            "required_series_missing": required_series,
            "validated": target_value == "1" and database_value == "1" and not required_series,
        }
        output = write_evidence(result)
        dbops.log_event(20, "monitoramento MariaDB validado", evidence=str(output.relative_to(ROOT_DIR)), **result)
        return 0 if result["validated"] else 4
    except Exception as exc:  # noqa: BLE001 - saída operacional controlada
        result = {
            "started_at": started.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "validated": False,
        }
        output = write_evidence(result)
        dbops.log_event(40, "monitoramento MariaDB falhou", evidence=str(output.relative_to(ROOT_DIR)), error_type=type(exc).__name__)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
