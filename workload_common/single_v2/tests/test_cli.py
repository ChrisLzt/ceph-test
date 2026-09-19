import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

class CLITests(unittest.TestCase):
    def test_all_render_and_validate_without_data_directory(self):
        self.assertIsNotNone(importlib.util.find_spec('workload_common.single_v2.__main__'), 'suite CLI missing')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            args=[sys.executable,'-m','workload_common.single_v2']
            result=subprocess.run(args+['render','--case','all','--data-root',str(root/'data'),'--output-root',str(root/'configs')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertFalse((root/'data').exists())
            result=subprocess.run(args+['validate','--case','all','--output-root',str(root/'configs')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('658.1700439453125',result.stdout)

if __name__=='__main__':unittest.main()
