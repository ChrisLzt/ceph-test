"""Explicit CLI: render/validate/preflight never start a workload."""
import argparse
import json
import os
from pathlib import Path
import sys

from . import CASES, build
from . import core, lifecycle

REPO = Path(__file__).resolve().parents[2]


def _rate(text):
    if text == 'max':
        return text
    try:
        value = float(text)
        core._positive(value, 'rate')
        return value
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['render','validate','preflight','prepare','verify','run','parser-check','preview'])
    parser.add_argument('--case', choices=['all',*CASES], default='all')
    parser.add_argument('--data-root', type=Path, default=Path('/mnt/cephfs/single_v2'))
    parser.add_argument('--output-root', type=Path, default=REPO/'SINGLE_workload')
    parser.add_argument('--rate', type=_rate, default='max', help='mean target IOPS; current design requires max (default)')
    parser.add_argument('--profile', choices=['baseline','zipf099','file_zipf099','phase_zipf099','current'], default='current')
    parser.add_argument('--design', choices=['source','file_zipf','phase_zipf','static_native','current'], default='current', help='file_zipf: global ranks; phase_zipf: business phases; static_native: Baleen native snapshot; derived designs require separate roots')
    parser.add_argument('--vdbench', type=Path, default=Path(os.environ.get('VDBENCH_HOME','/home/chris/PDSL/vdbench'))/'vdbench')
    parser.add_argument('--results', type=Path, help='new results root; each case gets its own child')
    parser.add_argument('--execute', action='store_true', help='explicitly perform preparation/measurement; requires user authorization')
    args=parser.parse_args()
    try:
        if args.action in ('prepare','run') and not args.execute:
            raise ValueError('this action requires explicit --execute')
        cases=list(CASES) if args.case=='all' else [args.case]
        bundles={case:args.output_root/CASES[case]/'rendered' for case in cases}
        if args.action=='render':
            if args.design != 'current' and args.output_root.resolve() == (REPO/'SINGLE_workload').resolve():
                raise ValueError('historical designs require a separate output root')
            if args.design=='static_native' and cases!=['baleen']:
                raise ValueError('static_native requires --case baleen')
            if args.design=='current':
                from .current_suite import build_current
                if args.rate!='max':raise ValueError('current suite requires --rate max')
                models={case:build_current(case) for case in cases}
            else:
                models={case:build(case) for case in cases}
            if args.design in ('file_zipf','phase_zipf','static_native'):
                if args.output_root == REPO/'SINGLE_workload' or args.data_root == Path('/mnt/cephfs/single_v2'):
                    raise ValueError('derived designs require separate --output-root and --data-root; preserve existing baseline data')
                if args.design == 'file_zipf':
                    from .file_zipf import transform
                elif args.design == 'phase_zipf':
                    from .phase_zipf import transform
                else:
                    from .baleen_static import build as build_static
                    transform = lambda model, case: build_static()
                models = {case:transform(model, case) for case,model in models.items()}
            total=sum(core.validate_model(model) for model in models.values())
            if args.case=='all' and not 500*2**30<=total<=700*2**30:
                raise ValueError('suite model capacity outside 500–700 GiB')
            from .current_suite import data_root as current_data_root
            reports=[core.render(model,data_root=(current_data_root(case) if args.design=='current' and args.data_root==Path('/mnt/cephfs/single_v2') else args.data_root/model['id']),output=bundles[case],rate=args.rate) for case,model in models.items()]
        else:
            reports=[core.validate_bundle(bundles[case]) for case in cases]
        for case, manifest in zip(cases,reports):
            if manifest['id'] != CASES[case]: raise ValueError('bundle case identity mismatch')
        roots=[core.safe_path(m['data_root']) for m in reports]
        for i, root in enumerate(roots):
            for other in roots[i+1:]:
                if root==other or root in other.parents or other in root.parents:
                    raise ValueError('selected cases have overlapping data roots')
        total=sum(m['capacity_bytes'] for m in reports)
        if args.case=='all' and not 500*2**30<=total<=700*2**30:
            raise ValueError('suite rendered capacity outside 500–700 GiB')
        if args.profile=='current':
            for m in reports:
                if 'current' not in m['profiles']:raise ValueError(f"{m['id']} has no current profile")
        if args.action == 'preview':
            print(core.json_text({'action':'preview','real_io_executed':False,'total_gib':total/2**30,
                'cases':[{'id':m['id'],'data_root':m['data_root'],'profile':args.profile,
                          'config':str(bundles[c]/f'run_{args.profile}.vdb'),
                          'config_sha256':m['config_sha256'][f'run_{args.profile}.vdb'],
                          'phases':m['profiles'][args.profile]} for c,m in zip(cases,reports)]}),end='')
            return 0
        if args.action == 'parser-check':
            if args.results is None: raise ValueError('--results must be a new parser report directory')
            from .parser_check import check
            report=check(list(bundles.values()),jar=args.vdbench.parent/'vdbench.jar',output=args.results)
            print(core.json_text(report),end='');return 0
        if args.action in ('preflight','prepare'):
            checks=[lifecycle.preflight(bundles[case]) for case in cases]
            # Require the complete selected suite to fit, not just every case separately.
            mounts={}
            for check in checks:
                group=mounts.setdefault(check['mount']['target'],{'required':0,'available':check['available_bytes']})
                group['required']+=check['required_free_bytes']
                group['available']=min(group['available'],check['available_bytes'])
            for target, group in mounts.items():
                if group['required']>group['available']:
                    raise ValueError(f"selected suite needs {group['required']} bytes free on {target}; available {group['available']}")
            if args.action=='preflight':
                print(core.json_text(checks),end='');return 0
        if args.action in ('prepare','run'):
            if not args.execute: raise ValueError('this action requires explicit --execute')
            if args.results is None: raise ValueError('--results must be a new directory outside data')
            lifecycle.validate_outputs(reports,list(bundles.values()),args.results)
            lifecycle._executable(args.vdbench)
        if args.action == 'run':
            for manifest in reports:
                if args.profile not in manifest['profiles']:
                    raise ValueError(f"{manifest['id']} has no {args.profile} profile")
            for case in cases:
                lifecycle.check_ready(bundles[case])
        if args.action in ('prepare','run'):
            if not args.execute: raise ValueError('this action requires explicit --execute')
            if args.results is None: raise ValueError('--results must be a new directory outside data')
            for case in cases:
                options={'vdbench':args.vdbench,'output':args.results/CASES[case],'execute':True}
                if args.action=='run':options.update(profile=args.profile)
                report=getattr(lifecycle,args.action)(bundles[case],**options)
                print(core.json_text(report),end='')
        elif args.action=='verify':
            for case in cases: print(core.json_text(lifecycle.check_ready(bundles[case])),end='')
        else:
            print(core.json_text({'action':args.action,'cases':[{'id':m['id'],'files':m['file_count'],'capacity_gib':m['capacity_bytes']/2**30,'max_run_fwd':m['max_run_fwd'],'max_prepare_fwd':m['max_prepare_fwd']} for m in reports], 'total_gib':total/2**30,'real_io_executed':False}),end='')
        return 0
    except (ValueError, OSError, KeyError) as error:
        print(f'FAIL: {error}',file=sys.stderr)
        return 1

if __name__=='__main__':sys.exit(main())
