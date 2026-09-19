"""Pure validation and deterministic Vdbench emission for SINGLE v2."""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import math
from pathlib import Path
import re

MAX_FWD = 512
BATCH_SIZE = 20
NAME = re.compile(r"[a-z][a-z0-9_]*\Z")


def json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def safe_path(path):
    path = Path(path).absolute()
    if not re.fullmatch(r"/[A-Za-z0-9_./-]+", str(path)) or ".." in path.parts:
        raise ValueError(f"Vdbench path must be absolute and contain no parameter metacharacters: {path}")
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError(f'symlink is not allowed in configuration/data path: {item}')
    return path


def _positive(value, label, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be positive and finite")
    if integer and not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")


def _name(value):
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise ValueError(f"invalid identifier: {value!r}")


def validate_model(model):
    _name(model['id'])
    bins = model['bins']
    if not bins or len({b['id'] for b in bins}) != len(bins):
        raise ValueError('bins must be nonempty and unique')
    lookup = {b['id']: b for b in bins}
    for b in bins:
        _name(b['id'])
        _positive(b['files'], 'file count', True)
        _positive(b['size_bytes'], 'file size', True)
        if b['size_bytes'] % 4096:
            raise ValueError('file size must be 4 KiB aligned')
    if 'baseline' not in model['profiles']:
        raise ValueError('baseline profile required')
    used = set()
    for profile, phases in model['profiles'].items():
        _name(profile)
        if not phases or len({p['name'] for p in phases}) != len(phases):
            raise ValueError('profile phases must be nonempty and unique')
        for phase in phases:
            _name(phase['name'])
            _positive(phase['seconds'], 'elapsed', True)
            _positive(phase.get('rate_multiplier', 1), 'rate multiplier')
            lanes = phase['lanes']
            if ('phase_zipf' in model or 'static_native' in model) and len(lanes)>256:
                raise ValueError('business phase exceeds 256 active FWDs')
            if not 0 < len(lanes) <= MAX_FWD:
                raise ValueError('each RD must expand to 1..512 FWDs')
            concurrency = Counter()
            for lane in lanes:
                b = lookup.get(lane['bin'])
                if b is None:
                    raise ValueError('lane references unknown bin')
                used.add(b['id'])
                if lane.get('threads', 1) != 1:
                    raise ValueError('v2 fixed bin plan requires one thread per FWD')
                concurrency[b['id']] += 1
                _positive(lane['weight'], 'lane probability')
                if lane.get('operation', 'read') != 'read':
                    raise ValueError('measurement must map all source operations to read')
                if lane['fileio'] not in ('random', 'sequential') or lane['fileselect'] not in ('random', 'sequential'):
                    raise ValueError('unsupported access selection')
                xfer = lane['xfersize']
                pairs = xfer if isinstance(xfer, list) else [[xfer, 1]]
                if not pairs:
                    raise ValueError('empty transfer histogram')
                for size, weight in pairs:
                    _positive(size, 'transfer bytes', True)
                    _positive(weight, 'transfer probability')
                    if size % 4096 or size > b['size_bytes']:
                        raise ValueError('transfer must be aligned and fit every file in its bin')
                if 'stopafter' in lane:
                    _positive(lane['stopafter'], 'stopafter', True)
            for key, count in concurrency.items():
                if count > lookup[key]['files']:
                    raise ValueError(f'bin {key} has fewer files than concurrent FWDs')
        if sum(p['seconds'] for p in phases) != 600:
            raise ValueError('each profile must total 600 seconds')
    if used != set(lookup):
        raise ValueError('unreferenced prepared bins')
    return sum(b['files'] * b['size_bytes'] for b in bins)


def percentages(weights):
    values = [Decimal(str(v)) for v in weights]
    total = sum(values)
    # Dyadic percentages sum exactly in both Java doubles and Decimal(prec=28).
    # Vdbench casts the floating sum to int: 99.99999999999999 is rejected.
    scale = 2 ** 24
    units = [int((v / total * 100 * scale).to_integral_value(rounding=ROUND_HALF_UP)) for v in values]
    i = max(range(len(units)), key=units.__getitem__)
    units[i] += 100 * scale - sum(units)
    if any(v <= 0 for v in units):
        raise ValueError('probability quantization erased a nonzero tail')
    return [format(Decimal(v) / scale, 'f') for v in units]


def transfer_percentages(weights):
    """Round transfer percentages for the stock 5.04.07 integer sampler.

    Correct rounding residuals by largest under/over-allocation; ties retain
    input order. Zero categories are omitted by the renderer, not forced to 1%.
    FWD skew deliberately continues to use the separate fractional encoder.
    """
    values = [Decimal(str(v)) for v in weights]
    if not values or any(not v.is_finite() or v <= 0 for v in values):
        raise ValueError('transfer weights must be finite and positive')
    total = sum(values)
    quotas = [v / total * 100 for v in values]
    units = [int(q.to_integral_value(rounding=ROUND_HALF_UP)) for q in quotas]
    while sum(units) != 100:
        if sum(units) < 100:
            i = max(range(len(units)), key=lambda i: quotas[i] - units[i])
            units[i] += 1
        else:
            i = max((i for i in range(len(units)) if units[i]),
                    key=lambda i: units[i] - quotas[i])
            units[i] -= 1
    return units


def _header(model, data_root, prepare):
    lines = [f"* SINGLE v2 {model['id']}; synthetic source-write-to-read research workload",
             'data_errors=1', 'messagescan=no', f"create_anchors={'yes' if prepare else 'no'}",
             'fsd=default,depth=1,width=1,shared=yes,openflags=o_direct']
    for b in model['bins']:
        lines.append(f"fsd={b['id']},anchor={data_root / b['id']},files={b['files']},size={b['size_bytes']}")
    return lines


def config_texts(model, data_root, rate):
    validate_model(model)
    if rate != 'max':
        _positive(rate, 'target mean IOPS')
    texts = {}
    lines = _header(model, data_root, True)
    lines.append('fwd=format,threads=1,xfersize=4m')
    for b in model['bins']:
        lines.append(f"fwd=prep_{b['id']},fsd={b['id']},operation=read,threads=1")
    for start in range(0, len(model['bins']), BATCH_SIZE):
        names = ','.join('prep_' + b['id'] for b in model['bins'][start:start+BATCH_SIZE])
        lines.append(f'rd=prepare_{start//BATCH_SIZE:03d},fwd=({names}),format=(restart,only),fwdrate=max')
    texts['prepare_data.vdb'] = '\n'.join(lines) + '\n'
    profiles = {}
    for profile, phases in model['profiles'].items():
        lines = _header(model, data_root, False)
        rds = []
        profiles[profile] = []
        for index, phase in enumerate(phases):
            prefix = f'p{index:03d}_'
            skews = percentages([l['weight'] for l in phase['lanes']])
            for lane_index, (lane, skew) in enumerate(zip(phase['lanes'], skews)):
                xfer = lane['xfersize']
                if isinstance(xfer, list):
                    pcts = transfer_percentages([pair[1] for pair in xfer])
                    xfer = '(' + ','.join(f'{pair[0]},{pct}' for pair, pct in zip(xfer, pcts) if pct > 0) + ')'
                suffix = f",stopafter={lane['stopafter']}" if 'stopafter' in lane else ''
                lines.append(f"fwd={prefix}{lane_index:04d},fsd={lane['bin']},operation=read,threads=1,xfersize={xfer},fileio={lane['fileio']},fileselect={lane['fileselect']},skew={skew}{suffix}")
            phase_rate = 'max' if rate == 'max' else format(rate * phase.get('rate_multiplier', 1), '.12g')
            rds.append(f"rd={prefix}{phase['name']},fwd={prefix}*,fwdrate={phase_rate},format=no,elapsed={phase['seconds']},interval=1")
            profiles[profile].append({'name':phase['name'], 'seconds':phase['seconds'], 'fwd_count':len(phase['lanes']), 'target_iops':phase_rate})
        texts[f'run_{profile}.vdb'] = '\n'.join(lines + rds) + '\n'
    return texts, profiles


def render(model, *, data_root, output, rate=100):
    data_root, output = safe_path(data_root), safe_path(output)
    if output == data_root or data_root in output.parents or output in data_root.parents:
        raise ValueError('configuration and data directories must be separate')
    capacity = validate_model(model)
    texts, profiles = config_texts(model, data_root, rate)
    layout = [{'id':b['id'], 'files':b['files'], 'size_bytes':b['size_bytes'], 'anchor':str(data_root/b['id'])} for b in model['bins']]
    manifest = {'schema':1, 'id':model['id'], 'data_root':str(data_root), 'capacity_bytes':capacity,
                'file_count':sum(b['files'] for b in layout), 'bins':layout, 'profiles':profiles,
                'max_run_fwd':max(p['fwd_count'] for phases in profiles.values() for p in phases),
                'max_prepare_fwd':min(BATCH_SIZE, len(layout)), 'rate':rate,
                'layout_sha256':digest(json_text(layout)), 'model_sha256':digest(json_text(model)),
                'provenance':model.get('provenance', {}),
                'config_sha256':{name:digest(text) for name,text in texts.items()}}
    output.mkdir(parents=True, exist_ok=True)
    for name, text in {**texts, 'model.json':json_text(model), 'manifest.json':json_text(manifest)}.items():
        destination = safe_path(output/name)
        destination.write_text(text)
    validate_bundle(output)
    return manifest


def validate_bundle(output):
    """Verify all emitted bytes against the pure model, not only stored checksums."""
    output = Path(output)
    manifest = json.loads((output/'manifest.json').read_text())
    model = json.loads((output/'model.json').read_text())
    if digest(json_text(model)) != manifest['model_sha256']:
        raise ValueError('model checksum differs from manifest')
    if validate_model(model) != manifest['capacity_bytes']:
        raise ValueError('capacity mismatch')
    data_root = safe_path(manifest['data_root'])
    layout = [{'id':b['id'], 'files':b['files'], 'size_bytes':b['size_bytes'], 'anchor':str(data_root/b['id'])} for b in model['bins']]
    if layout != manifest['bins'] or digest(json_text(layout)) != manifest['layout_sha256']:
        raise ValueError('layout mismatch')
    texts, profiles = config_texts(model, data_root, manifest['rate'])
    if profiles != manifest['profiles'] or set(texts) != set(manifest['config_sha256']):
        raise ValueError('profile/config inventory mismatch')
    from workload_common.validate_vdbench import validate_prepare_text, validate_run_text
    for name, expected in texts.items():
        actual = (output/name).read_text()
        if actual != expected or digest(actual) != manifest['config_sha256'][name]:
            raise ValueError(f'generated configuration was changed: {name}')
        (validate_prepare_text if name.startswith('prepare') else validate_run_text)(actual)
    return manifest
