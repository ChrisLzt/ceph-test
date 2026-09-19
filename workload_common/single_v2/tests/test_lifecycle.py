import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from workload_common.single_v2.tests import test_core
from workload_common.single_v2.core import render

class LifecycleTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('workload_common.single_v2.lifecycle'), 'safe lifecycle is missing')
        from workload_common.single_v2 import lifecycle
        return lifecycle

    def bundle(self, root):
        m=test_core.CoreTests().fixture()
        manifest=render(m,data_root=root/'data',output=root/'configs',rate=100)
        return manifest

    def test_prepare_requires_explicit_execution_without_side_effects(self):
        api=self.api()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.bundle(root)
            with self.assertRaises(ValueError):
                api.prepare(root/'configs',vdbench=Path('/missing'),output=root/'results',execute=False)
            self.assertFalse((root/'data').exists())

    def test_inventory_rejects_missing_sparse_wrong_size_and_symlinks(self):
        api=self.api()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); m=self.bundle(root); anchor=Path(m['bins'][0]['anchor'])/'vdb.1_1.dir'; anchor.mkdir(parents=True)
            with self.assertRaises(ValueError): api.verify_inventory(m)
            for i in range(4): (anchor/f'vdb_f{i:04d}.file').write_bytes(b'x'*65536)
            self.assertEqual(api.verify_inventory(m)['file_count'],4)
            (anchor/'vdb_f0000.file').rename(anchor/'vdb_f9999.file')
            with self.assertRaises(ValueError): api.verify_inventory(m)
            (anchor/'vdb_f9999.file').rename(anchor/'vdb_f0000.file')
            (anchor/'vdb_f0000.file').write_bytes(b'x')
            with self.assertRaises(ValueError): api.verify_inventory(m)
            (anchor/'vdb_f0000.file').unlink()
            (anchor/'vdb_f0000.file').symlink_to(anchor/'vdb_f0001.file')
            with self.assertRaises(ValueError): api.verify_inventory(m)

    def test_preflight_rejects_local_mount_and_existing_data(self):
        api=self.api()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); m=self.bundle(root)
            with self.assertRaises(ValueError): api.preflight(root/'configs')
            with patch.object(api,'mount_info',return_value={'target':str(root),'fstype':'ceph','source':'test'}):
                report=api.preflight(root/'configs')
                self.assertGreaterEqual(report['available_bytes'],m['capacity_bytes'])
                (root/'data').mkdir()
                (root/'data'/'old').write_text('preserve')
                with self.assertRaises(ValueError): api.preflight(root/'configs')
                self.assertEqual((root/'data'/'old').read_text(),'preserve')

    def test_output_checks_all_cases_before_creating_any_directory(self):
        api=self.api()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); m=self.bundle(root)
            other={**m,'id':'other_case','data_root':str(root/'other_data')}
            existing=root/'results'/'other_case';existing.mkdir(parents=True)
            with self.assertRaises(ValueError):
                api.validate_outputs([m,other],[root/'configs'],root/'results')
            self.assertFalse((root/'results'/m['id']).exists())
            with self.assertRaises(ValueError):
                api.validate_outputs([m,other],[root/'configs'],root/'other_data'/'results')
            with self.assertRaises(ValueError):
                api.validate_outputs([m],[root/'configs'],root/'configs'/'results')

    def test_run_requires_ready_marker_before_executor(self):
        api=self.api()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.bundle(root)
            with self.assertRaises(ValueError): api.check_ready(root/'configs')

    def test_ai_current_runs_direct_vdbench_without_ses(self):
        import os
        import sys
        from workload_common.single_v2 import __main__ as cli, CASES
        from workload_common.single_v2.current_suite import build_current
        api = self.api()
        for case in ('ai_training', 'ai_inference'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                bundle = root/'configs'/CASES[case]/'rendered'
                render(build_current(case), data_root=root/'data', output=bundle, rate='max')
                args = ['single_v2', 'run', '--case', case, '--profile', 'current',
                        '--output-root', str(root/'configs'), '--results', str(root/'results'),
                        '--vdbench', '/usr/bin/true', '--execute']
                with patch.dict(os.environ, {}, clear=True), patch.object(sys, 'argv', args), \
                     patch.object(api, 'check_ready', return_value={'state':'ready'}), \
                     patch.object(api.subprocess, 'run') as execute:
                    self.assertEqual(cli.main(), 0)
                    execute.assert_called_once_with(['/usr/bin/true', '-f', str(bundle/'run_current.vdb'),
                                                     '-o', str(root/'results'/CASES[case])], check=True)
                self.assertFalse((root/'data').exists())

if __name__=='__main__': unittest.main()
