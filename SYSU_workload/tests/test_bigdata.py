import re
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from SYSU_workload.bigdata_mapreduce_vdbench_v1.scripts.render import render


FSD_RE = re.compile(
    r"^fsd=fsd_(pool_\d+)_s(\d+),anchor=.*?,files=(\d+),size=(\d+)m$"
)
FWD_RE = re.compile(
    r"^fwd=(hot_a|hot_b|hot_c|reheat_a)_(pool_\d+)_s\d+.*?,skew=([0-9.]+)$"
)


class BigdataRendererTests(unittest.TestCase):
    def test_renders_exact_capacity_and_source_stage_weights(self) -> None:
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

        self.assertNotIn("\nhd=", prepare)
        self.assertNotIn("\nhd=", run)
        self.assertNotIn("format=", run)
        self.assertIn("format=(clean,only)", prepare)
        self.assertIn("format=(restart,only)", prepare)

        capacities = defaultdict(int)
        files = 0
        sizes = set()
        fsds = 0
        for line in prepare.splitlines():
            match = FSD_RE.match(line)
            if not match:
                continue
            pool, size_name, file_count, size_value = match.groups()
            self.assertEqual(size_name, size_value)
            capacities[pool] += int(file_count) * int(size_value)
            files += int(file_count)
            sizes.add(int(size_value))
            fsds += 1

        self.assertEqual(fsds, 20)
        self.assertEqual(sizes, {4, 8, 16, 32, 64})
        self.assertEqual(
            dict(capacities),
            {"pool_01": 30 * 1024, "pool_02": 30 * 1024, "pool_03": 30 * 1024, "pool_04": 660 * 1024},
        )
        self.assertEqual(sum(capacities.values()), 750 * 1024)
        self.assertEqual(files, 74400)

        actual = defaultdict(lambda: defaultdict(float))
        for line in run.splitlines():
            match = FWD_RE.match(line)
            if match:
                phase, pool, skew = match.groups()
                actual[phase][pool] += float(skew)
                self.assertIn("xfersize=4m", line)

        expected = {
            "hot_a": {"pool_01": 85, "pool_02": 1, "pool_03": 1, "pool_04": 13},
            "hot_b": {"pool_01": 1, "pool_02": 85, "pool_03": 1, "pool_04": 13},
            "hot_c": {"pool_01": 1, "pool_02": 1, "pool_03": 85, "pool_04": 13},
            "reheat_a": {"pool_01": 85, "pool_02": 1, "pool_03": 1, "pool_04": 13},
        }
        self.assertEqual(set(actual), set(expected))
        for phase, pools in expected.items():
            self.assertEqual(dict(actual[phase]), pools)


if __name__ == "__main__":
    unittest.main()
