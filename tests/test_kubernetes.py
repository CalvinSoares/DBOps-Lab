import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import check_kubernetes


class KubernetesCheckTests(unittest.TestCase):
    def test_manifest_check_passes_for_project_manifest(self):
        result = check_kubernetes.manifest_check(
            Path("kubernetes/postgres-statefulset.yaml"), None
        )
        self.assertEqual(result, 0)

    def test_manifest_check_fails_when_required_resource_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.yaml"
            manifest.write_text("kind: StatefulSet\n", encoding="utf-8")
            result = check_kubernetes.manifest_check(manifest, None)
        self.assertEqual(result, 1)

    @patch("automation.check_kubernetes.shutil.which", return_value="kubectl")
    @patch("automation.check_kubernetes.subprocess.run")
    def test_cluster_check_counts_ready_nodes(self, run, _which):
        run.return_value = type(
            "Completed",
            (),
            {
                "returncode": 0,
                "stdout": json.dumps(
                    {
                        "items": [
                            {
                                "status": {
                                    "conditions": [
                                        {"type": "Ready", "status": "True"}
                                    ]
                                }
                            }
                        ]
                    }
                ),
                "stderr": "",
            },
        )()
        result = check_kubernetes.cluster_check("test-context", 1, None)
        self.assertEqual(result, 0)
        run.assert_called_once()

    @patch("automation.check_kubernetes.shutil.which", return_value="kubectl")
    @patch("automation.check_kubernetes.subprocess.run")
    def test_cluster_check_returns_nonzero_when_api_is_unavailable(self, run, _which):
        run.return_value = type(
            "Completed",
            (),
            {"returncode": 1, "stdout": "", "stderr": "connection refused"},
        )()
        result = check_kubernetes.cluster_check(None, 1, None)
        self.assertEqual(result, 3)
