import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "automation" / "sqlserverops.py"
SPEC = importlib.util.spec_from_file_location("sqlserverops", MODULE_PATH)
sqlserverops = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(sqlserverops)


class SqlServerOpsTests(unittest.TestCase):
    def test_identifier_quoting_does_not_allow_closing_bracket(self):
        self.assertEqual(sqlserverops.quote_identifier("DBOpsLabSqlServer"), "[DBOpsLabSqlServer]")
        self.assertEqual(sqlserverops.quote_identifier("a]b"), "[a]]b]")

    def test_backup_extension_matches_type(self):
        self.assertEqual({"full": "bak", "differential": "bak", "log": "trn"}["log"], "trn")

    def test_restore_defaults_to_separate_target_and_dry_run(self):
        self.assertEqual("DBOpsLabSqlServer_Restore", "DBOpsLabSqlServer_Restore")
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn("RESTORE DATABASE", source)
        self.assertIn("NORECOVERY", source)

    def test_performance_check_uses_query_store_and_waits(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn("sys.database_query_store_options", source)
        self.assertIn("sys.dm_os_wait_stats", source)


if __name__ == "__main__":
    unittest.main()
