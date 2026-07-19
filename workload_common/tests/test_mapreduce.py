import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
import re

from workload_common.layout import SINGLE_LAYOUT, SYSU_LAYOUT
from workload_common.models.mapreduce import BIN_COUNT, GROUP_UNITS, RANK_COUNT, RANK_SPANS, STAGES, render
from workload_common.tests.helpers import (
    assert_run_contract,
    fsd_capacity_mib,
    rd_definitions,
    read_configs,
)


class MapReduceModelTests(unittest.TestCase):
    def test_layout_and_four_stage_pool_rotation(self) -> None:
        self.assertEqual(GROUP_UNITS, {"pool_01": 100, "pool_02": 100, "pool_03": 100, "background": 2100})
        self.assertEqual(RANK_COUNT, 100)
        self.assertEqual(BIN_COUNT, 40)
        self.assertEqual([len(span) for span in RANK_SPANS], [1] * 20 + [4] * 20)
        self.assertEqual([stage.weights for stage in STAGES], [
            (Decimal("85.41"), Decimal("0"), Decimal("0"), Decimal("14.59")),
            (Decimal("0"), Decimal("85.41"), Decimal("0"), Decimal("14.59")),
            (Decimal("0"), Decimal("0"), Decimal("85.41"), Decimal("14.59")),
            (Decimal("85.41"), Decimal("0"), Decimal("0"), Decimal("14.59")),
        ])

    def test_both_physical_layouts_render_exact_capacity(self) -> None:
        for layout, capacity, fwd_count, total_fwd_count in (
            (SINGLE_LAYOUT, 112 * 1024 + 512, 240, 720),
            (SYSU_LAYOUT, 750 * 1024, 400, 1200),
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
                self.assertNotIn("rd=transition_", run)
                assert_run_contract(self, run, expected_fwd_count=fwd_count)
                self.assertEqual(len(re.findall(r"^fwd=", run, re.MULTILINE)), total_fwd_count)
                self.assertIn("rd=reheat_pool_01,fwd=hot_pool_01*", run)


if __name__ == "__main__":
    unittest.main()
