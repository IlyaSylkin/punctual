CREATE TABLE positions (
    city           LowCardinality(String),
    route_id       LowCardinality(String),
    direction_id   UInt8,
    start_date     Date,
    start_time     String,
    trip_id        Nullable(String),
    vehicle_id     String,
    ts             DateTime,
    ingested_at    DateTime,
    lat            Float64,
    lon            Float64,
    bearing        Nullable(Float32),
    speed          Nullable(Float32),
    stop_id        Nullable(String),
    stop_sequence  Nullable(UInt16),
    current_status Nullable(Enum8('INCOMING_AT' = 0, 'STOPPED_AT' = 1, 'IN_TRANSIT_TO' = 2))
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(ts)
ORDER BY (city, route_id, direction_id, start_date, start_time, ts)
TTL ts + INTERVAL 3 WEEK;
