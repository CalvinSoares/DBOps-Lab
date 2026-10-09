#!/usr/bin/env python3
"""Game day isolado de indisponibilidade MariaDB."""

from __future__ import annotations

import argparse
import json
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


COMPOSE_FILE = ROOT_DIR / "incidents" / "docker-compose.mariadb-down.yml"
PROJECT_NAME = "dbops_incident_mariadb"
SERVICE = "incident-mariadb"
EVIDENCE_DIR = ROOT_DIR / "evidence" / "phase-6"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def run_compose(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        compose_command(*args),
        cwd=ROOT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )


def service_id() -> str:
    result = run_compose("ps", "-a", "-q", SERVICE)
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError("container MariaDB do game day não foi encontrado")
    return result.stdout.strip().splitlines()[0]


def inspect_state() -> dict[str, Any]:
    container = service_id()
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{json .State}}", container],
        cwd=ROOT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("não foi possível inspecionar o container MariaDB do game day")
    state = json.loads(result.stdout.strip())
    return {
        "container_id": container[:12],
        "status": state.get("Status"),
        "running": state.get("Running"),
        "health": state.get("Health", {}).get("Status"),
        "timestamp": utc_now().isoformat(),
    }


def wait_for_health(expected: str, timeout_seconds: int = 60) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        try:
            last = inspect_state()
            if last.get("health") == expected:
                return last
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError(f"MariaDB não chegou ao estado de health {expected}: {last}")


def query_ok() -> bool:
    result = run_compose(
        "exec",
        "-T",
        SERVICE,
        "sh",
        "-lc",
        'mariadb --protocol=socket --user=root --password="$MARIADB_ROOT_PASSWORD" --batch --skip-column-names --execute="SELECT 1;"',
    )
    return result.returncode == 0 and result.stdout.strip() == "1"


def evidence_path() -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    return EVIDENCE_DIR / f"incident-mariadb-down-{stamp}.json"


def write_result(result: dict[str, Any]) -> Path:
    output = evidence_path()
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def dry_run() -> int:
    result = {
        "incident": "mariadb-down",
        "mode": "dry-run",
        "status": "planned",
        "validated": False,
        "steps": [
            "subir o Compose descartável dbops_incident_mariadb",
            "confirmar MariaDB saudável",
            "parar somente o serviço incident-mariadb",
            "confirmar health status unhealthy ou container parado",
            "subir novamente incident-mariadb",
            "confirmar health check e SELECT 1",
            "remover somente os recursos do projeto isolado",
        ],
        "isolation": {
            "compose_file": str(COMPOSE_FILE.relative_to(ROOT_DIR)),
            "project_name": PROJECT_NAME,
            "service": SERVICE,
            "persistent_volume": False,
        },
    }
    output = write_result(result)
    print(json.dumps({"evidence_file": str(output.relative_to(ROOT_DIR)), **result}, indent=2))
    return 0


def execute() -> int:
    started = utc_now()
    result: dict[str, Any] = {
        "incident": "mariadb-down",
        "mode": "execute",
        "started_at": started.isoformat(),
        "project_name": PROJECT_NAME,
        "service": SERVICE,
        "steps": [],
        "validated": False,
    }
    return_code = 3
    try:
        up = run_compose("up", "-d")
        if up.returncode != 0:
            raise RuntimeError("Compose MariaDB isolado não iniciou")
        result["steps"].append({"name": "stack isolado iniciado", "status": "passed"})
        before = wait_for_health("healthy")
        result["before"] = before
        result["before_query_ok"] = query_ok()
        if not result["before_query_ok"]:
            raise RuntimeError("SELECT 1 falhou antes da indisponibilidade")
        result["steps"].append({"name": "MariaDB disponível e consulta validada", "status": "passed"})

        stopped = run_compose("stop", SERVICE)
        if stopped.returncode != 0:
            raise RuntimeError("não foi possível parar somente o serviço MariaDB isolado")
        during = inspect_state()
        result["during"] = during
        if during.get("running") is not False:
            raise RuntimeError("o serviço isolado não foi observado como parado")
        result["steps"].append({"name": "indisponibilidade observada", "status": "passed"})

        restarted = run_compose("up", "-d", SERVICE)
        if restarted.returncode != 0:
            raise RuntimeError("não foi possível reiniciar o serviço MariaDB isolado")
        after = wait_for_health("healthy")
        result["after"] = after
        result["after_query_ok"] = query_ok()
        if not result["after_query_ok"]:
            raise RuntimeError("SELECT 1 falhou após a recuperação")
        result["steps"].append({"name": "serviço recuperado e consulta validada", "status": "passed"})
        result["validated"] = True
        result["status"] = "validated"
        return_code = 0
    except Exception as exc:  # noqa: BLE001 - registrar falha e limpar o ambiente isolado
        result.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)})
    finally:
        cleanup = run_compose("down", "--volumes", "--remove-orphans")
        result["cleanup"] = "completed" if cleanup.returncode == 0 else {"status": "failed", "returncode": cleanup.returncode}
        if cleanup.returncode != 0 and return_code == 0:
            return_code = 5
    output = write_result(result)
    print(json.dumps({"evidence_file": str(output.relative_to(ROOT_DIR)), **result}, indent=2))
    return return_code


def main() -> int:
    parser = argparse.ArgumentParser(description="Game day isolado de MariaDB indisponível")
    parser.add_argument("--execute", action="store_true", help="executa o cenário isolado")
    args = parser.parse_args()
    dbops.load_env_file(ROOT_DIR / ".env")
    if not COMPOSE_FILE.exists():
        print(json.dumps({"error_type": "ConfigError", "message": "Compose do cenário MariaDB ausente"}))
        return 2
    return execute() if args.execute else dry_run()


if __name__ == "__main__":
    raise SystemExit(main())
