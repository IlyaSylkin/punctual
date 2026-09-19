"""Вопросы 1,3,4,5,16,17 по фиду позиций HSL."""
import os, sys, collections, statistics, glob, os
from reader import snapshots

HOURS = ["20260914-13","20260914-14","20260914-15","20260914-16","20260914-17"]
ROOT = os.environ.get("CAPTURE_DIR", "./capture")

last = {}                       # vehicle -> (ts, lat, lon)
periods = collections.Counter() # дельты vehicle.timestamp
total_records = 0; new_records = 0
stationary = moved = 0
routes = set(); vehicles = set(); stops = set(); trips = set()
snaps = 0
for hts, m in snapshots("hsl-positions", hours=HOURS, root=ROOT):
    snaps += 1
    for e in m.entity:
        if not e.HasField("vehicle"): continue
        v = e.vehicle; total_records += 1
        vid = v.vehicle.id
        vehicles.add(vid); routes.add(v.trip.route_id)
        if v.stop_id: stops.add(v.stop_id)
        trips.add((v.trip.route_id, v.trip.direction_id, v.trip.start_date, v.trip.start_time))
        prev = last.get(vid)
        if prev and prev[0] == v.timestamp:
            continue                      # тот же рапорт машины — дубликат
        new_records += 1
        if prev:
            d = v.timestamp - prev[0]
            if 0 < d < 300: periods[d] += 1
            if abs(v.position.latitude - prev[1]) < 1e-6 and abs(v.position.longitude - prev[2]) < 1e-6:
                stationary += 1
            else:
                moved += 1
        last[vid] = (v.timestamp, v.position.latitude, v.position.longitude)

print(f"снимков: {snaps}, записей всего: {total_records}")
print(f"\n### Q3 дедупликация по (vehicle_id, vehicle.timestamp)")
print(f"  уникальных рапортов: {new_records} ({100*new_records/total_records:.1f}%)")
print(f"  дубликатов отброшено: {total_records-new_records} ({100*(total_records-new_records)/total_records:.1f}%)")

print(f"\n### Q1 период обновления машины (дельта vehicle.timestamp)")
tot = sum(periods.values())
acc = 0
for d in sorted(periods):
    acc += periods[d]
    if d <= 5 or d in (10,15,20,30,60) or acc/tot > 0.99: pass
common = periods.most_common(8)
print(f"  частые дельты, с: {[(d,f'{100*c/tot:.0f}%') for d,c in common]}")
ds = sorted(periods.elements())
print(f"  медиана {statistics.median(ds):.0f} с, p90 {ds[int(.9*len(ds))]} с, p99 {ds[int(.99*len(ds))]} с")

print(f"\n### Q4 машина обновила время, но не сдвинулась")
print(f"  стояла: {stationary} ({100*stationary/(stationary+moved):.1f}%)")
print(f"  ехала:  {moved} ({100*moved/(stationary+moved):.1f}%)")

print(f"\n### Q16 кардинальности за 3.5 ч")
print(f"  машин {len(vehicles)}, маршрутов {len(routes)}, рейсов {len(trips)}, остановок {len(stops)}")

print(f"\n### Q5/Q17 объём")
gz = sum(os.path.getsize(f) for f in glob.glob(f"{ROOT}/hsl-positions/*.bin.gz"))
print(f"  архивы на диске: {gz/1e6:.0f} МБ на {snaps} снимков")
print(f"  уникальных рапортов за 3.5 ч: {new_records} → {new_records/3.5:.0f}/ч → "
      f"{new_records/3.5*24*30/1e6:.0f} млн/мес")
