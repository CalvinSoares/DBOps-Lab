import unittest

from automation.benchmark_postgres import plan_metrics


class BenchmarkPlanTests(unittest.TestCase):
    def test_plan_metrics_sums_nested_buffer_and_filter_counters(self):
        document = [{
            "Plan": {
                "Node Type": "Seq Scan",
                "Actual Rows": 10,
                "Actual Loops": 1,
                "Rows Removed by Filter": 90,
                "Shared Hit Blocks": 4,
                "Plans": [{
                    "Node Type": "Sort",
                    "Actual Rows": 10,
                    "Actual Loops": 1,
                    "Shared Read Blocks": 2,
                }],
            },
            "Planning Time": 0.1,
            "Execution Time": 1.2,
        }]
        metrics = plan_metrics(document)
        self.assertEqual(metrics["node_types"], ["Seq Scan", "Sort"])
        self.assertEqual(metrics["actual_rows"], 20)
        self.assertEqual(metrics["shared_hit_blocks"], 4)
        self.assertEqual(metrics["shared_read_blocks"], 2)
        self.assertEqual(metrics["rows_removed_by_filter"], 90)


if __name__ == "__main__":
    unittest.main()
