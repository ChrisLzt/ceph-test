import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKLOAD = ROOT / "hpc_wrf_ior_v1"
RENDERER = WORKLOAD / "render_config.sh"


class HpcIorRendererTests(unittest.TestCase):
    def test_requires_anchor_root(self) -> None:
        self.assertTrue(RENDERER.is_file(), "HPC IOR renderer does not exist")
        result = subprocess.run(
            [str(RENDERER)],
            env={"PATH": "/usr/bin:/bin"},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ANCHOR_ROOT", result.stderr)

    def test_renders_750_gib_file_per_process_lifecycle(self) -> None:
        self.assertTrue(RENDERER.is_file(), "HPC IOR renderer does not exist")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            env = os.environ.copy()
            env.update(
                {
                    "ANCHOR_ROOT": "/__SYSU_CEPHFS__",
                    "RENDERED_DIR": str(output),
                    "IOR_BIN": "/opt/ior/bin/ior",
                    "MPI_RUN": "/opt/mpi/bin/mpirun",
                }
            )
            env.pop("MPI_HOSTFILE", None)
            subprocess.run(
                [str(RENDERER)],
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            prepare = (output / "prepare_data.sh").read_text(encoding="utf-8")
            run = (output / "run_test.sh").read_text(encoding="utf-8")

        for text in (prepare, run):
            self.assertIn('ANCHOR="/__SYSU_CEPHFS__/hpc_wrf_ior_v1"', text)
            self.assertIn('IOR_BIN="/opt/ior/bin/ior"', text)
            self.assertIn('MPI_RUN="/opt/mpi/bin/mpirun"', text)
            self.assertIn('MPI_HOSTFILE=""', text)
            self.assertIn('NP="4"', text)
            self.assertIn('API="POSIX"', text)
            self.assertIn('BLOCK_SIZE="64000m"', text)
            self.assertIn('TRANSFER_SIZE="4m"', text)
            self.assertIn('SEGMENT_COUNT="1"', text)
            self.assertIn("--posix.odirect", text)
            self.assertIn("-F", text)
            self.assertNotRegex(text, r"@[A-Z_][A-Z_]*@")

        self.assertEqual(4 * 64000 * 3 / 1024, 750)
        self.assertIn('--posix.odirect -F -w -k -e', prepare)
        self.assertIn('--posix.odirect -F -r -k', run)
        self.assertNotRegex(prepare, re.compile(r"(?:^|\s)-r(?:\s|$)", re.M))
        self.assertNotRegex(run, re.compile(r"(?:^|\s)-w(?:\s|$)", re.M))
        self.assertEqual(prepare.count("run_ior_write prepare_"), 3)
        self.assertEqual(run.count("run_ior_read "), 4)

        expected_calls = (
            'run_ior_read startup_read "$ANCHOR/startup/wrf_state"',
            'run_ior_read checkpoint_read "$ANCHOR/checkpoint/wrfrst_current"',
            'run_ior_read history_read "$ANCHOR/history/wrfout_current"',
            'run_ior_read checkpoint_reheat "$ANCHOR/checkpoint/wrfrst_current"',
        )
        positions = [run.index(call) for call in expected_calls]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('PHASE_SECONDS="150"', run)
        self.assertIn('-D "$PHASE_SECONDS"', run)
        self.assertIn('-O "minTimeDuration=$PHASE_SECONDS"', run)
        self.assertIn("-O stoneWallingWearOut=0", run)

    def test_renders_optional_mpi_hostfile(self) -> None:
        self.assertTrue(RENDERER.is_file(), "HPC IOR renderer does not exist")
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.update(
                {
                    "ANCHOR_ROOT": "/__SYSU_CEPHFS__",
                    "RENDERED_DIR": tmp,
                    "MPI_HOSTFILE": "/etc/mpi/sysu-hosts",
                }
            )
            subprocess.run([str(RENDERER)], env=env, check=True)
            run = (Path(tmp) / "run_test.sh").read_text(encoding="utf-8")
        self.assertIn('MPI_HOSTFILE="/etc/mpi/sysu-hosts"', run)
        self.assertIn('mpi_args+=(--hostfile "$MPI_HOSTFILE")', run)


if __name__ == "__main__":
    unittest.main()
