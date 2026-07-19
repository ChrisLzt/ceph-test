from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import re
import tempfile
import unittest

from no_migration_workload.scripts.render import render


CASES = {
    "bigdata_mapreduce_no_migration_v1": {
        "durations": [600],
        "fileio": ["sequential"],
        "fwd_count": 240,
        "definition_count": 240,
        "required": [
            "/bigdata_mapreduce_vdbench_v1/pool_01/",
            "/bigdata_mapreduce_vdbench_v1/background/",
        ],
        "forbidden": [
            "/bigdata_mapreduce_vdbench_v1/pool_02/",
            "/bigdata_mapreduce_vdbench_v1/pool_03/",
        ],
    },
    "graph_graphchi_no_migration_v1": {
        "durations": [600],
        "fileio": ["sequential"],
        "fwd_count": 120,
        "definition_count": 120,
        "required": ["/graph_graphchi_vdbench_v1/shard_00/"],
        "forbidden": ["/shard_01/", "/shard_02/", "/shard_03/"],
    },
    "hpc_wrf_no_migration_v1": {
        "durations": [600],
        "fileio": ["sequential"],
        "fwd_count": 120,
        "definition_count": 120,
        "required": ["/hpc_wrf_vdbench_v1/startup/"],
        "forbidden": ["/checkpoint/", "/history/"],
    },
    "ai_training_no_migration_v1": {
        "durations": [160, 160, 160, 60, 60],
        "fileio": ["random", "random", "random", "sequential", "sequential"],
        "fwd_count": 120,
        "definition_count": 240,
        "required": ["/ai_training_checkpoint_vdbench_v1/dataset/"],
        "forbidden": ["/checkpoint_current/", "/checkpoint_old/"],
    },
    "ai_inference_no_migration_v1": {
        "durations": [100, 100, 100, 100, 100, 100],
        "fileio": ["sequential", "random", "sequential", "random", "random", "random"],
        "fwd_count": 120,
        "definition_count": 240,
        "required": ["/ai_inference_kvcache_vdbench_v1/kv_active/"],
        "forbidden": ["/kv_next/", "/kv_prefix/"],
    },
}


def parameter(line: str, name: str) -> str:
    match = re.search(rf"(?:^|,){re.escape(name)}=([^,]+)", line)
    if not match:
        raise AssertionError(f"missing {name}= in {line}")
    return match.group(1)


class NoMigrationModelTests(unittest.TestCase):
    def test_all_phases_keep_one_identical_hot_profile(self) -> None:
        for workload, expected in CASES.items():
            with self.subTest(workload=workload), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp)
                render(
                    workload=workload,
                    anchor_root="/__NO_MIGRATION_DATA__",
                    output_dir=output,
                    hd_line="hd=default,vdbench=/vdbench,user=test,shell=ssh\nhd=hd1,system=host",
                )
                config = output / "run_test.vdb"
                self.assertTrue(config.is_file())
                self.assertFalse((output / "prepare_data.vdb").exists())
                text = config.read_text(encoding="utf-8")

                fsds = {
                    line.split(",", 1)[0].split("=", 1)[1]: line
                    for line in text.splitlines()
                    if line.startswith("fsd=fsd_")
                }
                fwds = {
                    line.split(",", 1)[0].split("=", 1)[1]: line
                    for line in text.splitlines()
                    if line.startswith("fwd=")
                }
                rds = [line for line in text.splitlines() if line.startswith("rd=")]
                self.assertEqual(len(fwds), expected["definition_count"])

                self.assertEqual(
                    [int(parameter(line, "elapsed")) for line in rds],
                    expected["durations"],
                )
                self.assertEqual(sum(expected["durations"]), 600)

                signatures = []
                fileio_modes = []
                for rd in rds:
                    selector = parameter(rd, "fwd")
                    self.assertTrue(selector.endswith("*"))
                    selected = [
                        line
                        for fwd, line in fwds.items()
                        if fwd.startswith(selector[:-1])
                    ]
                    self.assertEqual(len(selected), expected["fwd_count"])
                    self.assertEqual(
                        sum((Decimal(parameter(line, "skew")) for line in selected), Decimal("0")),
                        Decimal("100"),
                    )
                    signatures.append(
                        sorted((parameter(line, "fsd"), parameter(line, "skew")) for line in selected)
                    )
                    fileio_modes.append({parameter(line, "fileio") for line in selected})
                    self.assertTrue(all(parameter(line, "operation") == "read" for line in selected))
                    self.assertTrue(all(parameter(line, "xfersize") == "4m" for line in selected))

                self.assertTrue(all(signature == signatures[0] for signature in signatures[1:]))
                self.assertEqual(fileio_modes, [{mode} for mode in expected["fileio"]])
                self.assertIn("fsd=default,depth=1,width=1,shared=yes,openflags=o_direct", text)
                self.assertNotIn("operation=create", text)
                for fragment in expected["required"]:
                    self.assertIn(fragment, text)
                for fragment in expected["forbidden"]:
                    self.assertNotIn(fragment, text)

                first_selector = parameter(rds[0], "fwd")[:-1]
                first_profile = {
                    name: line for name, line in fwds.items() if name.startswith(first_selector)
                }
                rank_one = sum(
                    Decimal(parameter(line, "skew"))
                    for line in first_profile.values()
                    if "_r001_" in parameter(line, "fsd")
                )
                rank_two = sum(
                    Decimal(parameter(line, "skew"))
                    for line in first_profile.values()
                    if "_r002_" in parameter(line, "fsd")
                )
                self.assertGreater(rank_one, rank_two)
                self.assertTrue(all(parameter(line, "fsd") in fsds for line in fwds.values()))

    def test_mapreduce_freezes_the_paper_pool_share_at_hot_pool_01(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            render(
                workload="bigdata_mapreduce_no_migration_v1",
                anchor_root="/__NO_MIGRATION_DATA__",
                output_dir=output,
                hd_line=None,
            )
            text = (output / "run_test.vdb").read_text(encoding="utf-8")
            fwds = [line for line in text.splitlines() if line.startswith("fwd=fixed_pool01_")]
            totals = {}
            for line in fwds:
                fsd = parameter(line, "fsd")
                group = next(
                    name
                    for name in ("pool_01", "pool_02", "pool_03", "background")
                    if f"fsd_{name}_" in fsd
                )
                totals[group] = totals.get(group, Decimal("0")) + Decimal(parameter(line, "skew"))
            self.assertEqual(
                totals,
                {
                    "pool_01": Decimal("85.41"),
                    "background": Decimal("14.59"),
                },
            )


if __name__ == "__main__":
    unittest.main()
