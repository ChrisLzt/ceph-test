"""Continuous WRF-inspired lifecycle; outputs become reads at their save event.

All physical files are precreated synthetic fragments. The model includes no
failure, rollback or recovery read and does not execute a weather simulation.
"""
FILE_BYTES = 64 * 1024 ** 2
TRANSFER_BYTES = 4 * 1024 ** 2


def build():
    """Return the 19-event baseline; no Zipf control was approved for WRF."""
    groups = [('input', 128, 'input', 'read')]
    groups += [(f'boundary_{i}', 32, 'boundary', 'read') for i in range(4)]
    groups += [(f'history_{i:02d}', 64, 'history', 'write') for i in range(1, 17)]
    groups += [(f'restart_{hour:02d}h', 256, 'restart', 'write') for hour in (8, 16)]
    bins = [{'id': name, 'group': name, 'files': count, 'size_bytes': FILE_BYTES,
             'source_role': role, 'source_operation': operation,
             'executed_operation': 'read'} for name, count, role, operation in groups]
    by_id = {b['id']: b for b in bins}
    events = [('cold_start', 80, ['input', 'boundary_0'], 0)]
    for hour in range(1, 17):
        history = f'history_{hour:02d}'
        active = [history]
        if hour in (5, 9, 13):
            active.insert(0, f'boundary_{(hour - 1) // 4}')
        events.append((history, 25, active, hour))
        if hour in (8, 16):
            restart = f'restart_{hour:02d}h'
            events.append((restart + '_output', 60, [restart], hour))

    total_bytes = sum(b['files'] * FILE_BYTES for b in bins)
    mean_iops = total_bytes / TRANSFER_BYTES / 600
    phases = []
    start = 0
    for name, seconds, active, hour in events:
        logical_bytes = sum(by_id[group]['files'] * FILE_BYTES for group in active)
        logical_iops = logical_bytes / TRANSFER_BYTES / seconds
        lanes = []
        for group in active:
            b = by_id[group]
            lanes.append({'bin': group, 'weight': b['files'] * FILE_BYTES / logical_bytes,
                          'xfersize': TRANSFER_BYTES, 'fileio': 'sequential',
                          'fileselect': 'sequential', 'threads': 1,
                          'source_role': b['source_role'],
                          'source_operation': b['source_operation'],
                          'executed_operation': 'read'})
        phases.append({'name': name, 'seconds': seconds, 'start_s': start,
                       'end_s': start + seconds, 'simulation_hour': hour,
                       'logical_visit_bytes': logical_bytes,
                       'logical_rate_iops': logical_iops,
                       'rate_multiplier': logical_iops / mean_iops, 'lanes': lanes})
        start += seconds
    return {'id': 'hpc_wrf_continuous_v2', 'bins': bins,
            'profiles': {'baseline': phases}, 'default_profile': 'baseline',
            'prepare_batch_size': 20, 'mean_logical_iops': mean_iops,
            'logical_visit_bytes': total_bytes,
            'scenario': 'continuous forecast; no failure, rollback or recovery-file reread',
            'rate_semantics': 'Configured mean IOPS times phase rate_multiplier; one logical visit mean is mean_logical_iops.',
            'coverage_semantics': 'Event duration does not guarantee full file coverage, a saved checkpoint, or forecast completion.',
            'provenance': {
                'design': '2026-09-14-wrf-continuous-design-candidate.md',
                'source_urls': [
                    'https://www2.mmm.ucar.edu/wrf/users/wrf_users_guide/build/html/running_wrf.html',
                    'https://www2.mmm.ucar.edu/wrf/users/wrf_users_guide/build/html/namelist_variables.html',
                    'https://www2.mmm.ucar.edu/wrf/site/online_tutorial/restart_exercise.html'],
                'model_scope': 'Engineering lifecycle and capacities; not a WRF trace, NetCDF replay, or MPI simulation.',
                'write_mapping': 'History and restart source writes execute as reads only at their output event.',
                'event_order_scope': 'Boundary read and history output share an RD; their internal call order is not reproduced.',
                'namelist_semantics': {'history_interval': 60, 'history_begin': 60,
                                      'frames_per_outfile': 1, 'restart_interval': 480,
                                      'interval_seconds': 14400, 'restart': False}}}
