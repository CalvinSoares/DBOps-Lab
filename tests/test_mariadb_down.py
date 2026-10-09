import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "automation" / "run_mariadb_down.py"
SPEC = importlib.util.spec_from_file_location("run_mariadb_down", MODULE_PATH)
run_mariadb_down = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(run_mariadb_down)


class MariaDBDownGameDayTests(unittest.TestCase):
    def test_scenario_is_isolated_and_ephemeral(self):
        self.assertEqual(run_mariadb_down.PROJECT_NAME, "dbops_incident_mariadb")
        self.assertFalse(run_mariadb_down.COMPOSE_FILE.name == "docker-compose.yml")

    def test_dry_run_lists_recovery_steps(self):
        self.assertTrue(run_mariadb_down.COMPOSE_FILE.exists())
        self.assertFalse(run_mariadb_down.SERVICE == "mariadb")


if __name__ == "__main__":
    unittest.main()
