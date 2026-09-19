"""Adapter safety and boundary tests; never execute SES or Vdbench."""
import hashlib
import importlib.util
import json
import os
import socket
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'ses_adapter.py'


class SESAdapterTest(unittest.TestCase):
    def module(self):
        self.assertTrue(MODULE.exists(), 'SES adapter implementation is missing')
        spec = importlib.util.spec_from_file_location('ses_adapter_under_test', MODULE)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def fixture(self, root):
        root.mkdir()
        (root / '__init__.py').write_text('__version__ = "1.2.0"\n__build_version = "1.2.0.25061615"\n')
        pin = root.parent / 'pin.json'
        pin.write_text(json.dumps({'version': '1.2.0', 'build': '1.2.0.25061615', 'dependencies': [], 'files': {'__init__.py': hashlib.sha256((root/'__init__.py').read_bytes()).hexdigest()}}))
        return pin

    def test_preflight_validates_source_without_import_or_process(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'storage_evaluation_system'
            pin = self.fixture(root)
            with patch.object(m, 'PIN_PATH', pin), patch.object(m, '_load_framework', side_effect=AssertionError('import forbidden')), patch.object(m.subprocess, 'Popen', side_effect=AssertionError('process forbidden')):
                result = m.preflight(root)
                self.assertEqual(result['version'], '1.2.0')
                self.assertEqual(result['missing_dependencies'], [])
                self.assertFalse(result['imports_executed'])
                (root/'__init__.py').write_text('__version__ = "1.3.0"\n')
                with self.assertRaisesRegex(ValueError, 'source|version'):
                    m.preflight(root)

    def test_source_tampering_and_missing_dependencies_fail_before_execution(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'storage_evaluation_system'
            pin = self.fixture(root)
            with patch.object(m, 'PIN_PATH', pin):
                (root/'__init__.py').write_text((root/'__init__.py').read_text() + '# tamper\n')
                with self.assertRaisesRegex(ValueError, 'hash|source'):
                    m.preflight(root)
                self.fixture_rehash(root, pin)
                data = json.loads(pin.read_text())
                data['dependencies'] = ['ses_dependency_that_does_not_exist']
                pin.write_text(json.dumps(data))
                result = m.preflight(root)
                self.assertEqual(result['missing_dependencies'], ['ses_dependency_that_does_not_exist'])

    def fixture_rehash(self, root, pin):
        data = json.loads(pin.read_text())
        data['files']['__init__.py'] = hashlib.sha256((root/'__init__.py').read_bytes()).hexdigest()
        pin.write_text(json.dumps(data))

    def test_unready_or_non_ai_metadata_rejected_before_framework_import(self):
        m = self.module()
        with patch.object(m, '_load_framework', side_effect=AssertionError('import forbidden')):
            for metadata in [{}, {'model_id': 'baleen_v2'}]:
                with self.assertRaises(ValueError):
                    m.run(config=Path('/missing'), output=Path('/missing'), vdbench=Path('/missing'), ses_root=Path('/missing'), metadata=metadata)

    def test_measurement_config_rejects_mutating_or_implicit_warmup(self):
        m = self.module()
        valid = 'fsd=b,anchor=/mnt/b,files=4,size=1g\nfwd=r,fsd=b,operation=read,fileio=random,fileselect=random,threads=1,xfersize=64k\nrd=measure,fwd=r,fwdrate=100,elapsed=600,interval=1,format=no\n'
        m._validate_measurement_config(valid)
        for invalid in [valid.replace('operation=read', 'operation=write'), valid.replace('format=no', 'format=yes'), valid.replace('elapsed=600', 'elapsed=600,warmup=60'), valid + 'startcmd=rm -rf /mnt/b\n', valid.replace('format=no', 'format=no,foroperation=write')]:
            with self.subTest(config=invalid):
                with self.assertRaises(ValueError):
                    m._validate_measurement_config(invalid)


    @unittest.skipUnless(os.environ.get('SES_SOURCE_ROOT'), 'opt-in isolated SES source lifecycle test')
    def test_real_framework_lifecycle_with_executor_stub(self):
        m = self.module()
        root = Path(os.environ['SES_SOURCE_ROOT'])
        # Import first: matplotlib may discover fonts via a local subprocess.
        # After imports every process and network connection is forbidden.
        m._load_framework(root)
        import storage_evaluation_system.suite as ses_suite
        import storage_evaluation_system.report as ses_report
        valid = 'data_errors=1\nmessagescan=no\ncreate_anchors=no\nfsd=default,depth=1,width=1,shared=yes,openflags=o_direct\nfsd=b,anchor=/no-storage-access,files=4,size=1g\nfwd=r,fsd=b,operation=read,fileio=random,fileselect=random,threads=1,xfersize=64k\nrd=measure,fwd=r,fwdrate=100,elapsed=600,interval=1,format=no\n'
        metadata = {'model_id': 'ai_inference_ses_v2', 'profile': 'baseline', 'manifest_sha256': 'a'*64, 'logical_bytes': 123480309760}
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config = base/'input.vdb'
            config.write_text(valid)
            executable = base/'fake-vdbench'
            executable.write_text('NEVER EXECUTE')
            executable.chmod(0o700)
            def executor(command, console):
                target = Path(command[4])
                target.mkdir()
                (target/'summary.html').write_text('<html>synthetic statistics for offline test</html>')
                return 0
            with patch.object(m, '_execute_vdbench', side_effect=executor), patch.object(m.subprocess, 'Popen', side_effect=AssertionError('process forbidden')), patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')), patch.object(ses_suite.Suite, 'validate', side_effect=AssertionError('upstream constructor mutation forbidden')), patch.object(ses_suite.Suite, 'load_client', side_effect=AssertionError('remote clients forbidden')), patch.object(ses_suite.Suite, 'monitor', side_effect=AssertionError('monitor forbidden')), patch.object(ses_report.Report, 'create_zip', side_effect=AssertionError('certification packaging forbidden')):
                result = m.run(config, base/'result', executable, root, metadata)
                self.assertEqual(result['status'], 'completed')
                report = Path(result['report']).read_text()
                self.assertIn('synthetic', (base/'result/vdbench-output/summary.html').read_text())
                self.assertIn('Vdbench actual statistics', report)
                self.assertIn('not SES certification', report)
                self.assertIn('case-result-pass', report)
                self.assertEqual(result['hardware'], {'status': 'not supplied'})
                self.assertEqual(json.loads((base/'result/ses-research-result.json').read_text())['status'], 'completed')
                with patch.object(m, '_execute_vdbench', return_value=7):
                    with self.assertRaises(RuntimeError):
                        m.run(config, base/'failed', executable, root, metadata)
                    failure = json.loads((base/'failed/ses-research-result.json').read_text())
                    self.assertEqual(failure['status'], 'failed')
                    self.assertEqual(failure['vdbench_exit_code'], 7)


if __name__ == '__main__':
    unittest.main()
