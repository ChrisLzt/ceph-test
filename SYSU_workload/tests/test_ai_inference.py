import re
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from SYSU_workload.ai_inference_kvcache_vdbench_v1.scripts.render import render


FSD_RE = re.compile(
    r"^fsd=fsd_(kv_active|kv_next|kv_prefix)_r(\d+)_s(\d+),anchor=.*?,files=(\d+),size=(\d+)m$"
)
FWD_RE = re.compile(
    r"^fwd=(prefill_active|decode_active|prefill_next|decode_next|prefix_reuse_primary|prefix_reuse_shifted)_r(\d+)_s\d+.*?,skew=([0-9.]+)$"
)
RD_RE = re.compile(r"^rd=([^,]+).*?,elapsed=(\d+),interval=1$")


class AiInferenceRendererTests(unittest.TestCase):
    def test_renders_kv_groups_with_zipf_and_access_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            render(
                anchor_root="/__SYSU_CEPHFS__",
                output_dir=output,
                threads=1,
                phase_seconds=100,
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
            group, rank, size_name, count, size_value = match.groups()
            self.assertEqual(size_name, size_value)
            capacity = int(count) * int(size_value)
            capacities[group] += capacity
            rank_capacities[(group, int(rank))] += capacity
            files += int(count)
        self.assertEqual(
            dict(capacities),
            {"kv_active": 250 * 1024, "kv_next": 250 * 1024, "kv_prefix": 250 * 1024},
        )
        self.assertEqual(set(rank_capacities.values()), {int(12.5 * 1024)})
        self.assertEqual(files, 74400)

        actual = defaultdict(lambda: defaultdict(float))
        modes = defaultdict(set)
        elapsed = {}
        for line in run.splitlines():
            match = FWD_RE.match(line)
            if match:
                phase, rank, skew = match.groups()
                actual[phase][int(rank)] += float(skew)
                modes[phase].add("random" if "fileio=random" in line else "sequential")
                self.assertIn("xfersize=4m", line)
                continue
            match = RD_RE.match(line)
            if match:
                elapsed[match.group(1)] = int(match.group(2))

        weights = [73, 6, 3, 2] + [1] * 16
        base = {rank: weight for rank, weight in enumerate(weights, 1)}
        for phase in ("prefill_active", "decode_active", "prefill_next", "decode_next", "prefix_reuse_primary"):
            self.assertEqual(dict(actual[phase]), base)
        shifted = {((1 + offset) % 20) + 1: weight for offset, weight in enumerate(weights)}
        self.assertEqual(dict(actual["prefix_reuse_shifted"]), shifted)
        self.assertEqual(modes["prefill_active"], {"sequential"})
        self.assertEqual(modes["prefill_next"], {"sequential"})
        for phase in ("decode_active", "decode_next", "prefix_reuse_primary", "prefix_reuse_shifted"):
            self.assertEqual(modes[phase], {"random"})
        self.assertEqual(sum(elapsed.values()), 600)
        self.assertNotIn("\nhd=", run)
        self.assertNotIn("format=", run)


if __name__ == "__main__":
    unittest.main()
