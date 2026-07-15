import tempfile
import unittest
from pathlib import Path
import re

from workload_common.layout import SINGLE_LAYOUT, SYSU_LAYOUT
from workload_common.models.graphchi import RANK_COUNT, SHARD_UNITS, STAGES, render
from workload_common.tests.helpers import assert_run_contract, fsd_capacity_mib, rd_definitions, read_configs


class GraphChiModelTests(unittest.TestCase):
    def test_four_equal_shards_use_one_hundred_zipf_ranks(self) -> None:
        self.assertEqual(STAGES, (0, 1, 2, 3))
        self.assertEqual(SHARD_UNITS, 600)
        self.assertEqual(RANK_COUNT, 100)

    def test_four_shards_with_internal_zipf_ranks_render(self) -> None:
        for layout, capacity, fwd_count in (
            (SINGLE_LAYOUT, 112 * 1024 + 512, 300),
            (SYSU_LAYOUT, 750 * 1024, 500),
        ):
            with self.subTest(layout=layout.name), tempfile.TemporaryDirectory() as tmp:
                render(layout=layout, anchor_root="/ceph", output_dir=Path(tmp), threads=1)
                prepare, run = read_configs(Path(tmp))
                self.assertEqual(fsd_capacity_mib(prepare), capacity)
                self.assertIn("/shard_00/rank_100/size_4m", prepare)
                self.assertNotIn("window_src", prepare)
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
