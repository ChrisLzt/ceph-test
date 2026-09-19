"""Frozen Region4 statistical read workload; no trace or network needed at build.

The packaged profile retains first-seen source key identities, per-key counts,
fixed membership, and complete bin/window aligned transfer histograms. Bin
selection approximates source operation probabilities; uniform file selection
within each bin introduces the documented error. Random offsets do not replay
source offsets, write dependencies, or production cache behavior.
"""
import hashlib
import json
import math
from pathlib import Path


_PROFILE = Path(__file__).with_name('data') / 'baleen_region4_640.json'
_PROFILE_SHA256 = 'df51d75efe3323789bcacbd7cbe6cfcf6f903891c0e2cee49e5a95706c86608e'


def build():
    """Return independent baseline and Zipf(0.99) phases on 640 shared bins.

    Transfer histogram weights are exact source operation counts. The common
    renderer normalizes and serializes them to percentages. Phase rates are
    normalized to an average multiplier of one over the 600-second workload.
    """
    raw = _PROFILE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != _PROFILE_SHA256:
        raise ValueError('Baleen packaged profile checksum mismatch')
    data = json.loads(raw)
    keys = data['keys']
    bins = [
        {
            'id': 'baleen_%03d' % i,
            'files': len(b['members']),
            'size_bytes': b['size_bytes'],
            'group': 'baleen',
            'active_mask': b['active_mask'],
            'source_key_indices': b['members'],
        }
        for i, b in enumerate(data['bins'])
    ]
    phase_counts = data['provenance']['source_phase_operations']
    profiles = {'baseline': [], 'zipf099': []}
    mean_count = sum(phase_counts) / 4
    averages = {'baseline': [], 'zipf099': []}
    for w in range(4):
        active = sorted(
            (i for i, k in enumerate(keys) if k[3][w]),
            key=lambda i: (-keys[i][3][w], i),
        )
        zipf_weights = [0.0] * len(keys)
        normalizer = math.fsum(rank ** -.99 for rank in range(1, len(active) + 1))
        for rank, i in enumerate(active, 1):
            zipf_weights[i] = rank ** -.99 / normalizer
        for profile in profiles:
            lanes = []
            for b, mapped in zip(data['bins'], bins):
                if not b['active_mask'] & (1 << w):
                    continue
                weight = (
                    sum(keys[i][3][w] for i in b['members'])
                    if profile == 'baseline'
                    else math.fsum(zipf_weights[i] for i in b['members'])
                )
                lanes.append({
                    'bin': mapped['id'],
                    'weight': weight,
                    'xfersize': [pair[:] for pair in b['histograms'][w]],
                    'fileio': 'random',
                    'fileselect': 'random',
                    'threads': 1,
                    'stopafter': 1,
                })
            profiles[profile].append({
                'name': 'phase_%d' % (w + 1),
                'seconds': 150,
                'rate_multiplier': phase_counts[w] / mean_count,
                'lanes': lanes,
            })
            total_weight = math.fsum(lane['weight'] for lane in lanes)
            averages[profile].append(math.fsum(
                lane['weight'] * sum(size * count for size, count in lane['xfersize'])
                / sum(count for _, count in lane['xfersize'])
                for lane in lanes
            ) / total_weight)
    provenance = data['provenance']
    provenance['profile_sha256'] = _PROFILE_SHA256
    provenance['profile_file'] = 'data/baleen_region4_640.json'
    return {
        'id': 'bigdata_baleen_v2',
        'bins': bins,
        'profiles': profiles,
        'provenance': provenance,
        'source_key_columns': data['key_columns'],
        'source_keys': keys,
        'expected_phase_bytes_per_operation': averages,
        'prepare_batch_size': 20,
        'limitations': [
            'Source GET and PUT are statistical read operations, not causal replay.',
            'Uniform file selection within fixed bins approximates per-key probabilities.',
            'Random aligned offsets can read file padding and do not retain source offsets.',
            'Zipf retains conditional bin/window transfer histograms; its global size mix changes.',
            'Candidate errors are analytical expectations, not finite-run or Ceph object measurements.',
            'One thread per bin is conservative; no single-file shared concurrency is requested.',
        ],
    }
