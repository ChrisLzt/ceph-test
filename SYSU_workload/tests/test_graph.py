import re
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from SYSU_workload.graph_graphchi_vdbench_v1.scripts.render import render


FSD_RE = re.compile(r"^fsd=fsd_(shard_\d+)_s(\d+),anchor=.*?,files=(\d+),size=(\d+)m$")
FWD_RE = re.compile(
    r"^fwd=(iter\d+_i\d+)_(shard_\d+)_s\d+.*?,skew=([0-9.]+)$"
)


class GraphRendererTests(unittest.TestCase):
    def test_renders_equal_shards_and_graphchi_stage_weights(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            render(
                anchor_root="/__SYSU_CEPHFS__",
                output_dir=output,
                threads=1,
                phase_seconds=120,
                fwdrate="max",
            )
            prepare = (output / "prepare_data.vdb").read_text(encoding="utf-8")
            run = (output / "run_test.vdb").read_text(encoding="utf-8")

        self.assertNotIn("\nhd=", run)
        self.assertNotIn("format=", run)
        capacities = defaultdict(int)
        files = 0
        for line in prepare.splitlines():
            match = FSD_RE.match(line)
            if not match:
                continue
            shard, size_name, count, size_value = match.groups()
            self.assertEqual(size_name, size_value)
            capacities[shard] += int(count) * int(size_value)
            files += int(count)
        self.assertEqual(dict(capacities), {f"shard_{i:02d}": 187.5 * 1024 for i in range(4)})
        self.assertEqual(sum(capacities.values()), 750 * 1024)
        self.assertEqual(files, 74400)

        actual = defaultdict(lambda: defaultdict(float))
        for line in run.splitlines():
            match = FWD_RE.match(line)
            if match:
                phase, shard, skew = match.groups()
                actual[phase][shard] += float(skew)
                self.assertIn("xfersize=4m", line)

        expected_rows = {
            "iter1_i0": [75, 13, 6, 6],
            "iter1_i1": [6, 75, 13, 6],
            "iter1_i2": [6, 6, 75, 13],
            "iter1_i3": [13, 6, 6, 75],
            "iter2_i0": [75, 13, 6, 6],
        }
        self.assertEqual(set(actual), set(expected_rows))
        for phase, weights in expected_rows.items():
            self.assertEqual(
                dict(actual[phase]),
                {f"shard_{i:02d}": weight for i, weight in enumerate(weights)},
            )


if __name__ == "__main__":
    unittest.main()
