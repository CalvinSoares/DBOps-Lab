#!/usr/bin/env python3
"""Game day isolado de indisponibilidade PostgreSQL."""

from __future__ import annotations

import argparse
import json
import subprocess
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


COMPOSE_FILE = ROOT_DIR / "incidents" / "docker-compose.database-down.yml"
PROMETHEUS_FILE = ROOT_DIR / "incidents" / "prometheus.database-down.yml"
PROJECT_NAME = "dbops_incident_down"
PROMETHEUS_PORT = 19090
EVIDENCE_DIR = ROOT_DIR / "evidence" / "phase-5"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def evidence_path() -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    return EVIDENCE_DIR / f"incident-database-down-{stamp}.json"


def compose_command(*args: str) -> list[str]:
    return [
        "docker",
        "compose",
        "--project-name",
        PROJECT_NAME,
        "--env-file",
        str(ROOT_DIR / ".env"),
        "--file",
        str(COMPOSE_FILE),
        *args,
    ]


def run_compose(*args: str) -> None:
    result = subprocess.run(
        compose_command(*args),
        cwd=ROOT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker compose falhou em {args[0]} com código {result.returncode}")


def prometheus_snapshot() -> dict[str, Any]:
    query = 'pg_up{job="incident-postgresql"}'
    encoded = urllib.parse.quote(query, safe="")
    url = f"http://127.0.0.1:{PROMETHEUS_PORT}/api/v1/query?query={encoded}"
    with urllib.request.urlopen(url, timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    if payload.get("status") != "success":
        raise RuntimeError("Prometheus isolado rejeitou a consulta pg_up")
    return {
        "timestamp": utc_now().isoformat(),
        "query": query,
        "series": payload.get("data", {}).get("result", []),
    }


def pg_up_value(snapshot: dict[str, Any]) -> str | None:
    series = snapshot.get("series", [])
    if not series:
        return None
    return series[0].get("value", [None, None])[1]


def wait_for_value(expected: str, timeout_seconds: int = 60) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_snapshot: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        try:
            last_snapshot = prometheus_snapshot()
            if pg_up_value(last_snapshot) == expected:
                return last_snapshot
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError(f"pg_up não chegou a {expected}; último snapshot={last_snapshot}")


def write_result(result: dict[str, Any]) -> Path:
    output = evidence_path()
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def dry_run() -> int:
    result = {
        "incident": "database-down",
        "mode": "dry-run",
        "status": "planned",
        "validated": False,
        "steps": [
            "subir o Compose isolado dbops_incident_down",
            "confirmar pg_up=1 no Prometheus isolado",
            "parar somente o serviço incident-postgres",
            "confirmar pg_up=0 durante a indisponibilidade",
            "subir novamente incident-postgres",
            "confirmar pg_up=1 após a recuperação",
            "remover containers e volumes descartáveis do projeto isolado",
        ],
        "isolation": {
            "compose_file": str(COMPOSE_FILE.relative_to(ROOT_DIR)),
            "prometheus_file": str(PROMETHEUS_FILE.relative_to(ROOT_DIR)),
            "project_name": PROJECT_NAME,
            "prometheus_port": PROMETHEUS_PORT,
        },
    }
    output = write_result(result)
    print(json.dumps({"evidence_file": str(output.relative_to(ROOT_DIR)), **result}, indent=2))
    return 0


def execute() -> int:
    started = utc_now()
    result: dict[str, Any] = {
        "incident": "database-down",
        "mode": "execute",
        "started_at": started.isoformat(),
        "project_name": PROJECT_NAME,
        "prometheus_port": PROMETHEUS_PORT,
        "steps": [],
        "validated": False,
    }
    try:
        run_compose("up", "-d")
        result["steps"].append({"name": "stack isolado iniciado", "status": "passed"})
        before = wait_for_value("1")
        result["before"] = before
        result["steps"].append({"name": "PostgreSQL isolado disponível", "status": "passed"})

        run_compose("stop", "incident-postgres")
        during = wait_for_value("0")
        result["during"] = during
        result["steps"].append({"name": "indisponibilidade observada", "status": "passed"})

        run_compose("up", "-d", "incident-postgres")
        after = wait_for_value("1")
        result["after"] = after
        result["steps"].append({"name": "serviço recuperado", "status": "passed"})

        result["validated"] = (
            pg_up_value(before) == "1"
            and pg_up_value(during) == "0"
            and pg_up_value(after) == "1"
        )
        result["status"] = "validated" if result["validated"] else "failed"
        return_code = 0 if result["validated"] else 4
    except Exception as exc:  # noqa: BLE001 - registrar falha e limpar o ambiente isolado
        result.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)})
        return_code = 3
    finally:
        try:
            run_compose("down", "--volumes", "--remove-orphans")
            result["cleanup"] = "completed"
        except Exception as exc:  # noqa: BLE001 - cleanup também precisa ser auditável
            result["cleanup"] = {"status": "failed", "error_type": type(exc).__name__}
            if return_code == 0:
                return_code = 5
    output = write_result(result)
    print(json.dumps({"evidence_file": str(output.relative_to(ROOT_DIR)), **result}, indent=2))
    return return_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Game day isolado de banco indisponível")
    parser.add_argument("--execute", action="store_true", help="executa o cenário isolado")
    args = parser.parse_args()
    dbops.load_env_file(ROOT_DIR / ".env")
    if not COMPOSE_FILE.exists() or not PROMETHEUS_FILE.exists():
        print(json.dumps({"error_type": "ConfigError", "message": "arquivos do cenário isolado ausentes"}))
        return 2
    return execute() if args.execute else dry_run()


if __name__ == "__main__":
    raise SystemExit(main())
