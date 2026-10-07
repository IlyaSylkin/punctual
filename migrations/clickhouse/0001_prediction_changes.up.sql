CREATE TABLE prediction_changes (
    city                  LowCardinality(String),
    route_id              LowCardinality(String),
    direction_id          UInt8,
    start_date            Date,
    start_time            String,
    stop_id               String,
    published_at          DateTime,
    predicted_arrival     Nullable(DateTime),
    predicted_departure   Nullable(DateTime),
    uncertainty           Nullable(UInt16),
    schedule_relationship LowCardinality(String),
    ingested_at           DateTime
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(published_at)
ORDER BY (city, route_id, direction_id, start_date, start_time, stop_id, published_at)
TTL published_at + INTERVAL 3 MONTH;
