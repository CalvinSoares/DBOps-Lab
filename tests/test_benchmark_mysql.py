import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "automation" / "benchmark_mysql.py"
SPEC = importlib.util.spec_from_file_location("benchmark_mysql", MODULE_PATH)
benchmark_mysql = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(benchmark_mysql)


class MysqlBenchmarkTests(unittest.TestCase):
    def test_query_is_controlled_and_index_columns_match(self):
        self.assertIn("performance_orders", benchmark_mysql.QUERY)
        self.assertIn("region", benchmark_mysql.QUERY)
        self.assertIn("status", benchmark_mysql.QUERY)

    def test_benchmark_uses_performance_schema(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn("performance_schema", source)
        self.assertIn("events_statements_summary_by_digest", source)


if __name__ == "__main__":
    unittest.main()
