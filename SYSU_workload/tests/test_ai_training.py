import re
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from SYSU_workload.ai_training_checkpoint_vdbench_v1.scripts.render import render


FSD_RE = re.compile(
    r"^fsd=fsd_(dataset_r\d+|checkpoint_current|checkpoint_old)_s(\d+),anchor=.*?,files=(\d+),size=(\d+)m$"
)
DATASET_FWD_RE = re.compile(r"^fwd=(dataset_epoch_\d+)_r(\d+)_s\d+.*?,skew=([0-9.]+)$")
CHECKPOINT_FWD_RE = re.compile(
    r"^fwd=(checkpoint_read_current_first|checkpoint_read_current_second|recovery_read_old_checkpoint)_s\d+.*?,skew=([0-9.]+)$"
)
RD_RE = re.compile(r"^rd=([^,]+).*?,elapsed=(\d+),interval=1$")


class AiTrainingRendererTests(unittest.TestCase):
    def test_renders_dataset_zipf_and_checkpoint_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            render(
                anchor_root="/__SYSU_CEPHFS__",
                output_dir=output,
                threads=1,
                dataset_phase_seconds=160,
                checkpoint_phase_seconds=40,
                fwdrate="max",
            )
            prepare = (output / "prepare_data.vdb").read_text(encoding="utf-8")
            run = (output / "run_test.vdb").read_text(encoding="utf-8")

        capacities = defaultdict(int)
        rank_capacities = defaultdict(int)
        files = 0
        for line in prepare.splitlines():
            match = FSD_RE.match(line)
            if not match:
                continue
            group, size_name, count, size_value = match.groups()
            self.assertEqual(size_name, size_value)
            capacity = int(count) * int(size_value)
            files += int(count)
            if group.startswith("dataset_r"):
                capacities["dataset"] += capacity
                rank_capacities[int(group.removeprefix("dataset_r"))] += capacity
            else:
                capacities[group] += capacity
        self.assertEqual(
            dict(capacities),
            {"dataset": 650 * 1024, "checkpoint_current": 50 * 1024, "checkpoint_old": 50 * 1024},
        )
        self.assertEqual(set(rank_capacities.values()), {int(32.5 * 1024)})
        self.assertEqual(files, 74400)

        dataset = defaultdict(lambda: defaultdict(float))
        checkpoints = defaultdict(float)
        elapsed = {}
        for line in run.splitlines():
            match = DATASET_FWD_RE.match(line)
            if match:
                phase, rank, skew = match.groups()
                dataset[phase][int(rank)] += float(skew)
                self.assertIn("fileio=random", line)
                self.assertIn("xfersize=4m", line)
                continue
            match = CHECKPOINT_FWD_RE.match(line)
            if match:
                phase, skew = match.groups()
                checkpoints[phase] += float(skew)
                self.assertIn("fileio=sequential", line)
                continue
            match = RD_RE.match(line)
            if match:
                elapsed[match.group(1)] = int(match.group(2))

        weights = [74, 5, 3, 2] + [1] * 16
        for epoch, hot_rank in enumerate((1, 2, 3), 1):
            phase = f"dataset_epoch_{epoch:02d}"
            expected = {
                ((hot_rank - 1 + offset) % 20) + 1: weight
                for offset, weight in enumerate(weights)
            }
            self.assertEqual(dict(dataset[phase]), expected)
        self.assertEqual(
            dict(checkpoints),
            {
                "checkpoint_read_current_first": 100,
                "checkpoint_read_current_second": 100,
                "recovery_read_old_checkpoint": 100,
            },
        )
        self.assertEqual(sum(elapsed.values()), 600)
        self.assertNotIn("\nhd=", run)
        self.assertNotIn("format=", run)


if __name__ == "__main__":
    unittest.main()
