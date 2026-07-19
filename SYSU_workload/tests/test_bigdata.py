import tempfile
import unittest
from pathlib import Path

from SYSU_workload.bigdata_mapreduce_vdbench_v1.scripts.render import render
from workload_common.tests.helpers import assert_run_contract, fsd_capacity_mib, rd_definitions, read_configs


class BigdataRendererTests(unittest.TestCase):
    def test_sysu_wrapper_renders_ranked_pool_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            render(anchor_root="/__SYSU_CEPHFS__", output_dir=output)
            prepare, run = read_configs(output)
        self.assertEqual(fsd_capacity_mib(prepare), 750 * 1024)
        rds = rd_definitions(run)
        self.assertEqual(len(rds), 4)
        self.assertEqual(sum(int(line.split("elapsed=", 1)[1].split(",", 1)[0]) for line in rds), 600)
        self.assertIn("/background/rank_040/size_64m", prepare)
        self.assertNotIn("\nhd=", run)
        self.assertNotIn("rd=transition_", run)
        assert_run_contract(self, run, expected_fwd_count=400)


if __name__ == "__main__":
    unittest.main()
