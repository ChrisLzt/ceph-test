import tempfile
import unittest
from pathlib import Path

from INSPUR_workload.ai_inference_kvcache_vdbench_v1.scripts.render import (
    render as render_inference,
)
from INSPUR_workload.ai_training_checkpoint_vdbench_v1.scripts.render import (
    render as render_training,
)
from INSPUR_workload.bigdata_mapreduce_vdbench_v1.scripts.render import (
    render as render_bigdata,
)
from INSPUR_workload.graph_graphchi_vdbench_v1.scripts.render import (
    render as render_graph,
)
from INSPUR_workload.hpc_wrf_vdbench_v1.scripts.render import render as render_hpc
from INSPUR_workload.tests.operation_helpers import assert_rd_operations
from workload_common.tests.helpers import (
    assert_run_contract,
    fsd_capacity_mib,
    rd_definitions,
    read_configs,
)


class InspurVdbenchRendererTests(unittest.TestCase):
    def render(self, renderer, **options) -> tuple[str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            renderer(
                anchor_root="/__INSPUR_CEPHFS__",
                output_dir=output,
                **options,
            )
            return read_configs(output)

    def assert_common(self, prepare: str, run: str, rd_count: int) -> None:
        self.assertEqual(fsd_capacity_mib(prepare), 3000 * 1024)
        self.assertEqual(len(rd_definitions(run)), rd_count)
        self.assertEqual(
            sum(
                int(line.split("elapsed=", 1)[1].split(",", 1)[0])
                for line in rd_definitions(run)
            ),
            600,
        )
        self.assertIn("/size_256m", prepare)
        self.assertNotIn("\nhd=", run)
        self.assertNotIn("rd=transition_", run)

    def test_mapreduce_preserves_four_read_stages_and_two_hundred_fwds(self) -> None:
        prepare, run = self.render(render_bigdata)
        self.assert_common(prepare, run, 4)
        assert_run_contract(self, run, expected_fwd_count=200)

    def test_graph_preserves_four_read_stages_and_two_hundred_fwds(self) -> None:
        prepare, run = self.render(render_graph)
        self.assert_common(prepare, run, 4)
        assert_run_contract(self, run, expected_fwd_count=200)

    def test_hpc_uses_read_write_write_read(self) -> None:
        prepare, run = self.render(render_hpc)
        self.assert_common(prepare, run, 4)
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

    def test_ai_training_uses_dataset_reads_checkpoint_write_and_recovery(self) -> None:
        prepare, run = self.render(render_training)
        self.assert_common(prepare, run, 5)
        assert_rd_operations(
            self,
            run,
            {
                "dataset_epoch_01": "read",
                "dataset_epoch_02": "read",
                "dataset_epoch_03": "read",
                "checkpoint_write_current": "write",
                "recovery_read_old_checkpoint": "read",
            },
        )

    def test_ai_inference_uses_write_prefill_and_read_decode(self) -> None:
        prepare, run = self.render(render_inference)
        self.assert_common(prepare, run, 6)
        assert_rd_operations(
            self,
            run,
            {
                "prefill_active": "write",
                "decode_active": "read",
                "prefill_next": "write",
                "decode_next": "read",
                "prefix_reuse_primary": "read",
                "prefix_reuse_shifted": "read",
            },
        )


if __name__ == "__main__":
    unittest.main()
