import tempfile
import unittest
from pathlib import Path
import re

from workload_common.layout import SINGLE_LAYOUT, SYSU_LAYOUT
from workload_common.models.hpc import BIN_COUNT, GROUP_UNITS, PHASES, RANK_COUNT, RANK_SPANS, render
from workload_common.tests.helpers import assert_run_contract, fsd_capacity_mib, fwd_definitions, rd_definitions, read_configs


class HpcModelTests(unittest.TestCase):
    def test_wrf_groups_and_reheat_stage(self) -> None:
        self.assertEqual(GROUP_UNITS, {"startup": 800, "checkpoint": 800, "history": 800})
        self.assertEqual(RANK_COUNT, 100)
        self.assertEqual(BIN_COUNT, 40)
        self.assertEqual([len(span) for span in RANK_SPANS], [1] * 20 + [4] * 20)
        self.assertEqual([phase.group for phase in PHASES], ["startup", "checkpoint", "history", "checkpoint"])

    def test_both_layouts_render_four_sequential_read_stages(self) -> None:
        for layout, capacity, fwd_count, total_fwd_count in (
            (SINGLE_LAYOUT, 112 * 1024 + 512, 120, 360),
            (SYSU_LAYOUT, 750 * 1024, 200, 600),
        ):
            with self.subTest(layout=layout.name), tempfile.TemporaryDirectory() as tmp:
                render(layout=layout, anchor_root="/ceph", output_dir=Path(tmp), threads=1)
                prepare, run = read_configs(Path(tmp))
                self.assertEqual(fsd_capacity_mib(prepare), capacity)
                rds = rd_definitions(run)
                self.assertEqual(len(rds), 4)
                self.assertEqual(
                    [int(re.search(r",elapsed=(\d+)", rd).group(1)) for rd in rds],
                    [150, 150, 150, 150],
                )
                self.assertEqual(
                    sum(int(re.search(r",elapsed=(\d+)", rd).group(1)) for rd in rds),
                    600,
                )
                self.assertNotIn("fileio=random", run)
                self.assertNotIn("rd=transition_", run)
                assert_run_contract(self, run, expected_fwd_count=fwd_count)
                self.assertEqual(len(fwd_definitions(run)), total_fwd_count)
                self.assertIn("rd=checkpoint_reheat,fwd=checkpoint_read*", run)


if __name__ == "__main__":
    unittest.main()
