import re
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from SYSU_workload.hpc_wrf_vdbench_v1.scripts.render import render


FSD_RE = re.compile(
    r"^fsd=fsd_(startup|checkpoint|history)_r(\d+)_s(\d+),anchor=.*?,files=(\d+),size=(\d+)m$"
)
FWD_RE = re.compile(
    r"^fwd=(startup_read|checkpoint_read|history_read|checkpoint_reheat)_r(\d+)_s\d+.*?,skew=([0-9.]+)$"
)


class HpcRendererTests(unittest.TestCase):
    def test_renders_three_zipf_groups_with_checkpoint_reheat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            render(
                anchor_root="/__SYSU_CEPHFS__",
                output_dir=output,
                threads=1,
                phase_seconds=150,
                fwdrate="max",
            )
            prepare = (output / "prepare_data.vdb").read_text(encoding="utf-8")
            run = (output / "run_test.vdb").read_text(encoding="utf-8")

        capacities = defaultdict(int)
        rank_capacities = defaultdict(int)
        files = 0
        fsds = 0
        for line in prepare.splitlines():
            match = FSD_RE.match(line)
            if not match:
                continue
            group, rank, size_name, count, size_value = match.groups()
            self.assertEqual(size_name, size_value)
            capacity = int(count) * int(size_value)
            capacities[group] += capacity
            rank_capacities[(group, int(rank))] += capacity
            files += int(count)
            fsds += 1
        self.assertEqual(fsds, 300)
        self.assertEqual(dict(capacities), {group: 250 * 1024 for group in ("startup", "checkpoint", "history")})
        self.assertEqual(set(rank_capacities.values()), {int(12.5 * 1024)})
        self.assertEqual(files, 74400)

        actual = defaultdict(lambda: defaultdict(float))
        for line in run.splitlines():
            match = FWD_RE.match(line)
            if match:
                phase, rank, skew = match.groups()
                actual[phase][int(rank)] += float(skew)
                self.assertIn("fileio=sequential", line)
                self.assertIn("xfersize=4m", line)
        expected_weights = [73, 6, 3, 2] + [1] * 16
        self.assertEqual(set(actual), {"startup_read", "checkpoint_read", "history_read", "checkpoint_reheat"})
        for phase in actual:
            self.assertEqual([actual[phase][rank] for rank in range(1, 21)], expected_weights)
        self.assertEqual(actual["checkpoint_read"], actual["checkpoint_reheat"])
        self.assertNotIn("\nhd=", run)
        self.assertNotIn("format=", run)


if __name__ == "__main__":
    unittest.main()
