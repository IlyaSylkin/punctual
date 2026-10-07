CREATE TABLE arrivals (
    city         LowCardinality(String),
    route_id     LowCardinality(String),
    direction_id UInt8,
    start_date   Date,
    start_time   String,
    stop_id      String,
    arrival_time DateTime,
    observed_at  DateTime,
    source       Enum8('feed' = 1, 'stopped_at' = 2, 'geofence' = 3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(arrival_time)
ORDER BY (city, route_id, direction_id, start_date, start_time, stop_id, observed_at);
