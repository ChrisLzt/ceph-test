"""Current SINGLE selection; aliases workload semantics without moving data."""
from copy import deepcopy
from pathlib import Path
from . import CASES, build
from .baleen_static import build as build_static
from .phase_zipf import transform

DATA_PARENTS={
    'baleen':'/mnt/cephfs/single_baleen_static_v1',
    'graphchi':'/mnt/cephfs/single_business_phase_v1',
    'wrf':'/mnt/cephfs/single_structural_zipf_v2',
    'ai_training':'/mnt/cephfs/single_ses_perf_zipf_v1',
    'ai_inference':'/mnt/cephfs/single_structural_zipf_v2',
}


def data_root(case):
    return Path(DATA_PARENTS[case])/CASES[case]


def build_current(case):
    model=build_static() if case=='baleen' else transform(build(case),case)
    selected='baseline' if case=='baleen' else 'phase_zipf099'
    model['profiles']={'baseline':model['profiles']['baseline'],
                       'current':deepcopy(model['profiles'][selected])}
    model['provenance']['current_suite']={'revision':'2026-09-17','source_profile':selected,
        'design':'static_native' if case=='baleen' else 'phase_zipf',
        'baseline_semantics':'native-frequency snapshot' if case=='baleen' else 'uniform within compatible groups'}
    return model
