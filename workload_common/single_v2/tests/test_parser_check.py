import importlib.util
from pathlib import Path
import tempfile
import unittest
from workload_common.single_v2 import core
from workload_common.single_v2.tests import test_core

class ParserTests(unittest.TestCase):
    def test_unpinned_jar_rejected_before_output_is_created(self):
        self.assertIsNotNone(importlib.util.find_spec('workload_common.single_v2.parser_check'),'audited parser entry missing')
        from workload_common.single_v2.parser_check import check
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); bundle=root/'bundle'
            core.render(test_core.CoreTests().fixture(),data_root=root/'data',output=bundle,rate=100)
            jar=root/'vdbench.jar'; jar.write_bytes(b'unapproved jar')
            with self.assertRaises(ValueError): check([bundle],jar=jar,output=root/'results')
            self.assertFalse((root/'results').exists())

if __name__=='__main__':unittest.main()
