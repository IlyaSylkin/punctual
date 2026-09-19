"""Сколько раз реально меняется прогноз за жизнь пары (рейс, остановка)."""
import os, sys, collections, statistics
from reader import snapshots, trip_key

HOURS = ["20260914-14","20260914-15","20260914-16"]
ROOT = os.environ.get("CAPTURE_DIR", "./capture")

seen = collections.defaultdict(lambda: [0, None, 0])   # ключ -> [наблюдений, послед.значение, изменений]
snaps = 0
for hts, m in snapshots("hsl-tripupdates", hours=HOURS, root=ROOT):
    snaps += 1
    for e in m.entity:
        if not e.HasField("trip_update"): continue
        tu = e.trip_update; k0 = trip_key(tu.trip)
        for s in tu.stop_time_update:
            a = s.arrival
            if not (s.HasField("arrival") and a.time): continue
            if a.HasField("uncertainty") and a.uncertainty == 0: continue   # факт, не прогноз
            st = seen[k0 + (s.stop_id,)]
            st[0] += 1
            if st[1] is not None and a.time != st[1]: st[2] += 1
            st[1] = a.time

obs = [v[0] for v in seen.values()]
chg = [v[2] for v in seen.values()]
rows_state = sum(obs)                    # если хранить состояние на каждый снимок
rows_delta = sum(1 + c for c in chg)     # если хранить только изменения (+1 на появление)

print(f"снимков: {snaps}, пар (рейс, остановка): {len(seen)}\n")
o = sorted(obs); c = sorted(chg)
print(f"наблюдений на пару:  медиана {statistics.median(o):.0f}, p90 {o[int(.9*len(o))]}, макс {max(o)}")
print(f"ИЗМЕНЕНИЙ на пару:   медиана {statistics.median(c):.0f}, среднее {statistics.mean(c):.1f}, "
      f"p90 {c[int(.9*len(c))]}, макс {max(c)}")
print(f"\nраспределение числа изменений:")
d = collections.Counter(min(x, 10) for x in c)
for k in sorted(d):
    label = f"{k}" if k < 10 else "10+"
    print(f"   {label:>3} изменений: {d[k]:>6} пар ({100*d[k]/len(c):.1f}%)")
print(f"\nстрок при хранении состояния:  {rows_state:>10,}")
print(f"строк при хранении изменений:  {rows_delta:>10,}   выигрыш {rows_state/rows_delta:.1f}x")
print(f"\nстрок на пару: состояние {rows_state/len(seen):.1f}, изменения {rows_delta/len(seen):.1f}")
