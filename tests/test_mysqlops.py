import unittest

from automation import mysqlops


class MysqlopsTests(unittest.TestCase):
    def test_backup_manifest_path_is_adjacent(self):
        artifact = mysqlops.ROOT_DIR / "mysql" / "backup" / "example.sql.gz"
        self.assertEqual(mysqlops.manifest_path(artifact).name, "example.sql.gz.manifest.json")

    def test_expected_service_and_container_path(self):
        self.assertEqual(mysqlops.SERVICE, "mariadb")
        self.assertEqual(mysqlops.CONTAINER_BACKUP_DIR, "/var/lib/mysql/backups")


if __name__ == "__main__":
    unittest.main()
