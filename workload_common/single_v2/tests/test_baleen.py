"""Baleen source conservation and independently recomputed approximation bounds."""
import importlib
import json
import math
import unittest
from collections import Counter


class BaleenTests(unittest.TestCase):
    def model(self):
        try:
            module = importlib.import_module('workload_common.single_v2.baleen')
        except ModuleNotFoundError:
            self.fail('Baleen build() is not implemented')
        return module.build()

    def test_capacity_and_every_source_identity_survive(self):
        m = self.model()
        self.assertEqual(m['id'], 'bigdata_baleen_v2')
        self.assertEqual(len(m['bins']), 640)
        self.assertEqual(sum(b['files'] for b in m['bins']), 29819)
        self.assertEqual(sum(b['files'] * b['size_bytes'] for b in m['bins']), 202163355648)
        sizes = Counter()
        indices = []
        for b in m['bins']:
            sizes[b['size_bytes'] // 2**20] += b['files']
            indices.extend(b['source_key_indices'])
            self.assertEqual(b['files'], len(b['source_key_indices']))
            for i in b['source_key_indices']:
                key = m['source_keys'][i]
                self.assertEqual(b['size_bytes'], ((key[2]+2**21-1)//2**21)*2**21)
                self.assertEqual(b['active_mask'], sum(1<<w for w,c in enumerate(key[3]) if c))
        self.assertEqual(sizes, {2:6064,4:2489,6:2553,8:17830,10:90,12:157,14:162,16:464,22:1,24:1,26:5,30:2,44:1})
        self.assertEqual(sorted(indices), list(range(29819)))
        self.assertEqual(len({tuple(k[:2]) for k in m['source_keys']}), 29819)
        self.assertEqual(m['provenance']['trace_sha1'], 'd17cc110e8c0b8343224cd1e9177acf669742457')
        self.assertEqual(m['provenance']['source_lines'], 173047)
        self.assertEqual(sum(m['provenance']['source_operations'].values()), 555643)
        self.assertEqual(m['provenance']['source_operations'], {'GET':534172,'PUT':21471})
        self.assertEqual(sum(sum(k[5]) for k in m['source_keys']), 21471)
        self.assertEqual(sum(sum(k[5]) == sum(k[3]) for k in m['source_keys']), 11841)

    def test_histograms_keep_every_get_and_put_and_file_selection_is_per_operation(self):
        m = self.model()
        expected_counts = [353586,122605,36361,43091]
        bins = {b['id']:b for b in m['bins']}
        hist_pairs = []
        for profile in m['profiles'].values():
            self.assertEqual([p['seconds'] for p in profile], [150]*4)
            self.assertAlmostEqual(sum(p['seconds']*p['rate_multiplier'] for p in profile), 600)
            self.assertEqual([len(p['lanes']) for p in profile], [290,368,405,382])
        for w, (native, control) in enumerate(zip(m['profiles']['baseline'],m['profiles']['zipf099'])):
            self.assertAlmostEqual(native['rate_multiplier'], expected_counts[w]*4/555643)
            self.assertEqual(native['rate_multiplier'],control['rate_multiplier'])
            n_hist, z_hist = {}, {}
            for label, phase, hist in [('native',native,n_hist),('zipf',control,z_hist)]:
                for lane in phase['lanes']:
                    b = bins[lane['bin']]
                    self.assertEqual((lane['fileio'],lane['fileselect'],lane['threads'],lane['stopafter']), ('random','random',1,1))
                    self.assertTrue(all(0 < size <= b['size_bytes'] and size%4096 == 0 and count>0 for size,count in lane['xfersize']))
                    hist[lane['bin']] = lane['xfersize']
                    members = [m['source_keys'][i] for i in b['source_key_indices']]
                    self.assertTrue(all(k[3][w] > 0 for k in members))
                    self.assertEqual(sum(count for _,count in lane['xfersize']),sum(k[3][w] for k in members))
                    self.assertEqual(sum(size*count for size,count in lane['xfersize']),sum(k[4][w] for k in members))
                    if label == 'native':
                        self.assertEqual(lane['weight'],sum(k[3][w] for k in members))
                        hist_pairs.append(len(lane['xfersize']))
            self.assertEqual(n_hist,z_hist)
            self.assertEqual(sum(l['weight'] for l in native['lanes']), expected_counts[w])
        self.assertEqual((len(hist_pairs),sum(hist_pairs),max(hist_pairs)), (1445,31448,422))

    def test_native_and_global_zipf_error_bounds_and_inactive_keys(self):
        m = self.model()
        keys = m['source_keys']
        bins = {b['id']:b for b in m['bins']}
        for w in range(4):
            active = sorted((i for i,k in enumerate(keys) if k[3][w]),key=lambda i:(-keys[i][3][w],i))
            targets = {}
            for name, raw in [('baseline',[k[3][w] for k in keys]),('bytes',[k[4][w] for k in keys])]:
                total = sum(raw)
                targets[name] = [v/total for v in raw]
            z = [0.0]*len(keys)
            normalizer = math.fsum(r**(-.99) for r in range(1,len(active)+1))
            for rank,i in enumerate(active,1): z[i] = rank**(-.99)/normalizer
            targets['zipf099'] = z
            for name in ['baseline','bytes','zipf099']:
                phase = m['profiles']['baseline' if name=='bytes' else name][w]
                weights = [(l,l['weight'] * (sum(s*c for s,c in l['xfersize'])/sum(c for _,c in l['xfersize']) if name=='bytes' else 1)) for l in phase['lanes']]
                denom = math.fsum(v for _,v in weights)
                actual = [0.0]*len(keys)
                for lane,weight in weights:
                    b = bins[lane['bin']]
                    for i in b['source_key_indices']: actual[i] = weight/denom/b['files']
                self.assertLess(sum(abs(a-b) for a,b in zip(actual,targets[name]))/2, .08)
                self.assertTrue(all(actual[i]==0 for i,k in enumerate(keys) if not k[3][w]))
                if name != 'bytes':
                    top = math.ceil(len(active)*.01)
                    self.assertLess(abs(sum(sorted(actual)[-top:])-sum(sorted(targets[name])[-top:])), .01)

    def test_build_is_deterministic_json_and_returns_independent_values(self):
        first = self.model()
        second = self.model()
        self.assertEqual(json.dumps(first,sort_keys=True), json.dumps(second,sort_keys=True))
        first['bins'][0]['files'] = -1
        first['profiles']['baseline'][0]['lanes'][0]['xfersize'][0][1] = -1
        self.assertGreater(second['bins'][0]['files'],0)
        self.assertGreater(second['profiles']['baseline'][0]['lanes'][0]['xfersize'][0][1],0)


if __name__ == '__main__':
    unittest.main()
