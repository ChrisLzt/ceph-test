"""Explicit preparation and readiness gates; never mount, clean, or repair data."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from datetime import datetime, timezone

from .core import digest, json_text, safe_path, validate_bundle

READY = '.single-v2-ready.json'
INTENT = '.single-v2-preparing.json'


def no_symlinks(path):
    path = safe_path(path)
    for item in reversed((path, *path.parents)):
        if item.is_symlink():
            raise ValueError(f'symlink is not allowed in data path: {item}')
    return path


def _existing_parent(path):
    while not path.exists():
        if path == path.parent:
            raise ValueError('no existing ancestor')
        path = path.parent
    return path


def mount_info(path):
    """Read mount identity only; intentionally omit mount options/credentials."""
    path = Path(path).absolute()
    matches = []
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        left, right = line.split(' - ', 1)
        fields, tail = left.split(), right.split()
        target = Path(re.sub(r'\\([0-7]{3})', lambda m:chr(int(m[1],8)), fields[4]))
        if path == target or target in path.parents:
            matches.append((len(target.parts), {'target':str(target), 'fstype':tail[0], 'source':tail[1]}))
    if not matches:
        raise ValueError(f'cannot determine mount: {path}')
    return max(matches, key=lambda pair:pair[0])[1]


def _ceph_target(root):
    root = no_symlinks(root)
    info = mount_info(root)
    if info['fstype'] not in ('ceph', 'fuse.ceph', 'fuse.ceph-fuse'):
        raise ValueError(f"target is not a CephFS mount: {info['target']} ({info['fstype']})")
    if root == Path(info['target']):
        raise ValueError('data root must be a dedicated directory below the mount')
    return root, info


def preflight(bundle):
    manifest = validate_bundle(bundle)
    root, mount = _ceph_target(manifest['data_root'])
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise ValueError(f'data root already contains content; no automatic overwrite or cleanup: {root}')
    parent = _existing_parent(root)
    fs = os.statvfs(parent)
    available = fs.f_bavail * fs.f_frsize
    required = (manifest['capacity_bytes'] * 105 + 99) // 100
    if available < required:
        raise ValueError(f'insufficient free space: {available} bytes available, {required} required including 5% headroom')
    if not os.access(parent, os.W_OK):
        raise ValueError(f'target parent is not writable: {parent}')
    return {'id':manifest['id'], 'data_root':str(root), 'mount':mount,
            'capacity_bytes':manifest['capacity_bytes'], 'required_free_bytes':required,
            'available_bytes':available, 'existing_empty_directory':root.exists()}


def verify_inventory(manifest):
    """Stat only: prove expected file counts, sizes and allocated extents, not payload checksums."""
    root = no_symlinks(manifest['data_root'])
    expected = {b['id'] for b in manifest['bins']}
    if not root.is_dir():
        raise ValueError(f'missing data root: {root}')
    for child in root.iterdir():
        if child.name not in expected | {READY, INTENT}:
            raise ValueError(f'unexpected content in data root: {child}')
        if child.is_symlink():
            raise ValueError(f'symlink in data root: {child}')
    total_files = total_bytes = 0
    for b in manifest['bins']:
        anchor = no_symlinks(b['anchor'])
        if not anchor.is_dir():
            raise ValueError(f'missing bin anchor: {anchor}')
        count = 0
        expected_files = {f'vdb.1_1.dir/vdb_f{i:04d}.file' for i in range(b['files'])}
        actual_files = set()
        for directory, dirs, files in os.walk(anchor, followlinks=False):
            for name in dirs:
                p = Path(directory)/name
                if p.is_symlink() or p.relative_to(anchor).as_posix() != 'vdb.1_1.dir':
                    raise ValueError(f'unexpected or symlink directory: {p}')
            for name in files:
                p = Path(directory)/name
                st = p.lstat()
                if not stat.S_ISREG(st.st_mode):
                    raise ValueError(f'not a regular file: {p}')
                relative = p.relative_to(anchor).as_posix()
                if relative == 'vdb_control.file':
                    continue
                if relative not in expected_files:
                    raise ValueError(f'unexpected file in bin: {p}')
                if st.st_size != b['size_bytes']:
                    raise ValueError(f'wrong file size: {p}')
                if st.st_blocks * 512 < st.st_size:
                    raise ValueError(f'sparse or incompletely allocated data file: {p}')
                actual_files.add(relative)
                count += 1
                total_bytes += st.st_size
        if actual_files != expected_files:
            raise ValueError(f"bin {b['id']} file identity inventory differs from Vdbench layout")
        if count != b['files']:
            raise ValueError(f"bin {b['id']} has {count} data files; expected {b['files']}")
        total_files += count
    if total_bytes != manifest['capacity_bytes'] or total_files != manifest['file_count']:
        raise ValueError('total file inventory mismatch')
    return {'file_count':total_files, 'capacity_bytes':total_bytes, 'verification':'stat counts/sizes/allocated extents; no content read'}


def _record(manifest, **extra):
    return {'id':manifest['id'], 'layout_sha256':manifest['layout_sha256'],
            'capacity_bytes':manifest['capacity_bytes'], 'utc':datetime.now(timezone.utc).isoformat(), **extra}


def _executable(vdbench):
    vdbench = Path(vdbench).absolute()
    if not vdbench.is_file() or not os.access(vdbench, os.X_OK):
        raise ValueError(f'Vdbench executable unavailable: {vdbench}')
    return vdbench


def validate_outputs(manifests, bundles, results):
    """Check every selected destination before any workload creates data/results."""
    results = safe_path(results)
    excluded = [safe_path(m['data_root']) for m in manifests] + [safe_path(b) for b in bundles]
    for manifest in manifests:
        output = safe_path(results/manifest['id'])
        if output.exists():
            raise ValueError(f'refuse existing output directory: {output}')
        for path in excluded:
            if output == path or path in output.parents or output in path.parents:
                raise ValueError(f'output overlaps selected data or configuration: {output}')
    return None


def _output(output, root, bundle):
    output = safe_path(output)
    if output.exists():
        raise ValueError(f'refuse existing output directory: {output}')
    for excluded in (root, Path(bundle).absolute()):
        if output == excluded or excluded in output.parents or output in excluded.parents:
            raise ValueError('results, data and configuration paths must be separate')
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def prepare(bundle, *, vdbench, output, execute=False):
    if not execute:
        raise ValueError('preparation writes data; explicit --execute is required')
    bundle = Path(bundle).absolute()
    manifest = validate_bundle(bundle)
    report = preflight(bundle)
    root = Path(manifest['data_root'])
    vdbench = _executable(vdbench)
    output = _output(output, root, bundle)
    root.mkdir(parents=True, exist_ok=True)
    # Exclusive intent file prevents duplicate preparations; leftovers require inspection.
    with (root/INTENT).open('x') as stream:
        stream.write(json_text(_record(manifest, state='preparing', output=str(output))))
    subprocess.run([str(vdbench), '-f', str(bundle/'prepare_data.vdb'), '-o', str(output)], check=True)
    inventory = verify_inventory(manifest)
    (root/READY).write_text(json_text(_record(manifest, state='ready', inventory=inventory)))
    return {**report, **inventory, 'state':'ready', 'output':str(output)}


def check_ready(bundle):
    manifest = validate_bundle(bundle)
    root, mount = _ceph_target(manifest['data_root'])
    marker = root/READY
    if not marker.is_file() or marker.is_symlink():
        raise ValueError('ready marker absent; preparation must finish successfully before measurement')
    ready = json.loads(marker.read_text())
    if ready.get('state') != 'ready' or ready.get('layout_sha256') != manifest['layout_sha256'] or ready.get('capacity_bytes') != manifest['capacity_bytes']:
        raise ValueError('prepared data belongs to a different layout')
    return {**verify_inventory(manifest), 'id':manifest['id'], 'mount':mount, 'state':'ready'}


def run(bundle, *, profile='baseline', vdbench, output, execute=False, ses_root=None):
    if not execute:
        raise ValueError('measurement requires explicit --execute')
    bundle = Path(bundle).absolute()
    manifest = validate_bundle(bundle)
    if profile not in manifest['profiles']:
        raise ValueError(f'unknown profile: {profile}')
    check_ready(bundle)
    vdbench = _executable(vdbench)
    root = Path(manifest['data_root'])
    output = _output(output, root, bundle)
    config = bundle/f'run_{profile}.vdb'
    if manifest['id'] in ('ai_training_ses_v2','ai_inference_ses_v2'):
        if ses_root is None:
            raise ValueError('AI measurement requires the pinned SES 1.2.0 source root')
        from . import ses_adapter
        return ses_adapter.run(config=config, output=output, vdbench=vdbench, ses_root=Path(ses_root),
            metadata={**manifest, 'model_id':manifest['id'], 'profile':profile,
                      'logical_bytes':manifest['capacity_bytes'],
                      'manifest_sha256':digest((bundle/'manifest.json').read_text())})
    subprocess.run([str(vdbench), '-f', str(config), '-o', str(output)], check=True)
    return {'id':manifest['id'], 'profile':profile, 'output':str(output)}
