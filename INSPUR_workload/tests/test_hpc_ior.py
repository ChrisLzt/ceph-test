import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKLOAD = ROOT / "hpc_wrf_ior_v1"
RENDERER = WORKLOAD / "render_config.sh"


class InspurHpcIorTests(unittest.TestCase):
    def test_renders_three_thousand_gib_read_write_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            env = os.environ.copy()
            env.update(
                {
                    "ANCHOR_ROOT": "/__INSPUR_CEPHFS__",
                    "RENDERED_DIR": str(output),
                    "IOR_BIN": "/opt/ior/bin/ior",
                    "MPI_RUN": "/opt/mpi/bin/mpirun",
                }
            )
            env.pop("MPI_HOSTFILE", None)
            subprocess.run([str(RENDERER)], env=env, check=True)
            prepare = (output / "prepare_data.sh").read_text(encoding="utf-8")
            run = (output / "run_test.sh").read_text(encoding="utf-8")

        for text in (prepare, run):
            self.assertIn(
                'ANCHOR="/__INSPUR_CEPHFS__/hpc_wrf_ior_v1"',
                text,
            )
            self.assertIn('NP="4"', text)
            self.assertIn('BLOCK_SIZE="256000m"', text)
            self.assertIn('TRANSFER_SIZE="4m"', text)
            self.assertIn("--posix.odirect", text)
            self.assertIn("-F", text)

        self.assertEqual(4 * 256000 * 3 / 1024, 3000)
        self.assertEqual(prepare.count("run_ior_write prepare_"), 3)
        self.assertEqual(run.count("run_ior_read "), 2)
        self.assertEqual(run.count("run_ior_write "), 2)
        expected_calls = (
            'run_ior_read startup_read "$ANCHOR/startup/wrf_state"',
            'run_ior_write checkpoint_write "$ANCHOR/checkpoint/wrfrst_current"',
            'run_ior_write history_write "$ANCHOR/history/wrfout_current"',
            'run_ior_read checkpoint_reheat "$ANCHOR/checkpoint/wrfrst_current"',
        )
        positions = [run.index(call) for call in expected_calls]
        self.assertEqual(positions, sorted(positions))


if __name__ == "__main__":
    unittest.main()
