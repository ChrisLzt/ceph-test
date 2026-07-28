import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKLOADS = (
    "bigdata_mapreduce_vdbench_v1",
    "graph_graphchi_vdbench_v1",
    "hpc_wrf_vdbench_v1",
    "ai_training_checkpoint_vdbench_v1",
    "ai_inference_kvcache_vdbench_v1",
)


class InspurSuiteTests(unittest.TestCase):
    def test_contains_five_vdbench_workloads_and_one_ior_workload(self) -> None:
        actual = sorted(
            path.name
            for path in ROOT.iterdir()
            if path.is_dir() and path.name.endswith("_vdbench_v1")
        )
        self.assertEqual(actual, sorted(WORKLOADS))
        self.assertTrue((ROOT / "hpc_wrf_ior_v1").is_dir())

    def test_top_level_workflow_and_capacity_documentation_exist(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertTrue((ROOT / "validate_all.sh").is_file())
        self.assertIn("3000 GiB", readme)
        self.assertIn("17.578", readme)
        self.assertIn("52.734", readme)
        self.assertIn("200 FWD", readme)


if __name__ == "__main__":
    unittest.main()
