"""Business eligibility and group mass first, conditional file Zipf second.

AI retains the SES PERF single-RD I/O mixture, with conditional file Zipf.
No compute, recovery, object hotspot, or real write is implemented.
"""
from bisect import bisect_left
from collections import defaultdict
from copy import deepcopy
import hashlib
import heapq
import math

ALPHA=.99
MAX_BINS=255  # Reserve one prepare format-default definition.
SEED='business-phase-zipf-v1'


def _sample_baleen(source):
    """Fixed stratified subset; never shrink an I/O or remove an active bin."""
    source=deepcopy(source)
    bins=source['bins'];target=128*2**30
    original=sum(b['files']*b['size_bytes'] for b in bins)
    original_count=sum(b['files'] for b in bins)
    def counts(scale):return [max(1,int(b['files']*scale)) for b in bins]
    def capacity(ns):return sum(n*b['size_bytes'] for n,b in zip(ns,bins))
    if capacity(counts(0))>target:raise ValueError('minimum strata exceed capacity target')
    lo,hi=0.,1.
    for _ in range(60):
        mid=(lo+hi)/2
        if capacity(counts(mid))<=target:lo=mid
        else:hi=mid
    chosen=counts(lo);remaining=target-capacity(chosen)
    while remaining:
        eligible=[i for i,b in enumerate(bins) if chosen[i]<b['files'] and b['size_bytes']<=remaining]
        if not eligible:break
        i=max(eligible,key=lambda j:(lo*bins[j]['files']-chosen[j],-j))
        chosen[i]+=1;remaining-=bins[i]['size_bytes']
    if remaining:raise ValueError('Baleen strata cannot reach exact 128 GiB without changing file sizes')
    seed='baleen-capacity-128-v1'
    for b,n in zip(bins,chosen):
        indices=sorted(range(b['files']),key=lambda i:hashlib.sha256(f'{seed}/{b["id"]}/{i}'.encode()).hexdigest())[:n]
        b['source_file_indices']=sorted(indices)
        b['files']=n
        b['source_key_indices']=[b['source_key_indices'][i] for i in sorted(indices)]
    return source,dict(method='fixed per-original-bin stratified file subset',seed=seed,
                       target_bytes=target,original_bytes=original,actual_bytes=capacity(chosen),
                       original_file_count=original_count,
                       original_population='29819 source files; original baseline retained',
                       sampled_file_count=sum(chosen),
                       retained='all original bin/window eligibility strata; file sizes and transfer histograms',
                       caveat='group request weights and histograms are from full source statistics; omitted keys are not replayed')


def _design(source,case):
    groups=defaultdict(list); member_group={}; lookup={b['id']:b for b in source['bins']}
    inventory=[]
    for b in source['bins']:
        for i in b.get('source_file_indices',range(b['files'])):
            identity=(b['id'],i)
            rank_key=hashlib.sha256(f'{SEED}/{case}/{identity[0]}/{i}'.encode()).hexdigest()
            inventory.append((rank_key,identity,b))
    inventory.sort()
    for _,identity,b in inventory:
        size=b['size_bytes']
        if case.startswith('ai_'):
            role='ses_perf';group=f'size_{size}'
        elif case=='baleen':
            role='baleen';group=f'size_{size}_mask_{b["active_mask"]}'
        else:
            role=b['group'];group=role
        groups[group].append({'source':list(identity),'size':size,'role':role})
        member_group[identity]=group

    # Per-phase business group weights and conditional transfer histograms.
    phases=[]
    for original in source['profiles']['baseline']:
        active={}
        for lane in original['lanes']:
            b=lookup[lane['bin']];group=member_group[(b['id'],b.get('source_file_indices',[0])[0])]
            dest=active.setdefault(group,{'weight':0.,'channels':{}})
            channel=dest['channels'].setdefault(lane['fileio'],{'weight':0.,'hist':defaultdict(float)})
            dest['weight']+=lane['weight'];channel['weight']+=lane['weight']
            pairs=lane['xfersize'] if isinstance(lane['xfersize'],list) else [[lane['xfersize'],1]]
            z=sum(w for _,w in pairs)
            for size,weight in pairs:channel['hist'][size]+=lane['weight']*weight/z
        for data in active.values():
            for channel in data['channels'].values():channel['share']=channel['weight']/data['weight']
        phases.append(dict(name=original['name'],seconds=original['seconds'],groups=active))
    for phase in phases:
        z=sum(v['weight'] for v in phase['groups'].values())
        for data in phase['groups'].values():data['weight']/=z
    return groups,phases


def _wrf_roles(source):
    """Seven timed role groups; byte-based quotas, not measured WRF ratios."""
    source=deepcopy(source)
    for b in source['bins']:
        if b['group'].startswith('history_'):
            n=int(b['group'].split('_')[1]);first=(n-1)//4*4+1
            b['group']=f'history_{first:02d}_{first+3:02d}'
    schedule=[('cold_start',80,['input','boundary_0']),
              ('history_01_04',100,['history_01_04']),
              ('history_05_08',100,['history_05_08','boundary_1']),
              ('restart_08h_output',60,['restart_08h']),
              ('history_09_12',100,['history_09_12','boundary_2']),
              ('history_13_16',100,['history_13_16','boundary_3']),
              ('restart_16h_output',60,['restart_16h'])]
    phases=[]
    for name,seconds,groups in schedule:
        lanes=[dict(bin=b['id'],weight=b['files']*b['size_bytes'],xfersize=4*2**20,
                    fileio='sequential',fileselect='random',threads=1)
               for b in source['bins'] if b['group'] in groups]
        phases.append(dict(name=name,seconds=seconds,lanes=lanes))
    source['profiles']={'baseline':phases}
    source['provenance']['group_adaptation']='seven event groups; four history outputs share one Zipf group; role request mass proportional to synthetic bytes'
    return source


def transform(source,case):
    # Partition logical files first; inference later gets two physical fragments.
    tv_limit=1e-12 if case=='ai_inference' else .06
    if case=='wrf':source=_wrf_roles(source)
    capacity_adaptation=None
    if case=='baleen':
        source,capacity_adaptation=_sample_baleen(source)
    groups,phases=_design(source,case)
    if len(groups)>MAX_BINS:raise ValueError('business groups exceed FWD/bin budget')
    distributions={}; importance=defaultdict(float)
    for phase in phases:
        for group,data in phase['groups'].items():importance[group]=max(importance[group],data['weight'])
    for group,members in groups.items():
        p=[r**-ALPHA for r in range(1,len(members)+1)];z=sum(p);p=[v/z for v in p]
        prefix=[0.]
        for v in p:prefix.append(prefix[-1]+v)
        distributions[group]=(p,prefix,[-v for v in p])
    def error(group,a,b):
        p,prefix,neg=distributions[group];mean=(prefix[b]-prefix[a])/(b-a)
        pivot=bisect_left(neg,-mean,a,b)
        return max(0.,prefix[pivot]-prefix[a]-(pivot-a)*mean)
    min_files={g:1 if case=='ai_inference' else max(len(p['groups'][g]['channels']) for p in phases if g in p['groups']) for g in groups}
    segments={};queue=[]
    def add(group,a,b):
        segments[(group,a,b)]=True
        minimum=min_files[group]
        if b-a<2*minimum:return
        # Evaluate every cut: exact L1 gain for this current segment.
        current=error(group,a,b)
        gain,k=max((current-error(group,a,k)-error(group,k,b),k) for k in range(a+minimum,b-minimum+1))
        heapq.heappush(queue,(-gain*importance[group],group,a,b,k))
    for group,members in sorted(groups.items()):add(group,0,len(members))
    # Baleen's different window eligibility masks need more physical bins,
    # but only the active window's FWDs are instantiated for its RD.
    budget=512 if case=='baleen' else MAX_BINS
    active_counts=[sum(len(d['channels']) for d in p['groups'].values()) for p in phases]
    while len(segments)<budget and queue:
        neg,group,a,b,k=heapq.heappop(queue)
        if neg>=0:break
        active=[i for i,p in enumerate(phases) if group in p['groups']]
        if any(active_counts[i]+len(phases[i]['groups'][group]['channels'])>256 for i in active):continue
        for i in active:active_counts[i]+=len(phases[i]['groups'][group]['channels'])
        del segments[(group,a,b)];add(group,a,k);add(group,k,b)
    bins=[]; bin_mass={}; group_error=defaultdict(float)
    for index,(group,a,b) in enumerate(sorted(segments)):
        members=groups[group][a:b];_,prefix,_=distributions[group]
        name=f'phasezipf_{index:03d}';bin_mass[name]=prefix[b]-prefix[a]
        group_error[group]+=error(group,a,b)
        bins.append(dict(id=name,files=b-a,size_bytes=members[0]['size'],group=group,
                         source_members=[m['source']+[rank] for rank,m in enumerate(members,a+1)],
                         role=members[0]['role']))
    profiles={};audits=[]
    for profile in ('baseline','phase_zipf099'):
        output=[];start=0
        for phase in phases:
            lanes=[]
            for b in bins:
                if b['group'] not in phase['groups']:continue
                data=phase['groups'][b['group']]
                mass=bin_mass[b['id']] if profile=='phase_zipf099' else b['files']/len(groups[b['group']])
                for mode,channel in data['channels'].items():
                    hist=sorted(channel['hist'].items());xfer=hist[0][0] if len(hist)==1 else [list(p) for p in hist]
                    lanes.append(dict(bin=b['id'],weight=data['weight']*mass*channel['share'],xfersize=xfer,
                                      fileio=mode,fileselect='random',threads=1))
            output.append(dict(name=phase['name'],seconds=phase['seconds'],start_s=start,end_s=start+phase['seconds'],rate_multiplier=1,lanes=lanes))
            if profile=='phase_zipf099':
                tv=sum(data['weight']*group_error[g] for g,data in phase['groups'].items())
                if tv>tv_limit:raise ValueError(f'phase Zipf TV exceeds {tv_limit:.0%} in {phase["name"]}: {tv}')
                audits.append(dict(name=phase['name'],seconds=phase['seconds'],fwd_count=len(lanes),tv_distance=tv,
                                   group_weights={g:d['weight'] for g,d in phase['groups'].items()}))
            start+=phase['seconds']
        profiles[profile]=output
    fragmentation=None
    if case=='ai_inference':
        for b in bins:
            if b['files']!=1:raise ValueError('inference requires exactly one logical file per bin')
            b['logical_size_bytes']=b['size_bytes'];b['size_bytes']//=2;b['files']=2
            b['fragments']=[dict(file_index=i,offset_bytes=i*b['size_bytes'],length_bytes=b['size_bytes']) for i in range(2)]
        fragmentation=dict(logical_files=len(bins),physical_files=2*len(bins),
                           scope='Zipf ranks original logical files; each bin contains two equal fragments of one logical file',
                           mapping='source_members lists logical identity once; fragments maps physical file indices to logical byte ranges; synthetic content',
                           limitation='physical file sizes and sequential span differ from SES template; no measured concurrency guarantee')
    return dict(id=source['id'],bins=bins,profiles=profiles,provenance=deepcopy(source['provenance']),
                capacity_adaptation=capacity_adaptation,fragmentation=fragmentation,phase_zipf=dict(alpha=ALPHA,seed=SEED,scope='fixed ranks within business groups; preserve per-phase business group mass',
                                max_bins=budget,max_fwd_per_rd=256,phases=audits,
                                source_members='[original bin, zero-based original file index, rank within business group]; physical order unless fragmentation is present, then logical identity with fragments mapping',
                                baseline='same business phases and layout with uniform selection within each group',
                                ai_extension='SES PERF single-RD read adaptation; conditional Zipf within size classes; no added business lifecycle',
                                coverage='timed file requests, not complete scans; no guarantee of completed epoch, validation, checkpoint or inference',
                                default_rate='max',read_only=True,tv_limit=tv_limit,
                                acceptance_per_case={'accuracy':.90,'precision':.85,'recall':.85},measured_acceptance=None))
