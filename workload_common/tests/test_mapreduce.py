import tempfile
import unittest
from pathlib import Path
import re

from workload_common.layout import SINGLE_LAYOUT, SYSU_LAYOUT
from workload_common.models.mapreduce import GROUP_UNITS, RANK_COUNT, STAGES, render
from workload_common.tests.helpers import (
    assert_run_contract,
    fsd_capacity_mib,
    rd_definitions,
    read_configs,
)


class MapReduceModelTests(unittest.TestCase):
    def test_layout_and_four_stage_pool_rotation(self) -> None:
        self.assertEqual(GROUP_UNITS, {"pool_01": 96, "pool_02": 96, "pool_03": 96, "background": 2112})
        self.assertEqual(RANK_COUNT, 24)
        self.assertEqual([stage.weights for stage in STAGES], [
            (85, 1, 1, 13), (1, 85, 1, 13), (1, 1, 85, 13), (85, 1, 1, 13),
        ])

    def test_both_physical_layouts_render_exact_capacity(self) -> None:
        for layout, capacity, fwd_count in (
            (SINGLE_LAYOUT, 112 * 1024 + 512, 288),
            (SYSU_LAYOUT, 750 * 1024, 480),
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


if __name__ == "__main__":
    unittest.main()
