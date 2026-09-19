"""Q2 и Q10: объём и скорость появления фактов по часам суток.

Нормирует на долю успешных опросов в часе: дыры в захвате не должны
выглядеть как спад активности транспорта.
"""
import sys, json, glob, os, collections, datetime as dt
sys.path.insert(0, "/mnt/data/learning/capture")
from reader import snapshots, trip_key

ROOT = "/mnt/data/learning/capture"
RUN = "20260916-193311-16018"
POLL = 10.0

def coverage():
    """доля успешных опросов в каждом часе, по журналу метаданных"""
    cov = {}
    for feed in ("hsl-positions", "hsl-tripupdates"):
        ok = collections.Counter(); all_ = collections.Counter()
        for l in open(f"{ROOT}/meta/{feed}__{RUN}.jsonl"):
            r = json.loads(l)
            h = dt.datetime.fromtimestamp(r["t"]).hour
            all_[h] += 1
            if r.get("http") == 200 and "err" not in r: ok[h] += 1
        cov[feed] = {h: ok[h] / (3600 / POLL) for h in range(24)}
    return cov

cov = coverage()
hours = [f"20260916-{h:02d}" for h in range(16, 24)] + [f"20260917-{h:02d}" for h in range(0, 18)]

# --- позиции: уникальные рапорты по часам ---
pos = collections.defaultdict(set)
for hts, m in snapshots("hsl-positions", hours=hours, root=ROOT):
    h = dt.datetime.fromtimestamp(hts).hour
    for e in m.entity:
        if e.HasField("vehicle"):
            pos[h].add((e.vehicle.vehicle.id, e.vehicle.timestamp))
print("позиции разобраны", flush=True)

# --- факты прибытия: новые записи uncertainty=0 по часам ---
seen = set(); facts = collections.Counter(); changes = collections.Counter()
last_pred = {}
for hts, m in snapshots("hsl-tripupdates", hours=hours, step=2, root=ROOT):
    h = dt.datetime.fromtimestamp(hts).hour
    for e in m.entity:
        if not e.HasField("trip_update"): continue
        tu = e.trip_update; k0 = trip_key(tu.trip)
        for s in tu.stop_time_update:
            a = s.arrival
            if not (s.HasField("arrival") and a.time): continue
            k = k0 + (s.stop_id,)
            if a.HasField("uncertainty") and a.uncertainty == 0:
                if k not in seen: seen.add(k); facts[h] += 1
            else:
                p = last_pred.get(k)
                if p is not None and p != a.time: changes[h] += 1
                last_pred[k] = a.time

print(f"\n{'час':>4}{'покрытие':>10}{'рапортов':>11}{'норм./ч':>10}{'фактов':>9}{'норм./ч':>9}{'фактов/с':>10}{'правок/ч':>10}")
tot_pos = tot_fact = 0
for h in range(24):
    cp = cov["hsl-positions"].get(h, 0); ct = cov["hsl-tripupdates"].get(h, 0)
    if cp < 0.79: continue    # часы с дырами отбрасываем целиком
    n = len(pos.get(h, ()))
    np_ = n / cp
    # факты НЕ нормируются: запись остаётся в фиде до конца рейса и видна
    # в десятках снимков, поэтому при неполном покрытии теряется мало
    f = facts[h]; nf = f
    tot_pos += np_; tot_fact += nf
    print(f"{h:>4}{cp:>9.0%}{n:>11}{np_:>10.0f}{f:>9}{nf:>9.0f}{nf/3600:>10.1f}{changes[h]/max(ct,0.01):>10.0f}")
n_h = sum(1 for h in range(24) if cov["hsl-positions"].get(h, 0) >= 0.79)
print(f"\nчасов с покрытием ≥79%: {n_h} из 24")
print(f"по ним: рапортов {tot_pos:,.0f}, фактов {tot_fact:,.0f}")
print(f"экстраполяция на сутки: рапортов {tot_pos/n_h*24:,.0f}, фактов {tot_fact/n_h*24:,.0f}")
print(f"в месяц: рапортов {tot_pos/n_h*24*30/1e6:.0f} млн, фактов {tot_fact/n_h*24*30/1e6:.0f} млн")
