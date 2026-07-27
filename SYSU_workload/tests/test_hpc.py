import tempfile
import unittest
from pathlib import Path

from SYSU_workload.hpc_wrf_vdbench_v1.scripts.render import render
from SYSU_workload.tests.operation_helpers import assert_rd_operations, assert_sysu_run_contract
from workload_common.tests.helpers import fsd_capacity_mib, rd_definitions, read_configs


class HpcRendererTests(unittest.TestCase):
    def test_sysu_wrapper_renders_one_hundred_rank_wrf_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            render(anchor_root="/__SYSU_CEPHFS__", output_dir=output)
            prepare, run = read_configs(output)
        self.assertEqual(fsd_capacity_mib(prepare), 750 * 1024)
        rds = rd_definitions(run)
        self.assertEqual(len(rds), 4)
        self.assertEqual(sum(int(line.split("elapsed=", 1)[1].split(",", 1)[0]) for line in rds), 600)
        self.assertIn("/checkpoint/rank_040/size_64m", prepare)
        self.assertNotIn("fileio=random", run)
        self.assertNotIn("rd=transition_", run)
        assert_rd_operations(
            self,
            run,
            {
                "startup_read": "read",
                "checkpoint_write": "write",
                "history_write": "write",
                "checkpoint_reheat": "read",
            },
        )
        self.assertNotIn("rd=checkpoint_read,", run)
        self.assertNotIn("rd=history_read,", run)
        assert_sysu_run_contract(self, run, expected_fwd_count=200)


if __name__ == "__main__":
    unittest.main()
