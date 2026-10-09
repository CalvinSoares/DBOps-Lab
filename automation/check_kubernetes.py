"""Preflight checks for the optional Kubernetes PostgreSQL deployment."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST = Path("kubernetes/postgres-statefulset.yaml")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_result(result: dict[str, Any], output: Path | None) -> None:
    payload = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    print(payload, end="")
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")


def manifest_check(manifest: Path, output: Path | None) -> int:
    started = time.monotonic()
    result: dict[str, Any] = {
        "check": "kubernetes-manifest",
        "timestamp_utc": utc_now(),
        "manifest": str(manifest),
        "status": "failed",
        "checks": {},
    }
    if not manifest.is_file():
        result["error"] = f"manifest not found: {manifest}"
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        write_result(result, output)
        return 2

    text = manifest.read_text(encoding="utf-8")
    checks = {
        "statefulset": "kind: StatefulSet" in text,
        "persistent_volume_claim": "kind: PersistentVolumeClaim" in text,
        "config_map": "kind: ConfigMap" in text,
        "secret": "kind: Secret" in text,
        "service": "kind: Service" in text,
        "probes": all(
            marker in text
            for marker in ("startupProbe:", "readinessProbe:", "livenessProbe:")
        ),
        "backup_cronjob": "kind: CronJob" in text,
        "separate_backup_claim": "claimName: postgres-backups" in text,
        "retention_policy": all(
            marker in text
            for marker in ("whenDeleted: Retain", "whenScaled: Retain")
        ),
        "placeholder_secret": "POSTGRES_PASSWORD: replace-before-apply" in text,
    }
    result["checks"] = checks
    result["status"] = "passed" if all(checks.values()) else "failed"
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    write_result(result, output)
    return 0 if result["status"] == "passed" else 1


def cluster_check(context: str | None, timeout: float, output: Path | None) -> int:
    started = time.monotonic()
    kubectl = shutil.which("kubectl")
    result: dict[str, Any] = {
        "check": "kubernetes-cluster",
        "timestamp_utc": utc_now(),
        "context": context,
        "status": "failed",
        "ready_nodes": 0,
    }
    if not kubectl:
        result["error"] = "kubectl not found in PATH"
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        write_result(result, output)
        return 2

    command = [kubectl]
    if context:
        command.extend(["--context", context])
    command.extend(
        [
            "get",
            "nodes",
            "--request-timeout",
            f"{timeout:g}s",
            "-o",
            "json",
        ]
    )
    result["command"] = command
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout + 2,
            check=False,
        )
    except subprocess.TimeoutExpired:
        result["error"] = f"kubectl timed out after {timeout:g}s"
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        write_result(result, output)
        return 3

    if completed.returncode != 0:
        result["error"] = (completed.stderr or completed.stdout).strip()[-1000:]
        result["returncode"] = completed.returncode
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        write_result(result, output)
        return 3

    try:
        payload = json.loads(completed.stdout)
        nodes = payload.get("items", [])
        ready_nodes = 0
        for node in nodes:
            conditions = node.get("status", {}).get("conditions", [])
            if any(
                item.get("type") == "Ready" and item.get("status") == "True"
                for item in conditions
            ):
                ready_nodes += 1
        result["node_count"] = len(nodes)
        result["ready_nodes"] = ready_nodes
    except json.JSONDecodeError as exc:
        result["error"] = f"kubectl returned invalid JSON: {exc}"
        result["duration_seconds"] = round(time.monotonic() - started, 3)
        write_result(result, output)
        return 3

    result["status"] = "passed" if result["ready_nodes"] > 0 else "failed"
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    write_result(result, output)
    return 0 if result["status"] == "passed" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest = subparsers.add_parser("manifest-check")
    manifest.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    manifest.add_argument("--output", type=Path)

    cluster = subparsers.add_parser("cluster-check")
    cluster.add_argument("--context")
    cluster.add_argument("--timeout", type=float, default=5.0)
    cluster.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "manifest-check":
        return manifest_check(args.manifest, args.output)
    return cluster_check(args.context, args.timeout, args.output)


if __name__ == "__main__":
    sys.exit(main())
