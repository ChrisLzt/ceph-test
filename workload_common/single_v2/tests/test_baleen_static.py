import unittest
from collections import defaultdict
from pathlib import Path
from workload_common.single_v2 import baleen, core
from workload_common.single_v2 import baleen_static

class StaticBaleenTests(unittest.TestCase):
    def test_native_population_and_distribution(self):
        source=baleen.build();m=baleen_static.build()
        self.assertEqual(core.validate_model(m),202163355648)
        self.assertEqual(sorted(i for b in m['bins'] for i in b['source_key_indices']),list(range(29819)))
        phase=m['profiles']['baseline']
        self.assertEqual([(p['name'],p['seconds']) for p in phase],[('native_all',600)])
        self.assertLessEqual(len(phase[0]['lanes']),256)
        counts=[sum(k[3]) for k in source['source_keys']];total=sum(counts)
        bins={b['id']:b for b in m['bins']};tv=0;actual_hist=defaultdict(float);expected_hist=defaultdict(float)
        for p in source['profiles']['baseline']:
            for l in p['lanes']:
                for size,n in l['xfersize']:expected_hist[size]+=n
        for l in phase[0]['lanes']:
            b=bins[l['bin']];self.assertNotIn('stopafter',l)
            self.assertEqual(l['weight'],sum(counts[i] for i in b['source_key_indices']))
            for i in b['source_key_indices']:tv+=abs(l['weight']/b['files']/total-counts[i]/total)/2
            z=sum(w for _,w in l['xfersize'])
            for size,w in l['xfersize']:actual_hist[size]+=l['weight']*w/z
        for size,n in expected_hist.items():self.assertAlmostEqual(actual_hist[size],n,places=6)
        self.assertEqual(actual_hist.keys(),expected_hist.keys())
        hottest=max(range(len(counts)),key=counts.__getitem__)
        self.assertEqual(next(b['files'] for b in m['bins'] if hottest in b['source_key_indices']),1)
        self.assertLess(tv,.01)
        text=core.config_texts(m,Path('/no-io'),'max')[0]['run_baseline.vdb']
        self.assertNotIn('stopafter=',text)
        self.assertIn('fwdrate=max',text)
