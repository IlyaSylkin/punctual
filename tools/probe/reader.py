"""Чтение захваченных архивов с дедупликацией по header.timestamp."""
import gzip, struct, glob, os
from google.transit import gtfs_realtime_pb2 as pb

ROOT = os.environ.get("CAPTURE_DIR", "./capture")
import zlib

def snapshots(feed, hours=None, step=1, dedup=True, root=None):
    """Отдаёт (header_timestamp, FeedMessage) по порядку. hours — список 'YYYYMMDD-HH' (UTC)."""
    base = root or ROOT
    files = sorted(glob.glob(f"{base}/{feed}/*.bin.gz"))
    if hours:
        files = [f for f in files if os.path.basename(f).replace(".bin.gz","").split("__")[0] in hours]
    seen = set(); i = 0
    for path in files:
        try:
            with gzip.open(path, "rb") as fh:
                while True:
                    hdr = fh.read(4)
                    if len(hdr) < 4: break
                    (ln,) = struct.unpack(">I", hdr)
                    buf = fh.read(ln)
                    if len(buf) < ln: break
                    i += 1
                    if i % step: continue
                    try:
                        m = pb.FeedMessage(); m.ParseFromString(buf)
                    except Exception:
                        continue
                    ts = m.header.timestamp
                    if dedup:
                        if ts in seen: continue
                        seen.add(ts)
                    yield ts, m
        except (EOFError, OSError, zlib.error, struct.error):
            continue   # незакрытый архив — читаем до последнего целого снимка

def trip_key(t):
    return (t.route_id, t.direction_id, t.start_date, t.start_time)
