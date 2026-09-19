"""SINGLE-only source-derived workloads; legacy multi-server models are unchanged."""
CASES = {
    'baleen': 'bigdata_baleen_v2',
    'graphchi': 'graph_graphchi_psw_v2',
    'wrf': 'hpc_wrf_continuous_v2',
    'ai_training': 'ai_training_ses_v2',
    'ai_inference': 'ai_inference_ses_v2',
}


def build(case):
    from . import baleen, graphchi, wrf, ses_ai
    factories = {'baleen':baleen.build, 'graphchi':graphchi.build, 'wrf':wrf.build,
                 'ai_training':ses_ai.build_training, 'ai_inference':ses_ai.build_inference}
    return factories[case]()
