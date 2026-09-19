import re
import tempfile
import unittest
from pathlib import Path

from workload_common.tests.helpers import fsd_capacity_mib, read_configs


ROOT = Path(__file__).resolve().parents[2]


class SingleWrapperTests(unittest.TestCase):
    def test_single_node_contains_exactly_five_vdbench_workloads(self) -> None:
        from workload_common.single_v2 import CASES
        expected = set(CASES.values())
        actual = {p.name for p in (ROOT / 'SINGLE_workload').iterdir()
                  if p.is_dir() and p.name != '__pycache__'}
        self.assertEqual(actual, expected)

    def test_current_config_lives_with_each_workload(self):
        from workload_common.single_v2 import CASES, core
        for name in CASES.values():
            bundle = ROOT/'SINGLE_workload'/name/'rendered'
            manifest = core.validate_bundle(bundle)
            self.assertIn('current', manifest['profiles'])
            self.assertTrue((bundle/'run_current.vdb').is_file())

    def test_prepare_wrappers_remove_all_old_rank_directories_safely(self) -> None:
        for relative in (
            "SYSU_workload/bigdata_mapreduce_vdbench_v1/prepare_data.sh",
            "SYSU_workload/graph_graphchi_vdbench_v1/prepare_data.sh",
            "SYSU_workload/hpc_wrf_vdbench_v1/prepare_data.sh",
            "SYSU_workload/ai_training_checkpoint_vdbench_v1/prepare_data.sh",
            "SYSU_workload/ai_inference_kvcache_vdbench_v1/prepare_data.sh",
        ):
            with self.subTest(script=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn("-mindepth 2 -maxdepth 2", text)
                self.assertIn("-name 'rank_*'", text)
                self.assertIn("-name 'size_*m'", text)
                self.assertIn("-exec rm -rf -- {} +", text)

    def test_mapreduce_prepare_wrappers_remove_legacy_pool_directories(self) -> None:
        for relative in (
            "SYSU_workload/bigdata_mapreduce_vdbench_v1/prepare_data.sh",
        ):
            with self.subTest(script=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn("pool_04 pool_05", text)

    def test_graph_prepare_wrappers_remove_only_legacy_window_directories(self) -> None:
        for relative in (
            "SYSU_workload/graph_graphchi_vdbench_v1/prepare_data.sh",
        ):
            with self.subTest(script=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn("-name 'window_src*'", text)
                self.assertIn("-exec rm -rf -- {} +", text)


if __name__ == "__main__":
    unittest.main()
