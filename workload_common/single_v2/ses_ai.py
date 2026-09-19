"""Pure SES 1.2.0 template read adaptations; no framework or storage imports.

Ranks are fixed within a size class, mapped in order to each bin's Vdbench
file identities. Zipf is a conditional, uniform-within-bin approximation.
"""
import json
import math
from pathlib import Path


def _build(kind):
    evidence = json.loads((Path(__file__).with_name('data') / 'ses_ai_evidence.json').read_text())
    spec = evidence[kind]
    bins = []
    profiles = {name: [{'name': 'measure', 'seconds': 600, 'rate_multiplier': 1, 'lanes': []}]
                for name in ('baseline', 'zipf099')}
    for size in spec['sizes']:
        size_bytes = size['size_bytes']
        group = 'size_' + str(size_bytes)
        if kind == 'inference':
            channels = [(131072, 'sequential', .3), (65536, 'sequential', .3),
                        (131072, 'random', .2), (65536, 'random', .2)]
        elif size_bytes < 1048576:
            channels = [(8192, 'sequential', 1/3), (32768, 'sequential', 1/3),
                        (65536, 'sequential', 1/3)]
        else:
            channels = [(1048576, 'sequential', 1)]
        probabilities = [rank ** -.99 for rank in range(1, size['file_count'] + 1)]
        normalizer = math.fsum(probabilities)
        start = 0
        for index, files in enumerate(size['bin_file_counts']):
            bin_id = group + '_b' + str(index).zfill(3)
            bins.append({'id': bin_id, 'files': files, 'size_bytes': size_bytes,
                         'group': group, 'rank_start': start + 1, 'rank_end': start + files})
            conditional = {'baseline': files / size['file_count'],
                           'zipf099': math.fsum(probabilities[start:start + files]) / normalizer}
            for name, phases in profiles.items():
                for xfer, access, fraction in channels:
                    phases[0]['lanes'].append({
                        'bin': bin_id, 'weight': size['operation_share'] * conditional[name] * fraction,
                        'xfersize': xfer, 'fileio': access, 'fileselect': access, 'threads': 1,
                    })
            start += files
    return {
        'id': 'ai_' + kind + '_ses_v2', 'bins': bins, 'profiles': profiles,
        'provenance': {**evidence['provenance'], 'source_case': 'PERF_002' if kind == 'training' else 'PERF_003',
                       'source_write_to_read': True, 'source_read_write_ratio': '70:30' if kind == 'training' else '80:20',
                       'adaptation': 'SES 1.2.0 template read adaptation research case; not standard SES certification'},
        'zipf': {'alpha': .99, 'scope': evidence['method']['scope'],
                 'tv_percent': spec['global_conditional_zipf_tv_percent'],
                 'status': 'offline ideal approximation; runtime error acceptance threshold not established'},
        'measurement': {'warmup_seconds': 0, 'discard_initial_seconds': 0, 'seconds': 600},
        'identity_policy': 'Fixed class-conditional rank mapped in bin/file enumeration order; no reshuffle',
    }


def build_training():
    """Return the approved 10,000-file, 388-FWD training layout and profiles."""
    return _build('training')


def build_inference():
    """Return the approved 100-file, 96-FWD inference layout and profiles."""
    return _build('inference')
