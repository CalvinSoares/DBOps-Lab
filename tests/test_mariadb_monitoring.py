import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "automation" / "check_mariadb_monitoring.py"
SPEC = importlib.util.spec_from_file_location("check_mariadb_monitoring", MODULE_PATH)
check_mariadb_monitoring = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(check_mariadb_monitoring)


class MariaDBMonitoringTests(unittest.TestCase):
    def test_queries_cover_core_operational_metrics(self):
        self.assertIn("target_up", check_mariadb_monitoring.QUERIES)
        self.assertIn("database_up", check_mariadb_monitoring.QUERIES)
        self.assertIn("connections", check_mariadb_monitoring.QUERIES)
        self.assertIn("slow_queries", check_mariadb_monitoring.QUERIES)

    def test_exporter_port_is_separate_from_database_port(self):
        self.assertNotEqual(check_mariadb_monitoring.EXPORTER_URL, "http://127.0.0.1:13306/metrics")


if __name__ == "__main__":
    unittest.main()
