"""Суточный захват сырья GTFS-RT. Пишет только изменившиеся ответы.

Формат файла: повторяющиеся [4 байта длины BE][protobuf], весь поток gzip.
Метаданные: JSONL, строка на каждый опрос.
"""
import asyncio, gzip, hashlib, json, os, signal, struct, sys, time, datetime as dt
import httpx

RUN = f"{dt.datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}"   # свой набор файлов на запуск

ROOT = os.environ.get("CAPTURE_DIR", "./capture")
UA = {"User-Agent": "gtfs-feed-probe/0.1 (portfolio feasibility study; polite, low rate)"}
HOURS = float(sys.argv[1]) if len(sys.argv) > 1 else 26.0
POLL = 10.0

FEEDS = {
    "hsl-positions":    "https://realtime.hsl.fi/realtime/vehicle-positions/v2/hsl",
    "hsl-tripupdates":  "https://realtime.hsl.fi/realtime/trip-updates/v2/hsl",
    "mbta-positions":   "https://cdn.mbta.com/realtime/VehiclePositions.pb",
    "mbta-tripupdates": "https://cdn.mbta.com/realtime/TripUpdates.pb",
}

def header_ts(buf: bytes):
    """Достать header.timestamp без полного разбора: поле 3 в FeedHeader (поле 1)."""
    try:
        from google.transit import gtfs_realtime_pb2 as pb
        m = pb.FeedMessage(); m.ParseFromString(buf)
        return m.header.timestamp, len(m.entity)
    except Exception:
        return None, None

class Writer:
    def __init__(self, feed):
        self.feed = feed; self.hour = None; self.fh = None
        os.makedirs(f"{ROOT}/{feed}", exist_ok=True)
        os.makedirs(f"{ROOT}/meta", exist_ok=True)
        self.meta = open(f"{ROOT}/meta/{feed}__{RUN}.jsonl", "a", buffering=1)
    def _roll(self, now):
        h = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y%m%d-%H")
        if h != self.hour:
            if self.fh: self.fh.close()
            self.hour = h
            # имя включает идентификатор запуска: два процесса физически не могут
            # писать в один файл, даже если запущены одновременно
            self.fh = gzip.open(f"{ROOT}/{self.feed}/{h}__{RUN}.bin.gz", "wb", compresslevel=6)
    def store(self, now, buf):
        self._roll(now)
        self.fh.write(struct.pack(">I", len(buf))); self.fh.write(buf); self.fh.flush()
    def log(self, rec):
        self.meta.write(json.dumps(rec, separators=(",", ":")) + "\n")
    def close(self):
        if self.fh: self.fh.close()
        self.meta.close()

async def run(name, url, client, deadline):
    w = Writer(name); last_hash = None; stored = polls = errs = 0
    while time.time() < deadline:
        t0 = time.time()
        rec = {"t": round(t0, 1)}
        try:
            r = await client.get(url, timeout=25.0)
            rec["http"] = r.status_code; rec["bytes"] = len(r.content)
            if r.status_code == 200:
                hts, n = header_ts(r.content)
                rec["hts"] = hts; rec["entities"] = n
                # дедупликация по содержимому: у HSL header.timestamp меняется
                # почти на каждый запрос и для этого непригоден
                h = hashlib.sha1(r.content).digest()
                if h != last_hash:
                    w.store(t0, r.content); last_hash = h
                    rec["stored"] = 1; stored += 1
        except Exception as e:
            rec["err"] = type(e).__name__; errs += 1
        polls += 1
        w.log(rec)
        await asyncio.sleep(max(0.5, POLL - (time.time() - t0)))
    w.close()
    print(f"{name}: опросов {polls}, сохранено {stored}, ошибок {errs}", flush=True)

async def main():
    deadline = time.time() + HOURS * 3600
    print(f"старт {dt.datetime.now():%Y-%m-%d %H:%M:%S}, работа {HOURS} ч, "
          f"до {dt.datetime.fromtimestamp(deadline):%Y-%m-%d %H:%M:%S}", flush=True)
    async with httpx.AsyncClient(headers=UA, follow_redirects=True) as c:
        await asyncio.gather(*(run(n, u, c, deadline) for n, u in FEEDS.items()))
    print("готово", flush=True)

asyncio.run(main())
