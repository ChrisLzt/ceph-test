import subprocess
import tempfile
import unittest
from pathlib import Path

from SYSU_workload.ai_inference_kvcache_vdbench_v1.scripts.render import render as render_inference
from SYSU_workload.ai_training_checkpoint_vdbench_v1.scripts.render import render as render_training
from SYSU_workload.bigdata_mapreduce_vdbench_v1.scripts.render import render as render_bigdata
from SYSU_workload.graph_graphchi_vdbench_v1.scripts.render import render as render_graph
from SYSU_workload.hpc_wrf_vdbench_v1.scripts.render import render as render_hpc


ROOT = Path(__file__).resolve().parents[1]
WORKLOADS = (
    "bigdata_mapreduce_vdbench_v1",
    "graph_graphchi_vdbench_v1",
    "hpc_wrf_vdbench_v1",
    "ai_training_checkpoint_vdbench_v1",
    "ai_inference_kvcache_vdbench_v1",
)


class SuiteContractTests(unittest.TestCase):
    def test_top_level_workflow_files_exist(self) -> None:
        self.assertTrue((ROOT / "README.md").is_file())
        self.assertTrue((ROOT / "validate_all.sh").is_file())

    def test_top_level_workflow_integrates_hpc_ior(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        validator = (ROOT / "validate_all.sh").read_text(encoding="utf-8")
        self.assertIn("hpc_wrf_ior_v1", readme)
        self.assertIn("五个", readme)
        self.assertIn("Vdbench 负载和一个保留的 HPC IOR 负载", readme)
        self.assertIn("hpc_wrf_ior_v1/validate_model.sh", validator)
        self.assertIn("workload_common.validate_vdbench", validator)

    def test_contains_exactly_five_vdbench_workloads(self) -> None:
        actual = sorted(
            path.name
            for path in ROOT.iterdir()
            if path.is_dir() and path.name.endswith("_vdbench_v1")
        )
        self.assertEqual(actual, sorted(WORKLOADS))

    def test_hpc_ior_workload_files_exist(self) -> None:
        workload = ROOT / "hpc_wrf_ior_v1"
        for name in (
            "README.md",
            "render_config.sh",
            "prepare_data.sh",
            "run_test.sh",
            "validate_model.sh",
        ):
            self.assertTrue((workload / name).is_file(), name)

    def test_all_rendered_run_configs_are_host_agnostic_direct_io(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            jobs = (
                ("bigdata", render_bigdata, {"threads": 1, "phase_seconds": 150, "fwdrate": "max"}),
                ("graph", render_graph, {"threads": 1, "phase_seconds": 150, "fwdrate": "max"}),
                ("hpc", render_hpc, {"threads": 1, "phase_seconds": 150, "fwdrate": "max"}),
                (
                    "training",
                    render_training,
                    {
                        "threads": 1,
                        "dataset_phase_seconds": 160,
                        "checkpoint_phase_seconds": 60,
                        "fwdrate": "max",
                    },
                ),
                ("inference", render_inference, {"threads": 1, "phase_seconds": 100, "fwdrate": "max"}),
            )
            for name, renderer, options in jobs:
                output = base / name
                renderer(anchor_root="/__SYSU_CEPHFS__", output_dir=output, **options)
                prepare = (output / "prepare_data.vdb").read_text(encoding="utf-8")
                run = (output / "run_test.vdb").read_text(encoding="utf-8")
                self.assertNotIn("\nhd=", prepare, name)
                self.assertNotIn("\nhd=", run, name)
                self.assertIn("openflags=o_direct", run, name)
                self.assertTrue(
                    all("xfersize=4m" in line for line in run.splitlines() if line.startswith("fwd=")),
                    name,
                )
                self.assertNotIn("format=", run, name)
                self.assertIn("format=(clean,only)", prepare, name)
                self.assertIn("format=(restart,only)", prepare, name)

    def test_every_shell_renderer_requires_anchor_root(self) -> None:
        for workload in WORKLOADS:
            result = subprocess.run(
                [str(ROOT / workload / "render_config.sh")],
                cwd=ROOT.parent,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                env={"PATH": "/usr/bin:/bin"},
            )
            self.assertNotEqual(result.returncode, 0, workload)
            self.assertIn("ANCHOR_ROOT", result.stderr, workload)


if __name__ == "__main__":
    unittest.main()
