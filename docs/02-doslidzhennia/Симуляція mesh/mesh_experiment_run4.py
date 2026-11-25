"""Original offline Monte Carlo experiment; no downloaded code or network.

Exploratory model only, not a Meshtastic emulator or radio measurement.
Each run samples a connected geometric topology and independent message times.
Flooded packets use hop limit, deduplication, random relay backoff, half-duplex,
single-channel destructive overlap, and a rolling one-hour TX duty ledger.
No capture, interference immunity, CAD, ACK, retransmission, fading or encryption.
All model assumptions are recorded beside results. CPU effort is logged.
"""
import csv, datetime, heapq, itertools, json, math, random, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEST = ROOT / 'audit_run4' / 'simulation'
DEST.mkdir(parents=True,exist_ok=True)
START = time.monotonic()
CPU_START = time.process_time()
DEADLINE = datetime.datetime.fromisoformat('2026-11-09T15:00:00+00:00').timestamp()

def toa(sf, payload, bw=125000, cr=1, preamble=8):
    de = int((2**sf / bw) >= .016)
    symbols = 8 + max(math.ceil((8*payload-4*sf+28+16)/(4*(sf-2*de)))*(cr+4),0)
    return (preamble+4.25+symbols)*2**sf/bw

def trial(seed, n, sf, interval, hops, duty, backoff, shape):
    rng = random.Random(seed)
    # A 1-D corridor and a 2-D campus provide different relay redundancy.
    points = [(rng.random()*4, rng.random()*(.3 if shape=='corridor' else 2)) for _ in range(n)]
    adj = [[j for j in range(n) if j!=i and math.dist(points[i],points[j])<1.3] for i in range(n)]
    duration = 3600.
    airtime=toa(sf,64)
    events=[]; seq=itertools.count(); origins={}; ledger=[[] for _ in range(n)]
    total_tx=blocked=0; collisions=0; delivered=0; expected=0; delays=[]
    seen=[set() for _ in range(n)]; active={}; receiving={}; heard={}
    def push(t, kind, value): heapq.heappush(events,(t,next(seq),kind,value))
    for node in range(n):
        t=rng.expovariate(1/interval)
        while t<duration:
            mid=len(origins); origins[mid]=(node,t); heard[mid]={node}
            # Measure delivery to all nodes reachable within the hop budget.
            reachable={node}; frontier={node}
            for _ in range(hops+1):
                frontier={j for i in frontier for j in adj[i]}-reachable; reachable|=frontier
            expected+=len(reachable)-1
            push(t,'tx',(node,mid,0)); t+=rng.expovariate(1/interval)
    txid=itertools.count()
    while events:
        t,_,kind,v=heapq.heappop(events)
        if t>duration+60: break
        if kind=='tx':
            node,mid,hop=v
            if (mid in seen[node] and hop>0): continue
            seen[node].add(mid)
            txlist=ledger[node]
            while txlist and txlist[0][0]<t-3600: txlist.pop(0)
            if sum(x[1] for x in txlist)+airtime>duty*3600 or node in active:
                blocked+=1; continue
            txlist.append((t,airtime)); total_tx+=1
            ident=next(txid); active[node]=ident
            outcomes={j:True for j in adj[node]}
            for j in adj[node]:
                if j in active: outcomes[j]=False
                for old in receiving.get(j,[]):
                    old[0][j]=False; outcomes[j]=False
                receiving.setdefault(j,[]).append((outcomes,ident))
            # Starting a TX destroys this node's ongoing receptions.
            for old in receiving.get(node,[]): old[0][node]=False
            push(t+airtime,'end',(node,mid,hop,ident,outcomes))
        else:
            node,mid,hop,ident,outcomes=v
            if active.get(node)==ident: del active[node]
            for j,success in outcomes.items():
                receiving[j]=[x for x in receiving[j] if x[1]!=ident]
                if not success: collisions+=1; continue
                if j not in heard[mid]:
                    heard[mid].add(j); delivered+=1; delays.append(t-origins[mid][1])
                if hop<hops and mid not in seen[j]:
                    push(t+rng.uniform(airtime,airtime+backoff),'tx',(j,mid,hop+1))
    delays.sort()
    return [seed,n,sf,interval,hops,duty,backoff,shape,len(origins),expected,delivered,
            total_tx,blocked,collisions,delivered/expected if expected else 0,
            delays[len(delays)//2] if delays else 0,delays[int(.95*(len(delays)-1))] if delays else 0]

def main():
    settings=list(itertools.product([5,10,20,40],[7,9,12],[30,120,600],[1,3],[.01,.1],[1,5],['corridor','campus']))
    columns=['seed','nodes','sf','mean_interval_s','relay_limit','duty_fraction','backoff_s','geometry',
             'generated','reachable_destinations','delivered_destinations','tx','blocked','failed_receptions',
             'delivery_fraction','latency_median_s','latency_p95_s']
    metadata={'kind':'original synthetic simulation, not measurement','payload_bytes':64,'bandwidth_hz':125000,
              'coding_rate':'4/5','preamble_symbols':8,'packet_crc':True,'header':'explicit',
              'assumptions':__doc__,'settings':len(settings),'seed_origin':202611090000,
              'replications_per_setting':48,'planned_trials':len(settings)*48,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (DEST/'metadata.json').write_text(json.dumps(metadata,indent=2))
    count=0; last=START
    with (DEST/'trials.csv').open('w',newline='') as f:
        w=csv.writer(f); w.writerow(columns)
        while count < len(settings)*48:
            s=settings[count%len(settings)]; row=trial(202611090000+count,*s); w.writerow(row); count+=1
            now=time.monotonic()
            if now-last>45:
                f.flush(); last=now
                status={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'trials':count,
                        'wall_seconds':now-START,'cpu_seconds':time.process_time()-CPU_START,
                        'latest_setting':s,'latest_delivery_fraction':row[-3]}
                (DEST/'status.json').write_text(json.dumps(status,indent=2))
                print('SIMULATION_PROGRESS '+json.dumps(status),flush=True)
    metadata.update({'complete_factorial_design':True,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     'trials':count,'wall_seconds':time.monotonic()-START,'cpu_seconds':time.process_time()-CPU_START})
    (DEST/'metadata.json').write_text(json.dumps(metadata,indent=2))
    print('SIMULATION_FINISHED '+json.dumps(metadata),flush=True)

if __name__=='__main__': main()
