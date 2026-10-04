import unittest

from automation import run_database_down


class DatabaseDownGameDayTests(unittest.TestCase):
    def test_compose_scenario_isolated_from_main_project(self):
        self.assertEqual(run_database_down.PROJECT_NAME, "dbops_incident_down")
        self.assertNotEqual(run_database_down.COMPOSE_FILE.name, "docker-compose.yml")
        self.assertEqual(run_database_down.PROMETHEUS_PORT, 19090)

    def test_pg_up_value_reads_prometheus_snapshot(self):
        snapshot = {"series": [{"value": [123, "0"]}]}
        self.assertEqual(run_database_down.pg_up_value(snapshot), "0")


if __name__ == "__main__":
    unittest.main()
