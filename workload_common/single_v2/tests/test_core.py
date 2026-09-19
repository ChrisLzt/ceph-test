import importlib.util
import tempfile
import unittest
from pathlib import Path

class CoreTests(unittest.TestCase):
    def core(self):
        self.assertIsNotNone(importlib.util.find_spec("workload_common.single_v2.core"), "new renderer is missing")
        from workload_common.single_v2 import core
        return core

    def fixture(self):
        return {"id":"test_case_v2", "bins":[{"id":"a","files":4,"size_bytes":65536,"group":"data"}], "profiles":{"baseline":[{"name":"steady","seconds":600,"lanes":[{"bin":"a","weight":1,"xfersize":8192,"fileio":"sequential","fileselect":"sequential","threads":1}]}]}, "provenance":{}}

    def test_render_writes_only_config_and_manifest(self):
        core=self.core()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); data=root/"absent_data"; out=root/"configs"
            manifest=core.render(self.fixture(), data_root=data, output=out, rate=100)
            self.assertFalse(data.exists())
            self.assertEqual(manifest["capacity_bytes"],262144)
            self.assertEqual(manifest["max_run_fwd"],1)
            text=(out/"prepare_data.vdb").read_text()
            self.assertNotIn("clean",text)
            self.assertIn("format=(restart,only)",text)
            self.assertIn("fwd=format,threads=1",text)
            self.assertEqual(core.validate_bundle(out)["layout_sha256"],manifest["layout_sha256"])
            (out/"run_baseline.vdb").write_text((out/"run_baseline.vdb").read_text().replace("operation=read","operation=write"))
            with self.assertRaises(ValueError): core.validate_bundle(out)

    def test_rejects_invalid_concurrency_and_transfer(self):
        core=self.core(); m=self.fixture(); m["bins"][0]["files"]=1
        m["profiles"]["baseline"][0]["lanes"]*=2
        with self.assertRaises(ValueError): core.validate_model(m)
        m=self.fixture(); m["profiles"]["baseline"][0]["lanes"][0]["xfersize"]=131072
        with self.assertRaises(ValueError): core.validate_model(m)

    def test_histogram_percentages_sum_exactly_in_double_arithmetic(self):
        from decimal import Decimal
        values=self.core().percentages(range(1,101))
        self.assertEqual(sum(map(float,values)),100.0)
        self.assertEqual(sum(map(Decimal,values)),Decimal(100))

    def test_caps_expanded_fwd_and_checks_all_profiles(self):
        core=self.core(); m=self.fixture(); m["bins"][0]["files"]=600
        m["profiles"]["baseline"][0]["lanes"]*=513
        with self.assertRaises(ValueError): core.validate_model(m)
        m=self.fixture(); m["profiles"]["bad"]=[]
        with self.assertRaises(ValueError): core.validate_model(m)

    def test_render_rejects_output_symlink_into_data(self):
        core=self.core()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/"data").mkdir(); (root/"alias").symlink_to(root/"data",target_is_directory=True)
            with self.assertRaises(ValueError):
                core.render(self.fixture(),data_root=root/"data",output=root/"alias"/"configs",rate=100)
            self.assertFalse((root/"data"/"configs").exists())

    def test_same_data_for_profiles_and_exact_skew(self):
        core=self.core(); m=self.fixture(); m["profiles"]["zipf099"]=m["profiles"]["baseline"]
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"configs"
            a=core.render(m,data_root=Path(tmp)/"data",output=out,rate=100)
            core.validate_bundle(out)
            self.assertEqual(set(a["profiles"]),{"baseline","zipf099"})
            self.assertEqual(a["profiles"]["baseline"][0]["fwd_count"],1)

if __name__ == "__main__": unittest.main()
