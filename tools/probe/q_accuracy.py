"""Вопросы 13,14,15 по фиду прогнозов HSL. Два прохода: факты, затем прогнозы."""
import sys, collections, statistics
sys.path.insert(0, "/mnt/data/learning/capture")
from reader import snapshots, trip_key

HOURS = ["20260914-13","20260914-14","20260914-15","20260914-16","20260914-17"]
ROOT = "/mnt/data/learning/capture/broken"

# --- проход 1: устоявшийся факт по каждой паре (рейс, остановка) ---
fact = {}
for hts, m in snapshots("hsl-tripupdates", hours=HOURS, root=ROOT):
    for e in m.entity:
        if not e.HasField("trip_update"): continue
        tu = e.trip_update; k0 = trip_key(tu.trip)
        for s in tu.stop_time_update:
            a = s.arrival
            if s.HasField("arrival") and a.time and a.HasField("uncertainty") and a.uncertainty == 0:
                fact[k0 + (s.stop_id,)] = a.time     # последнее увиденное = устоявшееся
print(f"проход 1: фактов {len(fact)}", flush=True)

# --- проход 2: прогнозы ---
BUCKETS = [(0,180,"0–3 мин",30,90), (180,360,"3–6 мин",60,150),
           (360,600,"6–10 мин",60,210), (600,900,"10–15 мин",90,270),
           (900,1800,"15–30 мин",None,None), (1800,10**9,"30+ мин",None,None)]
def bucket(h):
    for lo,hi,name,e,l in BUCKETS:
        if lo <= h < hi: return name,e,l
    return None,None,None

err = collections.defaultdict(list)
hit = collections.Counter(); tot = collections.Counter()
early_cnt = collections.Counter()
horizons_sec = []; stops_ahead = []
prev_pred = {}                      # ключ -> (t, предсказанное) для дрейфа
drift = collections.defaultdict(list)
for hts, m in snapshots("hsl-tripupdates", hours=HOURS, root=ROOT):
    for e in m.entity:
        if not e.HasField("trip_update"): continue
        tu = e.trip_update; k0 = trip_key(tu.trip)
        ahead = 0
        for s in tu.stop_time_update:
            a = s.arrival
            if not (s.HasField("arrival") and a.time): continue
            if a.HasField("uncertainty") and a.uncertainty == 0: continue   # это факт, не прогноз
            ahead += 1
            horizons_sec.append(a.time - hts)
            k = k0 + (s.stop_id,)
            f = fact.get(k)
            if f is None: continue
            h = f - hts                       # время до ФАКТИЧЕСКОГО прибытия
            if h <= 0: continue
            name, etol, ltol = bucket(h)
            if not name: continue
            d = a.time - f                    # >0: обещали позже, автобус пришёл раньше
            err[name].append(abs(d))
            tot[name] += 1
            if d > 0: early_cnt[name] += 1
            if etol is not None:
                ok = (d <= etol) if d > 0 else (-d <= ltol)
                hit[name] += ok
            p = prev_pred.get(k)
            if p and p[0] != hts:
                drift[name].append(abs(a.time - p[1]))
            prev_pred[k] = (hts, a.time)
        if ahead: stops_ahead.append(ahead)

print(f"\n### Q13 горизонт прогноза")
hs = sorted(horizons_sec)
print(f"  до прибытия, мин: медиана {statistics.median(hs)/60:.0f}, "
      f"p90 {hs[int(.9*len(hs))]/60:.0f}, макс {max(hs)/60:.0f}")
sa = sorted(stops_ahead)
print(f"  остановок впереди: медиана {statistics.median(sa):.0f}, p90 {sa[int(.9*len(sa))]}, макс {max(sa)}")

print(f"\n### Q15 ТОЧНОСТЬ ОФИЦИАЛЬНОГО ПРОГНОЗА HSL")
print(f"  корзины по времени до фактического прибытия (методика TransitApp)")
print(f"\n  {'корзина':<12}{'n':>9}{'MAE, с':>9}{'p90, с':>9}{'в допуске':>11}{'пришёл раньше':>15}")
for lo,hi,name,etol,ltol in BUCKETS:
    v = err.get(name)
    if not v: continue
    vs = sorted(v)
    acc = f"{100*hit[name]/tot[name]:.1f}%" if etol is not None else "—"
    print(f"  {name:<12}{len(v):>9}{statistics.mean(v):>9.0f}{vs[int(.9*len(vs))]:>9.0f}"
          f"{acc:>11}{100*early_cnt[name]/tot[name]:>14.0f}%")
tr = [n for _,_,n,e,_ in BUCKETS if e is not None]
if all(tot[n] for n in tr):
    overall = statistics.mean(100*hit[n]/tot[n] for n in tr)
    print(f"\n  итог по методике TransitApp (среднее 4 корзин): {overall:.1f}%")

print(f"\n### Q14 дрейф прогноза между соседними снимками")
print(f"  {'корзина':<12}{'n':>9}{'медиана':>9}{'p90':>8}{'макс':>8}")
for lo,hi,name,_,_ in BUCKETS:
    v = drift.get(name)
    if not v: continue
    vs = sorted(v)
    print(f"  {name:<12}{len(v):>9}{statistics.median(vs):>9.0f}{vs[int(.9*len(vs))]:>8}{max(vs):>8}")
