import collections
import importlib.util
import math
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'ses_ai.py'


class SESAIModelsTest(unittest.TestCase):
    def build(self, kind):
        self.assertTrue(MODULE.exists(), 'SES model implementation is missing')
        spec = importlib.util.spec_from_file_location('ses_ai_under_test', MODULE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return getattr(module, 'build_' + kind)()

    def test_exact_layout_capacity_and_concurrency(self):
        expectations = {
            'training': (10000, 196, 388, 123363000320, {65536: 6030, 131072: 2970, 1048576: 500, 2097152: 200, 8388608: 100, 134217728: 100, 1073741824: 100}),
            'inference': (100, 24, 96, 123480309760, {536870912: 30, 1073741824: 40, 2147483648: 30}),
        }
        for kind, (files, bins, fwds, capacity, sizes) in expectations.items():
            with self.subTest(kind=kind):
                model = self.build(kind)
                self.assertEqual(model['id'], 'ai_' + kind + '_ses_v2')
                self.assertEqual(len(model['bins']), bins)
                self.assertEqual(len({b['id'] for b in model['bins']}), bins)
                self.assertEqual(sum(b['files'] for b in model['bins']), files)
                self.assertEqual(sum(b['files'] * b['size_bytes'] for b in model['bins']), capacity)
                actual = collections.Counter()
                for b in model['bins']:
                    actual[b['size_bytes']] += b['files']
                self.assertEqual(actual, sizes)
                for phases in model['profiles'].values():
                    self.assertEqual(sum(p['seconds'] for p in phases), 600)
                    lanes = phases[0]['lanes']
                    self.assertEqual(len(lanes), fwds)
                    counts = collections.Counter(l['bin'] for l in lanes)
                    for b in model['bins']:
                        self.assertGreaterEqual(b['files'], counts[b['id']])
                    self.assertTrue(all(l['threads'] == 1 and 'stopafter' not in l for l in lanes))

    def test_profiles_preserve_class_mass_and_source_channel_mapping(self):
        for kind in ['training', 'inference']:
            model = self.build(kind)
            by_id = {b['id']: b for b in model['bins']}
            profile_masses = []
            for name in ['baseline', 'zipf099']:
                lanes = model['profiles'][name][0]['lanes']
                self.assertAlmostEqual(sum(l['weight'] for l in lanes), 1)
                self.assertTrue(all(l['weight'] > 0 for l in lanes))
                masses = collections.defaultdict(float)
                channels = collections.defaultdict(float)
                for l in lanes:
                    masses[by_id[l['bin']]['size_bytes']] += l['weight']
                    channels[(l['xfersize'], l['fileio'], l['fileselect'])] += l['weight']
                profile_masses.append(masses)
                if kind == 'training':
                    expected = {(8192, 'sequential', 'sequential'): .2, (32768, 'sequential', 'sequential'): .2, (65536, 'sequential', 'sequential'): .2, (1048576, 'sequential', 'sequential'): .4}
                else:
                    expected = {(131072, 'sequential', 'sequential'): .3, (65536, 'sequential', 'sequential'): .3, (131072, 'random', 'random'): .2, (65536, 'random', 'random'): .2}
                self.assertEqual(set(channels), set(expected))
                for key, weight in expected.items():
                    self.assertAlmostEqual(channels[key], weight)
            for size in profile_masses[0]:
                self.assertAlmostEqual(profile_masses[0][size], profile_masses[1][size])

    def test_conditional_zipf_error_and_identity_are_reproducible(self):
        for kind, expected_tv, expected_top in [('training', 4.26347224993344, 56.493295332824445), ('inference', 13.766302846904498, 6.738358609977582)]:
            model = self.build(kind)
            self.assertEqual(model, self.build(kind))
            lanes = model['profiles']['zipf099'][0]['lanes']
            weights = collections.defaultdict(float)
            for lane in lanes:
                weights[lane['bin']] += lane['weight']
            tv = 0
            file_probs = []
            groups = collections.defaultdict(list)
            for b in model['bins']:
                groups[b['group']].append(b)
            for bins in groups.values():
                n = sum(b['files'] for b in bins)
                ideal = [r ** -.99 for r in range(1, n + 1)]
                normalizer = math.fsum(ideal)
                mass = math.fsum(weights[b['id']] for b in bins)
                start = 0
                for b in bins:
                    self.assertEqual(b['rank_start'], start + 1)
                    per_file = weights[b['id']] / b['files']
                    file_probs.extend([per_file] * b['files'])
                    tv += sum(abs(mass * p / normalizer - per_file) for p in ideal[start:start + b['files']]) / 2
                    start += b['files']
            self.assertAlmostEqual(tv * 100, expected_tv, places=10)
            self.assertAlmostEqual(sum(sorted(file_probs, reverse=True)[:len(file_probs)//100]) * 100, expected_top, places=9)


if __name__ == '__main__':
    unittest.main()
