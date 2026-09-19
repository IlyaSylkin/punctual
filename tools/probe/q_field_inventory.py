"""Заполненность полей по обоим фидам. Считается по захваченным архивам."""
import sys, collections
sys.path.insert(0, "/mnt/data/learning/capture")
from reader import snapshots

ROOT = "/mnt/data/learning/capture/broken"
HOURS = ["20260914-14", "20260914-15"]

def walk(msg, prefix, cnt):
    for fd, val in msg.ListFields():
        path = f"{prefix}.{fd.name}" if prefix else fd.name
        single = hasattr(val, "ListFields")
        repeated = (not single and not isinstance(val, (str, bytes, int, float, bool))
                    and hasattr(val, "__len__"))
        if single:
            cnt[path] += 1; walk(val, path, cnt)
        elif repeated:
            cnt[path] += len(val)
            for v in val:
                if hasattr(v, "ListFields"): walk(v, path, cnt)
        else:
            cnt[path] += 1

for feed, root_field in (("hsl-positions", "vehicle"), ("mbta-positions", "vehicle"),
                         ("hsl-tripupdates", "trip_update"), ("mbta-tripupdates", "trip_update")):
    cnt = collections.Counter(); n = 0; snaps = 0
    for _, m in snapshots(feed, hours=HOURS, step=40, root=ROOT):
        snaps += 1
        for e in m.entity:
            if not e.HasField(root_field): continue
            n += 1
            walk(getattr(e, root_field), "", cnt)
    if not n:
        print(f"\n=== {feed}: нет данных"); continue
    base_stu = cnt.get("stop_time_update", n)
    print(f"\n=== {feed}: снимков {snaps}, записей {n}"
          + (f", stop_time_update {cnt.get('stop_time_update', 0)}" if root_field == "trip_update" else ""))
    for path, c in sorted(cnt.items()):
        d = base_stu if path.startswith("stop_time_update.") else n
        print(f"   {path:<44} {100*c/d:5.1f}%")
