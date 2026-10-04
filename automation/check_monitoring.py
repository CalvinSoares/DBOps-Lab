#!/usr/bin/env python3
"""Valida a cadeia PostgreSQL exporter -> Prometheus -> Grafana."""

from __future__ import annotations

import base64
import json
import os
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


def http_get(url: str, timeout: float = 5, headers: dict[str, str] | None = None) -> tuple[int, str]:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8", errors="replace")


def prometheus_query(port: str, query: str) -> list[dict[str, Any]]:
    encoded = urllib.parse.quote(query, safe="")
    status, body = http_get(f"http://127.0.0.1:{port}/api/v1/query?query={encoded}")
    if status != 200:
        raise RuntimeError(f"Prometheus retornou HTTP {status} para {query}")
    payload = json.loads(body)
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus rejeitou query {query}")
    return payload.get("data", {}).get("result", [])


def wait_for_metrics(prometheus_port: str, exporter_port: str, node_port: str) -> dict[str, Any]:
    deadline = time.monotonic() + 60
    last_error = "nenhuma tentativa executada"
    while time.monotonic() < deadline:
        try:
            exporter_status, exporter_body = http_get(f"http://127.0.0.1:{exporter_port}/metrics")
            pg_up = prometheus_query(prometheus_port, 'up{job="postgresql"}')
            node_up = prometheus_query(prometheus_port, 'up{job="node"}')
            db_up = prometheus_query(prometheus_port, "pg_up")
            node_cpu = prometheus_query(prometheus_port, "node_cpu_seconds_total")
            latency = prometheus_query(prometheus_port, 'dbops_activity_max_query_age_seconds{datname="dbops"}')
            lock_waits = prometheus_query(prometheus_port, 'dbops_lock_waits_blocked_queries{datname="dbops"}')
            backup_age = prometheus_query(prometheus_port, 'dbops_backup_status_age_seconds{backup_type="logical"}')
            backup_failed = prometheus_query(prometheus_port, 'dbops_backup_status_failed{backup_type="logical"}')
            rules_status, rules_body = http_get(f"http://127.0.0.1:{prometheus_port}/api/v1/rules?type=alert")
            if (
                exporter_status == 200
                and "pg_up" in exporter_body
                and "pg_stat_database_numbackends" in exporter_body
                and pg_up
                and pg_up[0]["value"][1] == "1"
                and node_up
                and node_up[0]["value"][1] == "1"
                and node_cpu
                and latency
                and lock_waits
                and backup_age
                and backup_failed
                and backup_failed[0]["value"][1] == "0"
                and db_up
                and db_up[0]["value"][1] == "1"
                and rules_status == 200
                and json.loads(rules_body).get("data", {}).get("groups")
            ):
                return {
                    "exporter_metrics_http": exporter_status,
                    "postgres_target_up": pg_up[0]["value"][1],
                    "node_target_up": node_up[0]["value"][1],
                    "node_cpu_series": len(node_cpu),
                    "latency_series": len(latency),
                    "lock_wait_series": len(lock_waits),
                    "backup_age_series": len(backup_age),
                    "backup_failed_series": len(backup_failed),
                    "backup_failed_logical": backup_failed[0]["value"][1],
                    "pg_up": db_up[0]["value"][1],
                    "alert_rule_groups": len(json.loads(rules_body)["data"]["groups"]),
                    "validated": True,
                }
        except Exception as exc:  # noqa: BLE001 - retry até a stack estabilizar
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(f"métricas não ficaram disponíveis em 60s: {last_error}")


def main() -> int:
    dbops.load_env_file(ROOT_DIR / ".env")
    prometheus_port = os.getenv("PROMETHEUS_PORT", "9090")
    exporter_port = os.getenv("POSTGRES_EXPORTER_PORT", "9187")
    node_port = os.getenv("NODE_EXPORTER_PORT", "9100")
    grafana_port = os.getenv("GRAFANA_PORT", "3000")
    try:
        grafana_status, grafana_body = http_get(f"http://127.0.0.1:{grafana_port}/api/health")
        credentials = f"{os.getenv('GRAFANA_ADMIN_USER', 'admin')}:{os.getenv('GRAFANA_ADMIN_PASSWORD', '')}"
        auth_header = {
            "Authorization": "Basic " + base64.b64encode(credentials.encode("utf-8")).decode("ascii")
        }
        dashboard_status, dashboard_body = http_get(
            f"http://127.0.0.1:{grafana_port}/api/dashboards/uid/dbops-postgres",
            headers=auth_header,
        )
        dashboard = json.loads(
            (ROOT_DIR / "monitoring/grafana/dashboards/dbops-postgres.json").read_text(encoding="utf-8")
        )
        if grafana_status != 200 or json.loads(grafana_body).get("database") != "ok":
            raise RuntimeError("Grafana não está saudável")
        if dashboard_status != 200 or json.loads(dashboard_body).get("dashboard", {}).get("uid") != "dbops-postgres":
            raise RuntimeError("dashboard dbops-postgres não foi carregado no Grafana")
        if len(dashboard.get("panels", [])) < 6:
            raise RuntimeError("dashboard possui menos de seis painéis")
        metrics = wait_for_metrics(prometheus_port, exporter_port, node_port)
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prometheus_port": prometheus_port,
            "grafana_port": grafana_port,
            "grafana_health_http": grafana_status,
            "grafana_dashboard_http": dashboard_status,
            "dashboard_panels": len(dashboard["panels"]),
            **metrics,
        }
        output_dir = ROOT_DIR / "evidence" / "phase-0"
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / f"monitoring-result-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({**result, "evidence_file": str(output.relative_to(ROOT_DIR))}, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001 - fronteira da CLI
        print(json.dumps({"level": "ERROR", "message": str(exc), "error_type": type(exc).__name__}))
        return 3


if __name__ == "__main__":
    sys.exit(main())
