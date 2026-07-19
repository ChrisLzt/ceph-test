import re
import tempfile
import unittest
from pathlib import Path

from new_workload.ai_inference_kvcache_vdbench_v1.scripts.render import render as render_single_inference
from new_workload.ai_training_checkpoint_vdbench_v1.scripts.render import render as render_single_training
from new_workload.bigdata_mapreduce_vdbench_v1.scripts.render import render as render_single_bigdata
from new_workload.graph_graphchi_vdbench_v1.scripts.render import render as render_single_graph
from new_workload.hpc_wrf_vdbench_v1.scripts.render import render as render_single_hpc
from workload_common.tests.helpers import fsd_capacity_mib, read_configs


ROOT = Path(__file__).resolve().parents[2]


class SingleWrapperTests(unittest.TestCase):
    def test_single_node_contains_exactly_five_vdbench_workloads(self) -> None:
        expected = {
            "bigdata_mapreduce_vdbench_v1",
            "graph_graphchi_vdbench_v1",
            "hpc_wrf_vdbench_v1",
            "ai_training_checkpoint_vdbench_v1",
            "ai_inference_kvcache_vdbench_v1",
        }
        actual = {
            path.name
            for path in (ROOT / "new_workload").iterdir()
            if path.is_dir()
            and (path / "render_config.sh").is_file()
            and (path / "rendered" / "run_test.vdb").is_file()
        }
        self.assertEqual(actual, expected)

    def test_all_single_wrappers_emit_host_and_batched_prepare(self) -> None:
        jobs = (
            (render_single_bigdata, {"phase_seconds": 150}),
            (render_single_graph, {"phase_seconds": 150}),
            (render_single_hpc, {"phase_seconds": 150}),
            (render_single_training, {"dataset_phase_seconds": 160, "checkpoint_phase_seconds": 60}),
            (render_single_inference, {"phase_seconds": 100}),
        )
        for renderer, options in jobs:
            with self.subTest(renderer=renderer.__module__), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp)
                renderer(
                    anchor_root="/mnt/cephfs",
                    output_dir=output,
                    host="test-host",
                    remote_user="test-user",
                    vdbench_home="/opt/vdbench",
                    threads=1,
                    fwdrate="max",
                    **options,
                )
                prepare, run = read_configs(output)
                self.assertEqual(fsd_capacity_mib(prepare), 112 * 1024 + 512)
                elapsed = [
                    int(value)
                    for value in re.findall(
                        r"^rd=.*\belapsed=(\d+)", run, flags=re.MULTILINE
                    )
                ]
                self.assertEqual(sum(elapsed), 600, renderer.__module__)
                for text in (prepare, run):
                    self.assertEqual(text.count("hd=default,"), 1)
                    self.assertEqual(text.count("hd=hd1,system=test-host"), 1)
                    self.assertIn("vdbench=/opt/vdbench,user=test-user", text)
                clean = [line for line in prepare.splitlines() if "format=(clean,only)" in line]
                create = [line for line in prepare.splitlines() if "format=(restart,only)" in line]
                self.assertEqual(len(clean), len(create))
                self.assertGreater(len(clean), 1)
                for line in clean:
                    self.assertLessEqual(len(re.findall(r"prep_[^,)]+", line)), 20 * 3)

    def test_prepare_wrappers_remove_all_old_rank_directories_safely(self) -> None:
        for relative in (
            "new_workload/bigdata_mapreduce_vdbench_v1/prepare_data.sh",
            "new_workload/graph_graphchi_vdbench_v1/prepare_data.sh",
            "new_workload/hpc_wrf_vdbench_v1/prepare_data.sh",
            "new_workload/ai_training_checkpoint_vdbench_v1/prepare_data.sh",
            "new_workload/ai_inference_kvcache_vdbench_v1/prepare_data.sh",
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
            "new_workload/bigdata_mapreduce_vdbench_v1/prepare_data.sh",
            "SYSU_workload/bigdata_mapreduce_vdbench_v1/prepare_data.sh",
        ):
            with self.subTest(script=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn("pool_04 pool_05", text)

    def test_graph_prepare_wrappers_remove_only_legacy_window_directories(self) -> None:
        for relative in (
            "new_workload/graph_graphchi_vdbench_v1/prepare_data.sh",
            "SYSU_workload/graph_graphchi_vdbench_v1/prepare_data.sh",
        ):
            with self.subTest(script=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn("-name 'window_src*'", text)
                self.assertIn("-exec rm -rf -- {} +", text)


if __name__ == "__main__":
    unittest.main()
