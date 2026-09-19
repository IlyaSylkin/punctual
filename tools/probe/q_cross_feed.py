"""Q8 связь фидов, Q11 расхождение определений прибытия, Q12 переход NO_DATA."""
import sys, collections, statistics
sys.path.insert(0, "/mnt/data/learning/capture")
from reader import snapshots, trip_key

HOURS = ["20260914-13","20260914-14","20260914-15","20260914-16","20260914-17"]
ROOT = "/mnt/data/learning/capture/broken"
STATUS = {0:"INCOMING_AT", 1:"STOPPED_AT", 2:"IN_TRANSIT_TO"}

# --- проход по фиду прогнозов ---
fact = {}                                  # (рейс, остановка) -> устоявшийся факт
tu_trips_by_snap = collections.defaultdict(set)
had_pred = set(); had_nodata = set()
first_nodata = {}; first_pred = {}
for hts, m in snapshots("hsl-tripupdates", hours=HOURS, root=ROOT):
    for e in m.entity:
        if not e.HasField("trip_update"): continue
        tu = e.trip_update; k0 = trip_key(tu.trip)
        tu_trips_by_snap[hts].add(k0)
        has = any(s.HasField("arrival") and s.arrival.time for s in tu.stop_time_update)
        if has:
            had_pred.add(k0); first_pred.setdefault(k0, hts)
        else:
            had_nodata.add(k0); first_nodata.setdefault(k0, hts)
        for s in tu.stop_time_update:
            a = s.arrival
            if s.HasField("arrival") and a.time and a.HasField("uncertainty") and a.uncertainty == 0:
                fact[k0 + (s.stop_id,)] = a.time
print(f"проход 1: фактов {len(fact)}, рейсов с прогнозом {len(had_pred)}, "
      f"рейсов с NO_DATA {len(had_nodata)}", flush=True)

# --- проход по фиду позиций ---
stopped_at = {}                            # (рейс, остановка) -> первое время STOPPED_AT
pos_trips_by_snap = collections.defaultdict(set)
pos_trips = set()
for hts, m in snapshots("hsl-positions", hours=HOURS, root=ROOT):
    for e in m.entity:
        if not e.HasField("vehicle"): continue
        v = e.vehicle; k0 = trip_key(v.trip)
        pos_trips_by_snap[hts].add(k0); pos_trips.add(k0)
        if v.HasField("current_status") and v.current_status == 1 and v.stop_id:
            k = k0 + (v.stop_id,)
            if k not in stopped_at or v.timestamp < stopped_at[k]:
                stopped_at[k] = v.timestamp
print(f"проход 2: пар STOPPED_AT {len(stopped_at)}, рейсов в позициях {len(pos_trips)}", flush=True)

print(f"\n### Q8 связь рейсов между фидами (ключ route+direction+start_date+start_time)")
tu_all = had_pred | had_nodata
both = pos_trips & tu_all
print(f"  рейсов в позициях {len(pos_trips)}, в прогнозах {len(tu_all)}, в обоих {len(both)}")
print(f"  доля рейсов позиций, найденных в прогнозах: {100*len(both)/max(len(pos_trips),1):.1f}%")
only_pos = pos_trips - tu_all; only_tu = tu_all - pos_trips
print(f"  только в позициях {len(only_pos)}, только в прогнозах {len(only_tu)}")

print(f"\n### Q11 расхождение: факт из прогнозов vs STOPPED_AT из позиций")
common = set(fact) & set(stopped_at)
print(f"  пар с обоими определениями: {len(common)} "
      f"(факты {len(fact)}, STOPPED_AT {len(stopped_at)})")
if common:
    d = sorted(stopped_at[k] - fact[k] for k in common)
    print(f"  STOPPED_AT минус факт, с: медиана {statistics.median(d):+.0f}, "
          f"p10 {d[int(.1*len(d))]:+}, p25 {d[int(.25*len(d))]:+}, "
          f"p75 {d[int(.75*len(d))]:+}, p90 {d[int(.9*len(d))]:+}")
    ad = sorted(abs(x) for x in d)
    print(f"  |расхождение|: медиана {statistics.median(ad):.0f} с, p90 {ad[int(.9*len(ad))]} с")
    print(f"  доля с расхождением до 5 с: {100*sum(1 for x in ad if x<=5)/len(ad):.0f}%, "
          f"до 15 с: {100*sum(1 for x in ad if x<=15)/len(ad):.0f}%, "
          f"до 30 с: {100*sum(1 for x in ad if x<=30)/len(ad):.0f}%")

print(f"\n### Q12 переход NO_DATA → прогноз")
trans = [k for k in had_nodata if k in had_pred and first_nodata[k] < first_pred.get(k, 1<<62)]
never = [k for k in had_nodata if k not in had_pred]
print(f"  рейсов, побывавших в NO_DATA: {len(had_nodata)}")
print(f"    из них получили прогноз позже: {len(trans)} ({100*len(trans)/max(len(had_nodata),1):.1f}%)")
print(f"    так и остались без прогноза:   {len(never)} ({100*len(never)/max(len(had_nodata),1):.1f}%)")
if trans:
    lag = sorted(first_pred[k] - first_nodata[k] for k in trans)
    print(f"  через сколько появился прогноз, мин: медиана {statistics.median(lag)/60:.0f}, "
          f"p10 {lag[int(.1*len(lag))]/60:.0f}, p90 {lag[int(.9*len(lag))]/60:.0f}")
