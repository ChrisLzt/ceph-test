"""Isolated SES 1.2.0 research overlay, called only after CLI readiness checks.

The source tree is external and immutable. Pure render never imports SES.
Suite construction bypasses the upstream monitor-file mutation; our registered
BaseCase uses the genuine CaseRunner and Report lifecycle without PERFBase,
remote clients, format/prepare, cache clearing, mounting, or implicit warmup.
"""
import ast
import datetime
import hashlib
import html
import importlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

PIN_PATH = Path(__file__).with_name('data') / 'ses_source_pin.json'
OVERLAY_VERSION = 'single-v2-ses-1'


def preflight(ses_root, check_imports=True):
    """Hash/AST checks and dependency discovery only; never import or start SES."""
    root = Path(ses_root).resolve()
    if not (root / '__init__.py').is_file() and (root / 'storage_evaluation_system').is_dir():
        root = root / 'storage_evaluation_system'
    pins = json.loads(PIN_PATH.read_text())
    for relative, expected in pins['files'].items():
        path = root / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('SES source hash mismatch or missing file: ' + str(path))
    values = {}
    for node in ast.parse((root/'__init__.py').read_text()).body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    values[target.id] = node.value.value
    if values.get('__version__') != pins['version'] or values.get('__build_version') != pins['build']:
        raise ValueError('SES source version/build must match pinned 1.2.0')
    dependencies = {name: importlib.util.find_spec(name) is not None for name in pins['dependencies']} if check_imports else {}
    source_hash = hashlib.sha256(json.dumps(pins['files'], sort_keys=True).encode()).hexdigest()
    return {'version': pins['version'], 'build': pins['build'], 'source_root': str(root),
            'source_sha256': source_hash, 'pinned_files': len(pins['files']),
            'dependencies': dependencies, 'missing_dependencies': [k for k, present in dependencies.items() if not present],
            'imports_executed': False, 'python': sys.executable}


def _load_framework(root):
    """Load only the verified external package, rejecting mixed SES installations."""
    root = Path(root).resolve()
    for name, module in list(sys.modules.items()):
        if name == 'storage_evaluation_system' or name.startswith('storage_evaluation_system.'):
            path = getattr(module, '__file__', None)
            if path and not Path(path).resolve().is_relative_to(root):
                raise ValueError('A different SES installation is already imported: ' + path)
    sys.path.insert(0, str(root.parent))
    try:
        return tuple(importlib.import_module('storage_evaluation_system.' + name)
                     for name in ('suite', 'basecase', 'report', 'constants'))
    finally:
        sys.path.pop(0)


def _validate_measurement_config(text):
    """Defense in depth for the renderer's restricted measurement grammar."""
    allowed = {'fsd': {'fsd', 'anchor', 'depth', 'width', 'files', 'size', 'sizes', 'shared', 'openflags'},
               'fwd': {'fwd', 'fsd', 'operation', 'fileio', 'fileselect', 'xfersize', 'threads', 'skew', 'stopafter'},
               'rd': {'rd', 'fwd', 'fwdrate', 'elapsed', 'interval', 'format'}}
    fwd_count = rd_count = 0
    durations = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(('*', '#')):
            continue
        if line in {'data_errors=1', 'messagescan=no', 'create_anchors=no'}:
            continue
        first = line.split('=', 1)[0]
        if first not in allowed:
            raise ValueError('Unsupported SES measurement directive: ' + first)
        # Transfer distributions can contain comma-separated values; extract only keys.
        pairs = re.findall(r'(?:^|,)\s*([a-zA-Z0-9_]+)\s*=\s*([^,]+)', line)
        fields = dict(pairs)
        if len(pairs) != len(fields) or set(fields) - allowed[first]:
            raise ValueError('Unsupported or repeated SES measurement parameter')
        if first == 'fwd':
            fwd_count += 1
            if fields.get('operation') != 'read' or fields.get('threads') != '1':
                raise ValueError('SES measurement requires read-only single-thread FWDs')
        if first == 'rd':
            rd_count += 1
            if fields.get('format') != 'no':
                raise ValueError('SES measurement requires format=no')
            durations.append(fields.get('elapsed'))
    if not 1 <= fwd_count <= 512 or durations not in (['600'], ['360','240'], ['200','40','60','200','40','60'], ['60','240','300']):
        raise ValueError('SES requires an approved 600-second phase schedule and 1..512 explicit FWDs')


def _execute_vdbench(command, console_path):
    """Own exactly this process group; no global process-name cleanup."""
    with Path(console_path).open('w') as console:
        process = subprocess.Popen(command, stdout=console, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            return process.wait(timeout=900)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            raise


def run(config, output, vdbench, ses_root, metadata):
    """Execute a ready AI case with SES case lifecycle and a research HTML report.

    Caller MUST first verify the full preparation manifest and mounted dataset.
    This function does not prepare or repair data. Hardware metadata supplied by
    the caller is reported verbatim; unavailable hardware fields remain unknown.
    """
    model_id = metadata.get('model_id', metadata.get('id'))
    if model_id not in ('ai_training_ses_v2', 'ai_inference_ses_v2'):
        raise ValueError('SES adapter requires an approved SINGLE AI model')
    if metadata.get('profile') not in ('baseline', 'zipf099', 'file_zipf099', 'phase_zipf099'):
        raise ValueError('SES adapter requires an approved baseline or Zipf profile')
    if not re.fullmatch(r'[a-f0-9]{64}', metadata.get('manifest_sha256', '')):
        raise ValueError('SES adapter requires the verified manifest SHA-256')
    capacity = metadata.get('logical_bytes', metadata.get('capacity_bytes'))
    expected = 123363000320 if model_id == 'ai_training_ses_v2' else 123480309760
    if capacity != expected:
        raise ValueError('SES research capacity does not match the approved model')
    config, output, vdbench = (Path(p).resolve() for p in (config, output, vdbench))
    config_text = config.read_text()
    _validate_measurement_config(config_text)
    if not vdbench.is_file() or not os.access(vdbench, os.X_OK):
        raise ValueError('Vdbench executable is missing or not executable')
    if output.exists() and any(output.iterdir()):
        raise ValueError('SES output directory must be new or empty')
    source = preflight(ses_root)
    if source['missing_dependencies']:
        raise ValueError('Missing isolated SES dependencies: ' + ', '.join(source['missing_dependencies']))
    suite_module, basecase_module, report_module, constants = _load_framework(source['source_root'])
    source['imports_executed'] = True
    output.mkdir(parents=True, exist_ok=True)
    run_config = output / 'measurement.vdb'
    run_config.write_text(config_text)
    vdb_output = output / 'vdbench-output'
    audit = {**metadata, 'framework': source, 'overlay_version': OVERLAY_VERSION,
             'config_sha256': hashlib.sha256(config_text.encode()).hexdigest(),
             'research_only': True, 'certification': False, 'warmup_seconds': 0,
             'discard_initial_seconds': 0, 'capacity_policy': 'Approved fixed research layout; SES standard minimum capacity rule not applied',
             'hardware': metadata.get('hardware', {'status': 'not supplied'}),
             'local_host': {'hostname': platform.node(), 'platform': ' '.join(os.uname()),
                            'memory_bytes': os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')},
             'command': [str(vdbench), '-f', str(run_config), '-o', str(vdb_output)],
             'status': 'starting'}
    audit_path = output / 'ses-research-result.json'

    def save_audit():
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')

    class ResearchReport(report_module.Report):
        @property
        def html_object(self):
            # Upstream property leaves its input file open.
            return report_module.ReportUtil.str2element(Path(self.path).read_text(encoding='utf-8'))

        def build_summary(self, title):
            # Preserve IDs consumed by upstream Report's TOC and finish hooks.
            return ('<div id="report-summary"><h1>' + html.escape(title) + '</h1>'
                    '<p>Research template adaptation; not SES certification.</p>'
                    '<p id="test-end-time">-</p><p id="test-elapsed">-</p>'
                    '<table id="summary-table"></table><pre>' + html.escape(json.dumps(audit, ensure_ascii=False, indent=2)) + '</pre></div>')

        def create_zip(self):
            # Upstream packaging copies/encrypts with a remote master host and
            # implies standard certification. Research HTML + JSON are complete.
            return None

    class ResearchSuite(suite_module.Suite):
        def validate(self):
            # Suite.__init__ otherwise removes/creates ~/ses.mon.
            return None

    class ResearchCase(basecase_module.BaseCase):
        def pre_condition(self):
            if hashlib.sha256(config.read_bytes()).hexdigest() != audit['config_sha256']:
                raise ValueError('Measurement config changed after validation')

        def procedure(self):
            audit['status'] = 'running'
            save_audit()
            code = _execute_vdbench(audit['command'], output / 'vdbench-console.log')
            audit['vdbench_exit_code'] = code
            if code != 0:
                raise RuntimeError('Vdbench exited with status ' + str(code))
            summary = vdb_output / 'summary.html'
            if not summary.is_file():
                raise RuntimeError('Vdbench produced no summary.html statistics')
            audit['actual_statistics'] = {'summary': 'vdbench-output/summary.html',
                                          'files': sorted(p.name for p in vdb_output.iterdir() if p.is_file()),
                                          'summary_sha256': hashlib.sha256(summary.read_bytes()).hexdigest(),
                                          'discard_initial_seconds': 0}

        def make_report(self):
            audit['status'] = 'completed' if self.result == constants.CaseResult.PASS else 'failed'
            content = '<p><a href="vdbench-output/summary.html">Vdbench actual statistics (all measured intervals)</a></p>'
            content += '<pre>' + html.escape(json.dumps(audit, ensure_ascii=False, indent=2)) + '</pre>'
            return report_module.ReportUtil.str2element(content)

    custom_config = ET.ElementTree(ET.Element('config'))
    suite = ResearchSuite(custom_config, 'SINGLE_SES_RESEARCH', str(output))
    case = ResearchCase(suite, ET.Element('case', id=model_id, name=model_id, category='performance'), {}, {}, True)
    suite.cases = [case]
    suite.cases_by_major_id = {model_id: [case]}
    suite.report = ResearchReport(suite)
    runner = suite_module.CaseRunner(suite, case)
    suite._running_case_runner = runner
    audit['started_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save_audit()
    try:
        # Synchronous invocation preserves exception/interrupt ownership in the
        # caller; this is the upstream CaseRunner lifecycle, without Suite.run's
        # remote tool checks and background monitor.
        runner.run()
        suite.report.finish()
        if case.result != constants.CaseResult.PASS or 'actual_statistics' not in audit:
            raise RuntimeError('SES research case failed; inspect report and console')
        suite.status = constants.SuiteStatus.COMPLETED
        audit['status'] = 'completed'
        audit['report'] = str(suite.report.path)
    except BaseException as error:
        audit['status'] = 'failed'
        audit['error'] = str(error)
        raise
    finally:
        audit['finished_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save_audit()
    return audit
