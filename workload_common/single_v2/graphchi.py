"""GraphChi PSW access-set model, using one shared copy of each edge cell.

This is a timed synthetic storage workload, not a GraphChi execution. Loading
and converted full-update writes share lanes; their call order is not modeled.
"""
import json
import math
from pathlib import Path

FILE_BYTES = 64 * 1024 ** 2
TRANSFER_BYTES = 4 * 1024 ** 2
TOTAL_FILES = 2048


def build():
    """Return baseline and conditional Zipf profiles on an identical layout."""
    topology = json.loads((Path(__file__).parent / 'data' / 'graphchi_topology.json').read_text())
    edges = [n for row in topology['edge_matrix_src_rows_dst_columns'] for n in row]
    total = topology['edges']
    counts = [TOTAL_FILES * n // total for n in edges]
    order = sorted(range(16), key=lambda i: (-(TOTAL_FILES * edges[i] % total), i))
    for i in order[:TOTAL_FILES - sum(counts)]:
        counts[i] += 1
    bins = []
    for i, count in enumerate(counts):
        source, destination = divmod(i, 4)
        group = f'dst_{destination:02d}_src_{source:02d}'
        tail, extra = divmod(count - 12, 12)
        lengths = [1] * 12 + [tail + (j < extra) for j in range(12)]
        norm = math.fsum(rank ** -0.99 for rank in range(1, count + 1))
        first = 1
        for number, length in enumerate(lengths):
            last = first + length - 1
            mass = math.fsum(rank ** -0.99 for rank in range(first, last + 1)) / norm
            bins.append({'id': f'{group}_bin_{number:02d}', 'group': group,
                         'files': length, 'size_bytes': FILE_BYTES,
                         'source_interval': source, 'destination_interval': destination,
                         'rank_start': first, 'rank_end': last,
                         'cell_files': count, 'conditional_zipf_mass': mass})
            first = last + 1

    profiles = {'baseline': [], 'zipf099': []}
    active_counts = [sum(count for i, count in enumerate(counts) if i // 4 == p or i % 4 == p)
                     for p in range(4)]
    total_visit_bytes = sum(active_counts) * FILE_BYTES * 2
    mean_iops = total_visit_bytes / TRANSFER_BYTES / 600
    for profile, phases in profiles.items():
        for interval, active in enumerate(active_counts):
            lanes = []
            for b in bins:
                if b['source_interval'] != interval and b['destination_interval'] != interval:
                    continue
                weight = b['files'] / active if profile == 'baseline' else (
                    b['cell_files'] / active * b['conditional_zipf_mass'])
                lanes.append({'bin': b['id'], 'weight': weight,
                              'xfersize': TRANSFER_BYTES, 'fileio': 'sequential',
                              'fileselect': 'sequential', 'threads': 1,
                              'psw_role': 'memory_shard' if b['destination_interval'] == interval else 'sliding_window',
                              'source_operations': ['read', 'write'],
                              'executed_operation': 'read', 'logical_access_multiplier': 2})
            logical_bytes = 2 * active * FILE_BYTES
            logical_iops = logical_bytes / TRANSFER_BYTES / 150
            phases.append({'name': f'psw_interval_{interval}', 'seconds': 150,
                           'start_s': interval * 150, 'end_s': (interval + 1) * 150,
                           'interval': interval, 'active_files': active,
                           'logical_access_multiplier': 2,
                           'logical_visit_bytes': logical_bytes,
                           'logical_rate_iops': logical_iops,
                           'rate_multiplier': logical_iops / mean_iops,
                           'lanes': lanes})
    return {'id': 'graph_graphchi_psw_v2', 'bins': bins, 'profiles': profiles,
            'default_profile': 'baseline', 'prepare_batch_size': 20,
            'mean_logical_iops': mean_iops,
            'logical_visit_bytes': total_visit_bytes,
            'rate_semantics': 'Configured mean IOPS times phase rate_multiplier; one logical sweep mean is mean_logical_iops.',
            'coverage_semantics': '600 seconds schedules active sets; it does not guarantee a completed sweep or file coverage.',
            'zipf_semantics': 'Fixed rank conditional Zipf(0.99) inside each cell; cell mass is preserved.',
            'quantization_tv': math.fsum(abs(count / TOTAL_FILES - n / total) for count, n in zip(counts, edges)) / 2,
            'provenance': {
                'topology': topology,
                'algorithm_url': 'https://www.usenix.org/system/files/conference/osdi12/osdi12-final-126.pdf',
                'implementation_commit': '6461c89f217f63482e2468d776bb942067f8288c',
                'design': '2026-09-14-graphchi-psw-design-candidate.md',
                'model_scope': 'Synthetic equal-byte edge fragments; not native graph encoding or measured trace.',
                'write_mapping': 'Full-update template: active-edge load and writeback both execute as reads on the same bins, with logical volume doubled.'}}
