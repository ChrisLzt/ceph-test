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

    def test_top_level_capacity_and_workload_design_documentation_exist(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertTrue((ROOT / "validate_all.sh").is_file())
        self.assertIn("3000 GiB", readme)
        self.assertIn("18000 GiB", readme)
        self.assertIn("54000 GiB", readme)
        self.assertIn("17.578", readme)
        self.assertIn("52.734", readme)
        for section in (
            "### MapReduce",
            "### GraphChi",
            "### HPC Vdbench",
            "### AI 训练",
            "### AI 推理",
            "### HPC IOR",
        ):
            with self.subTest(section=section):
                self.assertIn(section, readme)
        self.assertNotIn("200 FWD", readme)


if __name__ == "__main__":
    unittest.main()
