import unittest

from automation import run_incident


class IncidentPlanTests(unittest.TestCase):
    def test_all_required_incidents_have_a_plan(self):
        incidents = {
            "delete-data",
            "pitr",
            "disk-full",
            "database-down",
            "slow-query",
            "lock",
            "replication-lag",
            "backup-invalid",
        }
        for incident in incidents:
            with self.subTest(incident=incident):
                self.assertGreaterEqual(len(run_incident.dry_run_plan(incident)), 3)

    def test_dry_run_never_marks_incident_as_validated(self):
        result = run_incident.base_result("database-down", "dry-run", run_incident.utc_now())
        result["steps"] = [
            {"name": step, "status": "planned"}
            for step in run_incident.dry_run_plan("database-down")
        ]
        result["status"] = "planned"
        self.assertFalse(result["validated"])
        self.assertEqual(result["mode"], "dry-run")


if __name__ == "__main__":
    unittest.main()
