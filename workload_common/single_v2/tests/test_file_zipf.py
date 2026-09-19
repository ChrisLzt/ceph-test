import copy
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from workload_common.single_v2 import CASES, build, core


class FileZipfTests(unittest.TestCase):
    def test_global_file_probability_and_inventory(self):
        from workload_common.single_v2.file_zipf import transform
        total=0
        for case in CASES:
            source=build(case); before=copy.deepcopy(source)
            model=transform(source,case)
            self.assertEqual(source,before)
            total+=core.validate_model(model)
            self.assertEqual(Counter({size:sum(b['files'] for b in source['bins'] if b['size_bytes']==size) for size in {b['size_bytes'] for b in source['bins']}}),
                             Counter({size:sum(b['files'] for b in model['bins'] if b['size_bytes']==size) for size in {b['size_bytes'] for b in model['bins']}}))
            members=[member for b in model['bins'] for member in b['source_members']]
            n=sum(b['files'] for b in source['bins'])
            self.assertEqual(sorted(m[2] for m in members),list(range(1,n+1)))
            self.assertEqual(len({tuple(m[:2]) for m in members}),n)
            self.assertLessEqual(len(model['bins']),256)
            for phases in model['profiles'].values():
                for phase in phases:
                    self.assertLessEqual(len(phase['lanes']),256)
            p=[r**-.99 for r in range(1,n+1)]; z=sum(p)
            expected={b['id']:sum(p[m[2]-1]/z for m in b['source_members']) for b in model['bins']}
            for phase in model['profiles']['file_zipf099']:
                self.assertEqual(len(phase['lanes']),len(model['bins']))
                for lane in phase['lanes']:
                    self.assertAlmostEqual(lane['weight'],expected[lane['bin']])
                    self.assertEqual(lane['fileselect'],'random')
                    self.assertEqual(lane['stopafter'],1)
            self.assertLess(model['file_zipf']['tv_distance'],.02)
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                core.render(model,data_root=root/'data',output=root/'cfg',rate=100)
                core.validate_bundle(root/'cfg')
                self.assertFalse((root/'data').exists())
        self.assertEqual(total,706704703488)

    def test_repeatable_and_exact_top_ranks(self):
        from workload_common.single_v2.file_zipf import transform
        source=build('wrf')
        a=transform(source,'wrf');b=transform(source,'wrf')
        self.assertEqual(a,b)
        for bin in a['bins']:
            if min(m[2] for m in bin['source_members'])<=32:
                self.assertEqual(bin['files'],1)

    def test_two_phase_inference_bundle_validation(self):
        from workload_common.single_v2.file_zipf import transform
        model=transform(build('ai_inference'),'ai_inference')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            core.render(model,data_root=root/'data',output=root/'cfg',rate=100)
            manifest=core.validate_bundle(root/'cfg')
            self.assertEqual(manifest['capacity_bytes'],115*2**30)
            config=root/'cfg'/'run_file_zipf099.vdb'
            config.write_text(config.read_text().replace('elapsed=240','elapsed=241'))
            with self.assertRaises(ValueError):
                core.validate_bundle(root/'cfg')
