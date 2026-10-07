CREATE TABLE errors (
    city          LowCardinality(String),
    route_id      LowCardinality(String),
    direction_id  UInt8,
    start_date    Date,
    start_time    String,
    stop_id       String,
    arrival_time  DateTime,
    model         LowCardinality(String),
    model_version LowCardinality(String),
    err_0_3       Nullable(Int32),
    err_3_6       Nullable(Int32),
    err_6_10      Nullable(Int32),
    err_10_15     Nullable(Int32),
    err_15_30     Nullable(Int32),
    err_30p       Nullable(Int32),
    resolved_at   DateTime,
    hour          UInt8 MATERIALIZED toHour(arrival_time),
    day_type      UInt8 MATERIALIZED if(toDayOfWeek(arrival_time) < 6, 0, 1)
)
ENGINE = ReplacingMergeTree(resolved_at)
PARTITION BY toYYYYMM(arrival_time)
ORDER BY (city, model, model_version, route_id, arrival_time, stop_id);
