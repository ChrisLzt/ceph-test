import re
import unittest

from workload_common.layout import SINGLE_LAYOUT, make_rank_buckets
from workload_common.vdbench import (
    config_header,
    fwd_line,
    rd_line,
    render_prepare_config,
)


class VdbenchEmitterTests(unittest.TestCase):
    def test_prepare_batches_no_more_than_twenty_ranks(self) -> None:
        buckets = make_rank_buckets(
            layout=SINGLE_LAYOUT,
            prefix="data",
            anchor="/mnt/cephfs/test/data",
            group="data",
            total_units=25,
            rank_count=25,
        )
        text = render_prepare_config(
            "test",
            buckets,
            threads=1,
            hd_line="hd=hd1,system=host,user=user",
            batch_rank_limit=20,
        )
        clean = [line for line in text.splitlines() if "format=(clean,only)" in line]
        create = [line for line in text.splitlines() if "format=(restart,only)" in line]
        self.assertEqual(len(clean), 2)
        self.assertEqual(len(create), 2)
        self.assertEqual([len(re.findall(r"prep_data_r\d{3}_s\d+", line)) for line in clean], [60, 15])
        self.assertIn("hd=hd1,system=host,user=user", text)

    def test_prepare_defines_every_fwd_before_the_first_rd(self) -> None:
        buckets = make_rank_buckets(
            layout=SINGLE_LAYOUT,
            prefix="data",
            anchor="/mnt/cephfs/test/data",
            group="data",
            total_units=25,
            rank_count=25,
        )
        lines = render_prepare_config("test", buckets, threads=1).splitlines()
        first_rd = next(index for index, line in enumerate(lines) if line.startswith("rd="))
        self.assertFalse(any(line.startswith("fwd=") for line in lines[first_rd + 1 :]))

    def test_sysu_header_is_host_agnostic(self) -> None:
        text = "\n".join(config_header("test", hd_line=None))
        self.assertNotIn("\nhd=", text)

    def test_fwd_has_direct_workload_contract(self) -> None:
        bucket = make_rank_buckets(
            layout=SINGLE_LAYOUT,
            prefix="data",
            anchor="/mnt/cephfs/test/data",
            group="data",
            total_units=1,
            rank_count=1,
        )[0]
        line = fwd_line(
            name="phase_data",
            bucket=bucket,
            operation="read",
            fileio="random",
            threads=1,
            skew="12.345",
        )
        self.assertIn("operation=read", line)
        self.assertIn("fileio=random", line)
        self.assertIn("fileselect=random", line)
        self.assertIn("xfersize=4m", line)
        self.assertIn("skew=12.345", line)

    def test_run_rd_uses_name_prefix_wildcard_for_large_fwd_sets(self) -> None:
        fwds = [f"epoch_01_dataset_r{rank:03d}" for rank in range(600)]
        line = rd_line(name="epoch_01", fwds=fwds, rate="max", elapsed=160)
        self.assertEqual(
            line,
            "rd=epoch_01,fwd=epoch_01*,fwdrate=max,elapsed=160,interval=1",
        )

    def test_run_rd_rejects_fwd_outside_its_name_prefix(self) -> None:
        with self.assertRaisesRegex(ValueError, "must start with epoch_01_"):
            rd_line(
                name="epoch_01",
                fwds=["epoch_01_dataset_r001", "epoch_02_dataset_r002"],
                rate="max",
                elapsed=160,
            )


if __name__ == "__main__":
    unittest.main()
