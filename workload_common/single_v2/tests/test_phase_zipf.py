import copy
import unittest
from collections import Counter,defaultdict
from workload_common.single_v2 import CASES,build,core
from workload_common.single_v2.phase_zipf import transform


class PhaseZipfTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models={c:transform(build(c),c) for c in CASES}

    def test_inventory_budget_and_independent_probability_error(self):
        total=0
        for case,m in self.models.items():
            old=build(case)
            total+=core.validate_model(m)
            expected={(b['id'],i):b['size_bytes'] for b in old['bins'] for i in range(b['files'])}
            actual={tuple(member[:2]):b.get('logical_size_bytes',b['size_bytes']) for b in m['bins'] for member in b['source_members']}
            if case=='baleen':
                self.assertTrue(actual.keys()<=expected.keys())
                self.assertTrue(all(size==expected[key] for key,size in actual.items()))
                self.assertEqual({key[0] for key in actual},{b['id'] for b in old['bins']})
                self.assertEqual(sum(actual.values()),128*2**30)
                self.assertEqual(len(actual),20307)
            else:self.assertEqual(actual,expected)
            self.assertEqual(sum(len(b['source_members']) for b in m['bins']),len(actual))
            sizes=defaultdict(int)
            for b in m['bins']:sizes[b['group']]+=len(b['source_members'])
            for phase,audit in zip(m['profiles']['phase_zipf099'],m['phase_zipf']['phases']):
                self.assertLessEqual(len(phase['lanes']),256)
                self.assertEqual({l['bin'] for l in phase['lanes']},{b['id'] for b in m['bins'] if b['group'] in audit['group_weights']})
                lookup=defaultdict(float)
                for lane in phase['lanes']:
                    lookup[lane['bin']]+=lane['weight']
                    self.assertNotIn('stopafter',lane)
                    self.assertEqual(lane['fileselect'],'random')
                tv=0;group_mass=defaultdict(float)
                for b in m['bins']:
                    if b['id'] not in lookup:continue
                    mass=lookup[b['id']];group=b['group'];group_mass[group]+=mass
                    z=sum(r**-.99 for r in range(1,sizes[group]+1))
                    for _,_,rank in b['source_members']:
                        ideal=audit['group_weights'][group]*rank**-.99/z
                        tv+=abs(mass/len(b['source_members'])-ideal)/2
                for group,mass in group_mass.items():self.assertAlmostEqual(mass,audit['group_weights'][group])
                self.assertAlmostEqual(tv,audit['tv_distance'])
                self.assertLessEqual(tv,.09 if case=='ai_inference' else .06)
        self.assertEqual(total,706704703488-202163355648+128*2**30)

    def test_original_phase_eligibility_and_group_mass(self):
        for case in ('baleen','graphchi'):
            old=build(case);m=self.models[case]
            self.assertEqual([(p['name'],p['seconds']) for p in old['profiles']['baseline']],[(p['name'],p['seconds']) for p in m['profiles']['phase_zipf099']])
            old_bins={b['id']:b for b in old['bins']};new_bins={b['id']:b for b in m['bins']}
            for original,phase in zip(old['profiles']['baseline'],m['profiles']['phase_zipf099']):
                expected={(l['bin'],i) for l in original['lanes'] for i in range(old_bins[l['bin']]['files'])}
                actual={tuple(member[:2]) for l in phase['lanes'] for member in new_bins[l['bin']]['source_members']}
                selected={tuple(member[:2]) for b in m['bins'] for member in b['source_members']}
                self.assertEqual(actual,expected & selected)

    def test_wrf_grouped_events_preserve_inventory_and_weighted_quotas(self):
        old=build('wrf');m=self.models['wrf']
        batches=[(0,1),(1,5),(5,9),(9,10),(10,14),(14,18),(18,19)]
        original=old['profiles']['baseline'];lookup={b['id']:b['group'] for b in old['bins']}
        new_lookup={b['id']:b['group'] for b in m['bins']}
        for profile in m['profiles'].values():
            self.assertEqual([p['seconds'] for p in profile],[80,100,100,60,100,100,60])
            self.assertEqual([(p['start_s'],p['end_s']) for p in profile],[(0,80),(80,180),(180,280),(280,340),(340,440),(440,540),(540,600)])
            for phase,(a,b) in zip(profile,batches):
                expected=defaultdict(float);actual=defaultdict(float)
                allowed={l['bin'] for event in original[a:b] for l in event['lanes']}
                for oldbin in old['bins']:
                    if oldbin['id'] not in allowed:continue
                    group=oldbin['group']
                    if group.startswith('history_'):
                        n=int(group.split('_')[1]);first=(n-1)//4*4+1;group=f'history_{first:02d}_{first+3:02d}'
                    expected[group]+=oldbin['files']*oldbin['size_bytes']
                total=sum(expected.values());expected={g:w/total for g,w in expected.items()}
                actual_sources={member[0] for l in phase['lanes'] for bb in m['bins'] if bb['id']==l['bin'] for member in bb['source_members']}
                self.assertEqual(actual_sources,allowed)
                for lane in phase['lanes']:actual[new_lookup[lane['bin']]]+=lane['weight']
                self.assertEqual(actual.keys(),expected.keys())
                for group,weight in expected.items():self.assertAlmostEqual(actual[group],weight)
                self.assertLessEqual(len(phase['lanes']),256)

    def test_ai_preserves_perf_joint_io_distribution_in_one_rd(self):
        def distribution(model, phase):
            bins={b['id']:b for b in model['bins']}
            result=defaultdict(float)
            for lane in phase['lanes']:
                xfer=lane['xfersize']
                pairs=xfer if isinstance(xfer,list) else [(xfer,1)]
                total=sum(w for _,w in pairs)
                for size,weight in pairs:
                    result[(bins[lane['bin']].get('logical_size_bytes',bins[lane['bin']]['size_bytes']),lane['fileio'],size)]+=lane['weight']*weight/total
            return result
        for case in ('ai_training','ai_inference'):
            source=build(case);model=self.models[case]
            expected=distribution(source,source['profiles']['baseline'][0])
            for profile in model['profiles'].values():
                self.assertEqual(len(profile),1)
                self.assertEqual(profile[0]['seconds'],600)
                actual=distribution(model,profile[0])
                self.assertEqual(actual.keys(),expected.keys())
                for key,value in expected.items():self.assertAlmostEqual(actual[key],value)
                self.assertLessEqual(len(profile[0]['lanes']),256)
                self.assertEqual({l['bin'] for l in profile[0]['lanes']},{b['id'] for b in model['bins']})
            self.assertTrue(all(b['group']==f"size_{b.get('logical_size_bytes',b['size_bytes'])}" for b in model['bins']))

    def test_inference_two_fragments_per_logical_file(self):
        m=self.models['ai_inference']
        self.assertEqual(len(m['bins']),100)
        self.assertEqual(sum(b['files'] for b in m['bins']),200)
        self.assertEqual(sum(b['files']*b['size_bytes'] for b in m['bins']),115*2**30)
        for b in m['bins']:
            self.assertEqual(b['files'],2)
            self.assertEqual(len(b['source_members']),1)
            self.assertEqual(b['logical_size_bytes'],2*b['size_bytes'])
            self.assertEqual(b['fragments'],[{'file_index':0,'offset_bytes':0,'length_bytes':b['size_bytes']},
                                             {'file_index':1,'offset_bytes':b['size_bytes'],'length_bytes':b['size_bytes']}])
        p=m['profiles']['phase_zipf099'][0]
        self.assertEqual(len(p['lanes']),200)
        self.assertLess(m['phase_zipf']['phases'][0]['tv_distance'],1e-12)

    def test_determinism_source_preservation_and_read_only_config(self):
        from pathlib import Path
        old=build('ai_inference');snapshot=copy.deepcopy(old)
        self.assertEqual(transform(old,'ai_inference'),self.models['ai_inference'])
        self.assertEqual(old,snapshot)
        for case in ('ai_training','ai_inference'):
            text=core.config_texts(self.models[case],Path('/no-io'), 'max')[0]['run_phase_zipf099.vdb']
            self.assertNotIn('operation=write', text)
            self.assertIn('elapsed=600', text)
            core.validate_model(self.models[case])
