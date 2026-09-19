import unittest
from workload_common.single_v2 import CASES,build,core
from workload_common.single_v2.current_suite import build_current, data_root
from workload_common.single_v2.phase_zipf import transform
from workload_common.single_v2.baleen_static import build as static

class CurrentSuiteTests(unittest.TestCase):
    def test_selected_semantics_and_data_roots(self):
        total=0
        for case in CASES:
            model=build_current(case)
            original=static() if case=='baleen' else transform(build(case),case)
            profile='baseline' if case=='baleen' else 'phase_zipf099'
            self.assertEqual(model['profiles']['current'],original['profiles'][profile])
            self.assertEqual(model['bins'],original['bins'])
            total+=core.validate_model(model)
            self.assertLessEqual(max(len(p['lanes']) for p in model['profiles']['current']),256)
            self.assertTrue(str(data_root(case)).endswith(CASES[case]))
        self.assertEqual(total/2**30,658.1700439453125)
        self.assertEqual(len({data_root(c) for c in CASES}),5)

    def test_cli_preview_and_authorization_without_data_io(self):
        import json, subprocess, sys, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config=root/'config';data=root/'data'
            base=[sys.executable,'-m','workload_common.single_v2']
            opts=['--design','current','--profile','current','--output-root',str(config),'--data-root',str(data),'--rate','max']
            result=subprocess.run(base+['render']+opts,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertFalse(data.exists())
            result=subprocess.run(base+['preview']+opts,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            report=json.loads(result.stdout)
            self.assertEqual(len(report['cases']),5)
            self.assertEqual([len(c['phases']) for c in report['cases']],[1,4,7,1,1])
            self.assertTrue(all(c['profile']=='current' for c in report['cases']))
            self.assertFalse(data.exists())
            for action in ('prepare','run'):
                result=subprocess.run(base+[action]+opts,capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('requires explicit --execute',result.stderr)
            self.assertFalse(data.exists())
