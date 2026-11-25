"""Зведення Monte Carlo симуляції mesh (trials.csv) -> таблиці для розділу 4."""
import csv, sys, statistics as st, json, math
from collections import defaultdict
path = sys.argv[1]
R = list(csv.DictReader(open(path)))
for r in R:
    for k in ("nodes","sf","mean_interval_s","relay_limit"): r[k]=int(r[k])
    for k in ("duty_fraction","backoff_s","delivery_fraction","latency_median_s","latency_p95_s"): r[k]=float(r[k])
    for k in ("tx","blocked","failed_receptions","generated"): r[k]=int(r[k])
def ci(xs):
    m=st.mean(xs); s=st.stdev(xs) if len(xs)>1 else 0; return m, 1.96*s/math.sqrt(len(xs))
def group(keys, flt=lambda r: True):
    g=defaultdict(list)
    for r in R:
        if flt(r): g[tuple(r[k] for k in keys)].append(r)
    return dict(sorted(g.items()))
out={"trials":len(R)}
def summ(rows):
    m,h=ci([r["delivery_fraction"] for r in rows])
    lat=[r["latency_median_s"] for r in rows if r["latency_median_s"]>0]
    p95=[r["latency_p95_s"] for r in rows if r["latency_p95_s"]>0]
    blk=sum(r["blocked"] for r in rows)/max(1,sum(r["blocked"]+r["tx"] for r in rows))
    return dict(n=len(rows),pdr=round(100*m,1),ci=round(100*h,1),lat50=round(st.median(lat),2) if lat else None,
                lat95=round(st.median(p95),2) if p95 else None,blocked=round(100*blk,1))
for name,keys in [("sf",["sf"]),("relay",["relay_limit"]),("nodes",["nodes"]),("interval",["mean_interval_s"]),
                  ("duty",["duty_fraction"]),("geometry",["geometry"]),("backoff",["backoff_s"]),
                  ("sf_relay",["sf","relay_limit"]),("nodes_interval",["nodes","mean_interval_s"]),
                  ("sf_duty",["sf","duty_fraction"])]:
    out[name]={"/".join(map(str,k)):summ(v) for k,v in group(keys).items()}
# найкращий і найгірший режим серед повної сітки
cells={k:summ(v) for k,v in group(["nodes","sf","mean_interval_s","relay_limit","duty_fraction","backoff_s","geometry"]).items()}
best=sorted(cells.items(),key=lambda kv:-kv[1]["pdr"])
out["best5"]=[("/".join(map(str,k)),v) for k,v in best[:5]]
out["worst5"]=[("/".join(map(str,k)),v) for k,v in best[-5:]]
out["cells_ge90"]=sum(1 for v in cells.values() if v["pdr"]>=90); out["cells"]=len(cells)
print(json.dumps(out,ensure_ascii=False,indent=1))
