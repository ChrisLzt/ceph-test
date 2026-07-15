import tempfile
import unittest
from pathlib import Path
import re

from workload_common.layout import SINGLE_LAYOUT, SYSU_LAYOUT
from workload_common.models.ai_training import GROUP_UNITS, PHASES, RANK_COUNT, render
from workload_common.tests.helpers import assert_run_contract, fsd_capacity_mib, fwd_definitions, rd_definitions, read_configs


class AiTrainingModelTests(unittest.TestCase):
    def test_dataset_and_ranked_checkpoint_design(self) -> None:
        self.assertEqual(GROUP_UNITS, {"dataset": 2000, "checkpoint_current": 200, "checkpoint_old": 200})
        self.assertEqual(RANK_COUNT, 100)
        self.assertEqual([phase.seconds for phase in PHASES], [160, 160, 160, 60, 60])
        self.assertEqual(
            [phase.name for phase in PHASES],
            [
                "dataset_epoch_01",
                "dataset_epoch_02",
                "dataset_epoch_03",
                "checkpoint_read_current",
                "recovery_read_old_checkpoint",
            ],
        )
        self.assertEqual([phase.hot_rank for phase in PHASES[:3]], [1, 2, 3])

    def test_both_layouts_render_five_training_phases(self) -> None:
        for layout, capacity, fwd_count in (
            (SINGLE_LAYOUT, 112 * 1024 + 512, 300),
            (SYSU_LAYOUT, 750 * 1024, 500),
        ):
            with self.subTest(layout=layout.name), tempfile.TemporaryDirectory() as tmp:
                render(layout=layout, anchor_root="/ceph", output_dir=Path(tmp), threads=1)
                prepare, run = read_configs(Path(tmp))
                self.assertEqual(fsd_capacity_mib(prepare), capacity)
                self.assertEqual(sum(phase.seconds for phase in PHASES), 600)
                rds = rd_definitions(run)
                self.assertEqual(len(rds), 5)
                self.assertEqual(
                    [int(re.search(r",elapsed=(\d+)", rd).group(1)) for rd in rds],
                    [160, 160, 160, 60, 60],
                )
                self.assertEqual(
                    sum(int(re.search(r",elapsed=(\d+)", rd).group(1)) for rd in rds),
                    600,
                )
                fwds = fwd_definitions(run)
                self.assertTrue(all("fileio=random" in line for name, line in fwds.items() if name.startswith("dataset_epoch")))
                self.assertTrue(all("fileio=sequential" in line for name, line in fwds.items() if name.startswith("checkpoint") or name.startswith("recovery")))
                self.assertNotIn("rd=transition_", run)
                assert_run_contract(self, run, expected_fwd_count=fwd_count)


if __name__ == "__main__":
    unittest.main()
