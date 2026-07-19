import tempfile
import unittest
from pathlib import Path

from SYSU_workload.ai_training_checkpoint_vdbench_v1.scripts.render import render
from workload_common.tests.helpers import assert_run_contract, fsd_capacity_mib, rd_definitions, read_configs


class AiTrainingRendererTests(unittest.TestCase):
    def test_sysu_wrapper_renders_ranked_dataset_and_checkpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            render(anchor_root="/__SYSU_CEPHFS__", output_dir=output)
            prepare, run = read_configs(output)
        self.assertEqual(fsd_capacity_mib(prepare), 750 * 1024)
        self.assertEqual(len(rd_definitions(run)), 5)
        self.assertIn("/checkpoint_old/rank_040/size_64m", prepare)
        self.assertEqual(sum(int(line.split("elapsed=", 1)[1].split(",", 1)[0]) for line in rd_definitions(run)), 600)
        self.assertNotIn("rd=transition_", run)
        assert_run_contract(self, run, expected_fwd_count=200)


if __name__ == "__main__":
    unittest.main()
