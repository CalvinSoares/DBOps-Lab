import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import dbops


class DbopsConfigTests(unittest.TestCase):
    def test_load_env_file_does_not_override_existing_environment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("DBOPS_TEST_VALUE=from-file\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("DBOPS_TEST_VALUE", None)
                dbops.load_env_file(env_path)
                self.assertEqual(os.environ["DBOPS_TEST_VALUE"], "from-file")

            with patch.dict(os.environ, {"DBOPS_TEST_VALUE": "from-process"}, clear=False):
                dbops.load_env_file(env_path)
                self.assertEqual(os.environ["DBOPS_TEST_VALUE"], "from-process")

    def test_settings_reject_missing_role_password(self):
        values = {
            "POSTGRES_DB": "dbops",
            "POSTGRES_USER": "admin",
            "POSTGRES_PASSWORD": "admin-password",
            "POSTGRES_APP_USER": "app",
            "POSTGRES_APP_PASSWORD": "app-password",
            "POSTGRES_OPERATOR_USER": "operator",
            "POSTGRES_OPERATOR_PASSWORD": "operator-password",
            "POSTGRES_READONLY_USER": "readonly",
            "POSTGRES_READONLY_PASSWORD": "readonly-password",
            "POSTGRES_MONITOR_USER": "monitor",
        }
        with patch.dict(os.environ, values, clear=True):
            with self.assertRaises(dbops.ConfigError):
                dbops.Settings.from_environment()


if __name__ == "__main__":
    unittest.main()
