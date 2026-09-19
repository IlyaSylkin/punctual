"""Q9 уточнённый: отделить правку факта от коллизии ключа на повторных остановках."""
import os, sys, collections, statistics
from reader import snapshots, trip_key

HOURS = ["20260914-13","20260914-14","20260914-15","20260914-16","20260914-17"]
ROOT = os.environ.get("CAPTURE_DIR", "./capture")

obs = collections.defaultdict(list)      # ключ с номером посещения -> [(t, arrival)]
multi_stop = set()                       # ключи, где остановка встречается в рейсе >1 раза
snaps = 0
for ts, m in snapshots("hsl-tripupdates", hours=HOURS, step=2, root=ROOT):
    snaps += 1
    for e in m.entity:
        if not e.HasField("trip_update"): continue
        tu = e.trip_update; k0 = trip_key(tu.trip)
        cnt = collections.Counter(s.stop_id for s in tu.stop_time_update)
        seen = collections.Counter()
        for s in tu.stop_time_update:
            occ = seen[s.stop_id]; seen[s.stop_id] += 1
            a = s.arrival
            if s.HasField("arrival") and a.time and a.HasField("uncertainty") and a.uncertainty == 0:
                k = k0 + (s.stop_id, occ)
                obs[k].append((ts, a.time))
                if cnt[s.stop_id] > 1: multi_stop.add(k)
    if snaps % 100 == 0:
        print(f"  снимков {snaps}, ключей {len(obs)}", file=sys.stderr, flush=True)

def report(keys, label):
    st = ch = single = 0; deltas = []; lag = []
    for k in keys:
        v = obs[k]
        if len(v) == 1: single += 1; continue
        vals = [a for _, a in v]
        if len(set(vals)) == 1: st += 1
        else:
            ch += 1; deltas.append(max(vals) - min(vals))
            t0 = v[0][0]
            for (t, a) in v[1:]:
                if a != v[0][1]: lag.append(t - t0); break
    multi = st + ch
    print(f"\n### {label}: ключей {len(keys)}, из них с ≥2 наблюдениями {multi}")
    if multi:
        print(f"    не менялись {st} ({100*st/multi:.2f}%), менялись {ch} ({100*ch/multi:.2f}%)")
    if deltas:
        d = sorted(deltas)
        print(f"    изменение, с: медиана {statistics.median(d):.0f}, p90 {d[int(.9*len(d))]}, макс {max(d)}")
    if lag:
        l = sorted(lag)
        print(f"    когда произошла правка после первой публикации, с: "
              f"медиана {statistics.median(l):.0f}, p90 {l[int(.9*len(l))]}, макс {max(l)}")

single_keys = [k for k in obs if k not in multi_stop]
print(f"\nснимков обработано: {snaps}, всего ключей: {len(obs)}")
report(single_keys, "остановка встречается в рейсе ОДИН раз")
report(list(multi_stop), "остановка встречается в рейсе НЕСКОЛЬКО раз")
