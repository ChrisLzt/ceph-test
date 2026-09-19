"""Global file-level Zipf; no extra files, hot pool, or object-prefix selection.

One global rank per original file. Adjacent probability bands are grouped only
within compatible domain/size groups. FWD chooses a bin by its total mass and
then chooses one file uniformly; the resulting approximation is audited.
"""
from collections import defaultdict
from copy import deepcopy
import hashlib
import math

ALPHA = .99
RANK_SEED = 'single-file-zipf-v1'
MAX_BINS = 256
MAX_TV = .02


def transform(source, case):
    lookup={b['id']:b for b in source['bins']}
    files=[]
    for b in source['bins']:
        for index in range(b['files']):
            identity=f'{RANK_SEED}/{case}/{b["id"]}/{index}'
            files.append((hashlib.sha256(identity.encode()).hexdigest(),b['id'],index))
    files.sort()
    n=len(files)
    probability=[r**-ALPHA for r in range(1,n+1)]
    normalizer=math.fsum(probability)
    probability=[p/normalizer for p in probability]

    def partition(width):
        groups=defaultdict(list)
        for rank,(_,original,index) in enumerate(files,1):
            b=lookup[original]
            band=rank if rank<=32 else 33+int(math.log(rank/33)/math.log1p(width))
            groups[(b['group'],b['size_bytes'],band)].append([original,index,rank])
        return groups

    width=.01
    groups=partition(width)
    while len(groups)>MAX_BINS:
        width*=1.08
        groups=partition(width)
        if width>100:
            raise ValueError('domain groups cannot fit the FWD budget')

    # Preserve transfer histograms conditional on original domain/size group.
    hist=defaultdict(lambda:defaultdict(float))
    for phase in source['profiles']['baseline']:
        lane_total=math.fsum(l['weight'] for l in phase['lanes'])
        for lane in phase['lanes']:
            b=lookup[lane['bin']]
            key=(b['group'],b['size_bytes'])
            pairs=lane['xfersize'] if isinstance(lane['xfersize'],list) else [[lane['xfersize'],1]]
            pair_total=math.fsum(w for _,w in pairs)
            scale=phase['seconds']*phase.get('rate_multiplier',1)*lane['weight']/lane_total
            for size,weight in pairs:
                hist[key][size]+=scale*weight/pair_total

    bins=[]; masses={}; tv=0
    for i,(key,members) in enumerate(sorted(groups.items())):
        group,size_bytes,_=key
        name=f'filezipf_{i:03d}'
        mass=math.fsum(probability[m[2]-1] for m in members)
        per_file=mass/len(members)
        tv+=.5*math.fsum(abs(per_file-probability[m[2]-1]) for m in members)
        bins.append(dict(id=name,files=len(members),size_bytes=size_bytes,group=group,
                         source_members=members))
        masses[name]=mass
    if tv>MAX_TV:
        raise ValueError(f'file Zipf approximation TV exceeds 2%: {tv}')

    # A singleton rank must have only one concurrent FWD. Inference's 60:40
    # sequential/random mix is expressed in time, with all files in both RDs.
    modes=([('sequential',360),('random',240)] if case=='ai_inference' else
           [('random' if case=='baleen' else 'sequential',600)])
    profiles={}
    for profile in ('baseline','file_zipf099'):
        phases=[]
        for mode,seconds in modes:
            lanes=[]
            for b in bins:
                histogram=hist[(b['group'],b['size_bytes'])]
                pairs=sorted(histogram.items())
                xfer=pairs[0][0] if len(pairs)==1 else [[size,weight] for size,weight in pairs]
                lanes.append(dict(bin=b['id'],weight=(masses[b['id']] if profile=='file_zipf099' else b['files']/n),
                                  xfersize=xfer,fileio=mode,fileselect='random',threads=1,stopafter=1))
            phases.append(dict(name=mode,seconds=seconds,rate_multiplier=1,lanes=lanes))
        profiles[profile]=phases
    top_mass={}
    for fraction in (.01,.10,.20):
        count=max(1,math.ceil(n*fraction))
        ideal=math.fsum(probability[:count])
        achieved=math.fsum(masses[b['id']]/b['files']*sum(m[2]<=count for m in b['source_members']) for b in bins)
        top_mass[str(fraction)]={'files':count,'ideal':ideal,'bin_approximation':achieved}
    return dict(id=source['id'],bins=bins,profiles=profiles,
                provenance=deepcopy(source['provenance']),
                file_zipf=dict(alpha=ALPHA,scope='all files in this case; one global normalizer',
                               rank_seed=RANK_SEED,rank_method='SHA256(seed/case/original_bin/file_index), ascending',
                               band_width=width,tv_distance=tv,top_mass=top_mass,
                               file_count=n,bin_count=len(bins),max_fwd_per_rd=MAX_BINS,
                               tv_limit=MAX_TV,hot_pool=False,
                               baseline='uniform-file comparison on the same new layout, NOT the original application baseline',
                               source_identity='source_members entry = [original bin, zero-based file index, global rank]; list order is new file index',
                               semantics='one I/O per file selection; sequential offsets retain Vdbench behavior, no prefix/extent pinning; no source phase eligibility restrictions',
                               acceptance_per_case={'accuracy':.90,'precision':.85,'recall':.85},
                               measured_acceptance=None),
                limitations=['Global file selection changes source timing, class request mass and active-file restrictions.',
                             'Grouped ranks are uniform inside a bin; TV is analytical request probability error, not measured accuracy.',
                             'No guaranteed hot object proportion or metric outcome; retain unchanged HP labels.',
                             'Inference sequential/random proportions are time-separated; global transfer histogram is preserved within each size group.'])
