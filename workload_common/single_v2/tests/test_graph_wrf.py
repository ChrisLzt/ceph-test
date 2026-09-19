"""Independent design acceptance checks; never create benchmark data."""
import importlib
import importlib.util
import json
import math
import unittest
from collections import Counter, defaultdict

MIB = 1024 ** 2
GIB = 1024 ** 3


def build_model(name):
    module = 'workload_common.single_v2.' + name
    if importlib.util.find_spec(module) is None:
        raise AssertionError('missing approved pure model: ' + name)
    return importlib.import_module(module).build()


class GraphChiTests(unittest.TestCase):
    def test_topology_quantization_and_shared_storage(self):
        m = build_model('graphchi')
        topology = m['provenance']['topology']
        self.assertEqual(topology['nodes'], 875713)
        self.assertEqual(topology['edges'], 5105039)
        self.assertEqual(topology['inclusive_interval_cuts'], [245316, 487247, 718657])
        self.assertEqual(topology['compressed_sha256'], 'bcac0af0471d749f4a8c010bca92b61cf2868a0570741de06892fc062f265ea6')
        self.assertEqual(sum(map(sum, topology['edge_matrix_src_rows_dst_columns'])), 5105039)
        self.assertEqual(len(m['bins']), 384)
        self.assertEqual(len({b['id'] for b in m['bins']}), 384)
        self.assertEqual(sum(b['files'] for b in m['bins']), 2048)
        self.assertEqual(sum(b['files'] * b['size_bytes'] for b in m['bins']), 128 * GIB)
        cells = defaultdict(list)
        for b in m['bins']:
            self.assertGreater(b['files'], 0)
            self.assertEqual(b['size_bytes'], 64 * MIB)
            cells[b['source_interval'], b['destination_interval']].append(b)
        want = [[137,137,138,138], [135,135,136,135], [130,129,129,130], [110,110,110,109]]
        for (s,d), bins in cells.items():
            self.assertEqual(len(bins), 24)
            self.assertEqual([b['files'] for b in bins[:12]], [1] * 12)
            self.assertEqual(sum(b['files'] for b in bins), want[s][d])
            ranks = [r for b in bins for r in range(b['rank_start'], b['rank_end'] + 1)]
            self.assertEqual(ranks, list(range(1, want[s][d] + 1)))
        self.assertLess(m['quantization_tv'], 0.0011)
        json.dumps(m, allow_nan=False)

    def test_psw_cross_intersection_and_converted_writes(self):
        m = build_model('graphchi')
        bins = {b['id']: b for b in m['bins']}
        profiles = m['profiles']
        self.assertEqual(set(profiles), {'baseline', 'zipf099'})
        for phases in profiles.values():
            self.assertEqual([p['seconds'] for p in phases], [150] * 4)
            counts = Counter()
            for interval, p in enumerate(phases):
                self.assertEqual(len(p['lanes']), 168)
                selected = [bins[l['bin']] for l in p['lanes']]
                self.assertEqual(len({b['id'] for b in selected}), 168)
                self.assertEqual({(b['source_interval'],b['destination_interval']) for b in selected},
                                 {(s,d) for s in range(4) for d in range(4) if s == interval or d == interval})
                active = [925,917,902,842][interval]
                self.assertEqual(sum(b['files'] for b in selected), active)
                self.assertEqual(p['logical_visit_bytes'], 2 * active * 64 * MIB)
                self.assertEqual(p['logical_access_multiplier'], 2)
                self.assertAlmostEqual(p['rate_multiplier'], active / 896.5)
                self.assertAlmostEqual(sum(l['weight'] for l in p['lanes']), 1.0)
                for lane in p['lanes']:
                    self.assertEqual(lane['source_operations'], ['read', 'write'])
                    self.assertEqual(lane['executed_operation'], 'read')
                    self.assertEqual(lane['xfersize'], 4 * MIB)
                    self.assertEqual(lane['fileio'], 'sequential')
                    self.assertEqual(lane['fileselect'], 'sequential')
                    self.assertNotIn('stopafter', lane)
                    counts[lane['bin']] += 1
            for id_, b in bins.items():
                self.assertEqual(counts[id_], 1 if b['source_interval'] == b['destination_interval'] else 2)
            self.assertEqual(sum(p['logical_visit_bytes'] for p in phases), 448.25 * GIB)

    def test_conditional_zipf_preserves_cell_mass_and_fixed_ranks(self):
        m = build_model('graphchi')
        bins = {b['id']: b for b in m['bins']}
        errors = []
        for base, control in zip(m['profiles']['baseline'], m['profiles']['zipf099']):
            self.assertEqual([l['bin'] for l in base['lanes']], [l['bin'] for l in control['lanes']])
            self.assertEqual(base['rate_multiplier'], control['rate_multiplier'])
            groups = defaultdict(list)
            active = sum(bins[l['bin']]['files'] for l in base['lanes'])
            for lane in base['lanes']:
                self.assertAlmostEqual(lane['weight'] / bins[lane['bin']]['files'], 1 / active)
            for lane in control['lanes']:
                groups[bins[lane['bin']]['group']].append(lane)
            tv = 0
            for lanes in groups.values():
                n = sum(bins[l['bin']]['files'] for l in lanes)
                mass = n / active
                self.assertAlmostEqual(sum(l['weight'] for l in lanes), mass)
                norm = math.fsum(r ** -0.99 for r in range(1,n+1))
                for lane in lanes:
                    b = bins[lane['bin']]
                    exact = [mass * r ** -0.99 / norm for r in range(b['rank_start'],b['rank_end']+1)]
                    self.assertAlmostEqual(lane['weight'], sum(exact))
                    tv += sum(abs(x - lane['weight'] / b['files']) for x in exact) / 2
            self.assertLess(tv, 0.02)
            errors.append(tv)
        for actual, want in zip(errors, [0.016976898347739484,0.016914197046717043,0.016354564806937353,0.015591974703385]):
            self.assertAlmostEqual(actual, want, places=12)


class WrfTests(unittest.TestCase):
    def test_capacity_and_event_identities(self):
        m = build_model('wrf')
        self.assertEqual(set(m['profiles']), {'baseline'})
        self.assertEqual(len(m['bins']), 23)
        self.assertEqual(sum(b['files'] for b in m['bins']), 1792)
        self.assertEqual(sum(b['files'] * b['size_bytes'] for b in m['bins']), 112 * GIB)
        groups = {b['group']: b['files'] for b in m['bins']}
        self.assertEqual(groups['input'], 128)
        self.assertEqual([groups[f'boundary_{i}'] for i in range(4)], [32] * 4)
        self.assertEqual([groups[f'history_{i:02d}'] for i in range(1,17)], [64] * 16)
        self.assertEqual([groups['restart_08h'],groups['restart_16h']], [256,256])
        json.dumps(m, allow_nan=False)

    def test_continuous_timeline_and_no_recovery_reads(self):
        m = build_model('wrf')
        phases = m['profiles']['baseline']
        self.assertEqual(len(phases), 19)
        self.assertEqual(sum(p['seconds'] for p in phases), 600)
        self.assertEqual([p['name'] for p in phases], ['cold_start'] + [f'history_{i:02d}' for i in range(1,9)] + ['restart_08h_output'] + [f'history_{i:02d}' for i in range(9,17)] + ['restart_16h_output'])
        expected_times = [(0,80)] + [(80+25*i,105+25*i) for i in range(8)] + [(280,340)] + [(340+25*i,365+25*i) for i in range(8)] + [(540,600)]
        self.assertEqual([(p['start_s'],p['end_s']) for p in phases], expected_times)
        bins = {b['id']:b for b in m['bins']}
        seen = Counter()
        source_volume = Counter()
        for phase in phases:
            self.assertLessEqual(len(phase['lanes']), 2)
            self.assertAlmostEqual(sum(l['weight'] for l in phase['lanes']), 1)
            self.assertAlmostEqual(phase['logical_rate_iops'], phase['logical_visit_bytes'] / (4*MIB) / phase['seconds'])
            self.assertAlmostEqual(phase['rate_multiplier'] * m['mean_logical_iops'], phase['logical_rate_iops'])
            for lane in phase['lanes']:
                b = bins[lane['bin']]
                seen[b['group']] += 1
                source_volume[lane['source_operation']] += b['files'] * b['size_bytes']
                expected_op = 'read' if b['group'] == 'input' or b['group'].startswith('boundary') else 'write'
                self.assertEqual(lane['source_operation'], expected_op)
                self.assertEqual(lane['executed_operation'], 'read')
                self.assertEqual(lane['xfersize'], 4*MIB)
                self.assertEqual(lane['fileio'], 'sequential')
                self.assertEqual(lane['fileselect'], 'sequential')
                self.assertNotIn('stopafter', lane)
        self.assertEqual(set(seen.values()), {1})
        self.assertEqual(len(seen), 23)
        self.assertEqual(source_volume, {'read':16*GIB, 'write':96*GIB})
        self.assertEqual([l['weight'] for l in phases[0]['lanes']], [0.8,0.2])
        for index, group in [(5,'boundary_1'),(10,'boundary_2'),(14,'boundary_3')]:
            self.assertEqual(phases[index]['lanes'][0]['bin'], group)
            self.assertEqual([l['weight'] for l in phases[index]['lanes']], [1/3,2/3])
        self.assertAlmostEqual(sum(p['rate_multiplier']*p['seconds'] for p in phases), 600)


if __name__ == '__main__':
    unittest.main()
