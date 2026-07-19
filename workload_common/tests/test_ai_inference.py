import tempfile
import unittest
from pathlib import Path
import re

from workload_common.layout import SINGLE_LAYOUT, SYSU_LAYOUT
from workload_common.models.ai_inference import BIN_COUNT, GROUP_UNITS, PHASES, RANK_COUNT, RANK_SPANS, render
from workload_common.tests.helpers import assert_run_contract, fsd_capacity_mib, fwd_definitions, rd_definitions, read_configs


class AiInferenceModelTests(unittest.TestCase):
    def test_kvcache_phase_design(self) -> None:
        self.assertEqual(GROUP_UNITS, {"kv_active": 800, "kv_next": 800, "kv_prefix": 800})
        self.assertEqual(RANK_COUNT, 100)
        self.assertEqual(BIN_COUNT, 40)
        self.assertEqual([len(span) for span in RANK_SPANS], [1] * 20 + [4] * 20)
        self.assertEqual([phase.seconds for phase in PHASES], [100] * 6)
        self.assertEqual([phase.hot_rank for phase in PHASES], [1, 1, 1, 1, 1, 2])

    def test_both_layouts_render_six_inference_phases(self) -> None:
        for layout, capacity, fwd_count, total_fwd_count in (
            (SINGLE_LAYOUT, 112 * 1024 + 512, 120, 720),
            (SYSU_LAYOUT, 750 * 1024, 200, 1200),
        ):
            with self.subTest(layout=layout.name), tempfile.TemporaryDirectory() as tmp:
                render(layout=layout, anchor_root="/ceph", output_dir=Path(tmp), threads=1)
                prepare, run = read_configs(Path(tmp))
                self.assertEqual(fsd_capacity_mib(prepare), capacity)
                rds = rd_definitions(run)
                self.assertEqual(len(rds), 6)
                self.assertEqual(
                    [int(re.search(r",elapsed=(\d+)", rd).group(1)) for rd in rds],
                    [100] * 6,
                )
                self.assertEqual(
                    sum(int(re.search(r",elapsed=(\d+)", rd).group(1)) for rd in rds),
                    600,
                )
                self.assertNotIn("rd=transition_", run)
                fwds = fwd_definitions(run)
                self.assertTrue(all("fileio=sequential" in line for name, line in fwds.items() if name.startswith("prefill")))
                self.assertTrue(all("fileio=random" in line for name, line in fwds.items() if name.startswith("decode") or name.startswith("prefix")))
                assert_run_contract(self, run, expected_fwd_count=fwd_count)
                self.assertEqual(len(fwd_definitions(run)), total_fwd_count)


if __name__ == "__main__":
    unittest.main()
