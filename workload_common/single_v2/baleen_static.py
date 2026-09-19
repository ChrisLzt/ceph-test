"""Full-population native-frequency snapshot, not temporal trace replay."""
from bisect import bisect_left
from collections import defaultdict
from copy import deepcopy
import heapq
from . import baleen


def build():
    source=baleen.build();keys=source['source_keys']
    counts=[sum(k[3]) for k in keys];total=sum(counts)
    by_size=defaultdict(list);origin={};histograms=defaultdict(lambda:defaultdict(float))
    old_counts={}
    for b in source['bins']:
        old_counts[b['id']]=sum(counts[i] for i in b['source_key_indices'])
        for i in b['source_key_indices']:
            by_size[b['size_bytes']].append(i);origin[i]=b['id']
    for phase in source['profiles']['baseline']:
        for lane in phase['lanes']:
            for xfer,n in lane['xfersize']:histograms[lane['bin']][xfer]+=n
    arrays={}
    for size,indices in by_size.items():
        indices.sort(key=lambda i:(-counts[i],i))
        values=[counts[i] for i in indices];prefix=[0]
        for value in values:prefix.append(prefix[-1]+value)
        arrays[size]=(indices,prefix,[-v for v in values])
    def error(size,a,b):
        _,p,neg=arrays[size];mean=(p[b]-p[a])/(b-a)
        k=bisect_left(neg,-mean,a,b)
        return max(0.,p[k]-p[a]-(k-a)*mean)
    parts=set();queue=[]
    def add(size,a,b):
        parts.add((size,a,b))
        if b-a<2:return
        current=error(size,a,b)
        gain,k=max((current-error(size,a,k)-error(size,k,b),k) for k in range(a+1,b))
        if gain>1e-10:heapq.heappush(queue,(-gain,size,a,b,k))
    for size,indices in by_size.items():add(size,0,len(indices))
    while len(parts)<255 and queue:
        _,size,a,b,k=heapq.heappop(queue);parts.remove((size,a,b));add(size,a,k);add(size,k,b)
    bins=[];lanes=[];tv=0.
    for number,(size,a,b) in enumerate(sorted(parts)):
        indices=arrays[size][0][a:b];weight=sum(counts[i] for i in indices)
        contributions=defaultdict(int);hist=defaultdict(float)
        for i in indices:contributions[origin[i]]+=counts[i]
        for old,n in contributions.items():
            for xfer,value in histograms[old].items():hist[xfer]+=value*n/old_counts[old]
        name=f'native_{number:03d}'
        bins.append(dict(id=name,files=len(indices),size_bytes=size,group=f'size_{size}',source_key_indices=indices))
        lanes.append(dict(bin=name,weight=weight,xfersize=sorted(map(list,hist.items())),fileio='random',fileselect='random',threads=1))
        tv+=error(size,a,b)/total
    if tv>.01:raise ValueError('native per-key probability TV exceeds 1%')
    provenance=deepcopy(source['provenance'])
    provenance.update(adaptation='single 600s native-frequency snapshot; all GET+PUT become reads',
                      histogram_adaptation='old-bin all-window histograms distributed by member operation mass; full global histogram preserved, per-key xfer correlation approximated',
                      timeline='original temporal order removed; no window gating; no Zipf imposed')
    return dict(id=source['id'],bins=bins,profiles={'baseline':[dict(name='native_all',seconds=600,rate_multiplier=1,lanes=lanes)]},
                provenance=provenance,static_native=dict(source_key_count=len(keys),source_operations=total,
                native_tv=tv,top_key_operations=max(counts),top_key_share=max(counts)/total,
                max_fwd_per_rd=256,default_rate='max',read_only=True,
                coverage='configured request shares, not measured file/object heat; no stopafter and no temporal replay'))
