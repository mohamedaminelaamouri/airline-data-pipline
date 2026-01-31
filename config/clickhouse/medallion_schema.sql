-- ═══════════════════════════════════════════════════════════════
-- ARCHITECTURE MÉDAILLON - CLICKHOUSE
-- Scenario A: Bronze → Silver → Gold layers
-- Date: 2026-01-31
-- ═══════════════════════════════════════════════════════════════

USE airline_data;

-- ═══════════════════════════════════════════════════════════════
-- LAYER BRONZE: Raw Data (Kafka → ClickHouse)
-- Purpose: Audit trail, replay capability, data lineage
-- Retention: 90 days (TTL)
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS flights_bronze (
    -- Raw payload from Kafka
    raw_json String,
    
    -- Kafka metadata
    kafka_topic String DEFAULT 'airline-delays',
    kafka_partition UInt32,
    kafka_offset UInt64,
    kafka_timestamp DateTime64(3),
    
    -- Processing metadata
    ingestion_timestamp DateTime DEFAULT now(),
    processing_status Enum8(
        'pending' = 0,
        'processed' = 1,
        'failed' = 2,
        'skipped' = 3
    ) DEFAULT 'pending',
    processing_error String DEFAULT '',
    processing_attempts UInt8 DEFAULT 0,
    
    -- Source tracking
    source_system String DEFAULT 'nifi',
    source_version String DEFAULT 'v1.0',
    
    -- Data quality
    json_valid Bool DEFAULT 1,
    schema_version String DEFAULT 'v1'
    
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(ingestion_timestamp)
ORDER BY (ingestion_timestamp, kafka_partition, kafka_offset)
TTL ingestion_timestamp + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

-- Index for fast lookup by Kafka offset
ALTER TABLE flights_bronze ADD INDEX idx_kafka_offset kafka_offset TYPE minmax GRANULARITY 4;

-- ═══════════════════════════════════════════════════════════════
-- LAYER SILVER: Cleaned & Validated Data
-- Purpose: Business-ready data, validated, enriched
-- Retention: 5 years
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS flights_silver (
    -- Business keys
    id String,
    year UInt16,
    month UInt8,
    carrier FixedString(2),
    carrier_name String,
    airport FixedString(3),
    airport_name String,
    
    -- Metrics (validated)
    arr_flights UInt32,
    arr_del15 UInt32,
    arr_delay UInt32,
    arr_cancelled UInt16,
    arr_diverted UInt16,
    
    -- Delay breakdown (minutes)
    carrier_delay UInt32,
    weather_delay UInt32,
    nas_delay UInt32,
    security_delay UInt16,
    late_aircraft_delay UInt32,
    
    -- Delay causes breakdown (counts)
    carrier_ct Float32,
    weather_ct Float32,
    nas_ct Float32,
    security_ct Float32,
    late_aircraft_ct Float32,
    
    -- Calculated KPIs (materialized columns)
    delay_rate Float32 MATERIALIZED 
        CASE WHEN arr_flights > 0 THEN arr_del15 / arr_flights ELSE 0 END,
    
    cancel_rate Float32 MATERIALIZED 
        CASE WHEN arr_flights > 0 THEN arr_cancelled / arr_flights ELSE 0 END,
    
    divert_rate Float32 MATERIALIZED 
        CASE WHEN arr_flights > 0 THEN arr_diverted / arr_flights ELSE 0 END,
    
    avg_delay_per_flight Float32 MATERIALIZED 
        CASE WHEN arr_flights > 0 THEN arr_delay / arr_flights ELSE 0 END,
    
    avg_delay_per_delayed Float32 MATERIALIZED 
        CASE WHEN arr_del15 > 0 THEN arr_delay / arr_del15 ELSE 0 END,
    
    -- Geographic enrichment (from airports_gps)
    latitude Float64,
    longitude Float64,
    city String,
    state FixedString(2),
    country_code FixedString(2) DEFAULT 'US',
    
    -- Audit & Lineage
    bronze_kafka_offset UInt64,  -- Reference to bronze layer
    processed_at DateTime DEFAULT now(),
    data_quality_score UInt8,    -- 0-100 quality score
    validation_flags UInt32,     -- Bitmap of validation checks passed
    
    -- Timestamps
    business_date Date MATERIALIZED toDate(concat(toString(year), '-', toString(month), '-01')),
    record_hash String MATERIALIZED cityHash64(concat(carrier, airport, toString(year), toString(month)))
    
) ENGINE = ReplacingMergeTree(processed_at)
PARTITION BY (year, month)
ORDER BY (year, month, carrier, airport, id)
SETTINGS index_granularity = 8192;

-- Indexes for common query patterns
ALTER TABLE flights_silver ADD INDEX idx_delay_rate delay_rate TYPE minmax GRANULARITY 4;
ALTER TABLE flights_silver ADD INDEX idx_cancel_rate cancel_rate TYPE minmax GRANULARITY 4;
ALTER TABLE flights_silver ADD INDEX idx_carrier carrier TYPE set(0) GRANULARITY 4;
ALTER TABLE flights_silver ADD INDEX idx_airport airport TYPE set(0) GRANULARITY 4;
ALTER TABLE flights_silver ADD INDEX idx_state state TYPE set(0) GRANULARITY 4;

-- ═══════════════════════════════════════════════════════════════
-- LAYER GOLD: Business Aggregations (Materialized Views)
-- Purpose: Pre-computed aggregations for dashboards & ML
-- Refresh: Incremental (automatic)
-- ═══════════════════════════════════════════════════════════════

-- ───────────────────────────────────────────────────────────────
-- GOLD 1: Airport Performance Summary
-- ───────────────────────────────────────────────────────────────

CREATE MATERIALIZED VIEW IF NOT EXISTS gold_airport_performance
ENGINE = AggregatingMergeTree()
PARTITION BY year
ORDER BY (year, month, airport)
POPULATE  -- Initialize with existing data
AS SELECT
    year,
    month,
    airport,
    any(airport_name) as airport_name,
    any(city) as city,
    any(state) as state,
    any(latitude) as latitude,
    any(longitude) as longitude,
    
    -- Aggregated metrics
    sum(arr_flights) as total_flights,
    sum(arr_del15) as total_delayed,
    sum(arr_cancelled) as total_cancelled,
    sum(arr_diverted) as total_diverted,
    sum(arr_delay) as total_delay_minutes,
    
    -- Delay causes
    sum(carrier_delay) as total_carrier_delay,
    sum(weather_delay) as total_weather_delay,
    sum(nas_delay) as total_nas_delay,
    sum(security_delay) as total_security_delay,
    sum(late_aircraft_delay) as total_late_aircraft_delay,
    
    -- Calculated KPIs
    avg(delay_rate) as avg_delay_rate,
    avg(cancel_rate) as avg_cancel_rate,
    avg(avg_delay_per_flight) as avg_delay_minutes,
    
    -- Statistical measures
    quantile(0.50)(delay_rate) as median_delay_rate,
    quantile(0.90)(delay_rate) as p90_delay_rate,
    quantile(0.95)(delay_rate) as p95_delay_rate,
    
    -- Data quality
    avg(data_quality_score) as avg_quality_score,
    count() as record_count,
    
    -- Metadata
    max(processed_at) as last_updated,
    any(country_code) as country
    
FROM flights_silver
GROUP BY year, month, airport;

-- ───────────────────────────────────────────────────────────────
-- GOLD 2: Carrier Performance Summary
-- ───────────────────────────────────────────────────────────────

CREATE MATERIALIZED VIEW IF NOT EXISTS gold_carrier_performance
ENGINE = SummingMergeTree()
ORDER BY (year, month, carrier)
POPULATE
AS SELECT
    year,
    month,
    carrier,
    any(carrier_name) as carrier_name,
    
    -- Aggregated metrics
    sum(arr_flights) as total_flights,
    sum(arr_del15) as total_delayed,
    sum(arr_cancelled) as total_cancelled,
    sum(arr_delay) as total_delay_minutes,
    
    -- KPIs
    avg(delay_rate) as avg_delay_rate,
    avg(cancel_rate) as avg_cancel_rate,
    
    -- Rankings
    count(DISTINCT airport) as airports_served,
    
    -- Metadata
    max(processed_at) as last_updated
    
FROM flights_silver
GROUP BY year, month, carrier;

-- ───────────────────────────────────────────────────────────────
-- GOLD 3: Monthly Trends (Time Series)
-- ───────────────────────────────────────────────────────────────

CREATE MATERIALIZED VIEW IF NOT EXISTS gold_monthly_trends
ENGINE = SummingMergeTree()
ORDER BY (year, month)
POPULATE
AS SELECT
    year,
    month,
    
    -- Volume metrics
    count() as total_records,
    sum(arr_flights) as total_flights,
    sum(arr_del15) as total_delayed,
    sum(arr_cancelled) as total_cancelled,
    
    -- Delay breakdown
    sum(carrier_delay) as total_carrier_delay,
    sum(weather_delay) as total_weather_delay,
    sum(nas_delay) as total_nas_delay,
    sum(security_delay) as total_security_delay,
    sum(late_aircraft_delay) as total_late_aircraft_delay,
    
    -- Industry-wide KPIs
    avg(delay_rate) as industry_avg_delay_rate,
    avg(cancel_rate) as industry_avg_cancel_rate,
    
    -- Geographic distribution
    count(DISTINCT airport) as unique_airports,
    count(DISTINCT carrier) as unique_carriers,
    
    -- Metadata
    max(processed_at) as last_updated
    
FROM flights_silver
GROUP BY year, month;

-- ───────────────────────────────────────────────────────────────
-- GOLD 4: Route Performance (Carrier + Airport pairs)
-- ───────────────────────────────────────────────────────────────

CREATE MATERIALIZED VIEW IF NOT EXISTS gold_route_performance
ENGINE = AggregatingMergeTree()
PARTITION BY year
ORDER BY (year, month, carrier, airport)
POPULATE
AS SELECT
    year,
    month,
    carrier,
    airport,
    any(carrier_name) as carrier_name,
    any(airport_name) as airport_name,
    any(state) as state,
    
    -- Route metrics
    sum(arr_flights) as route_flights,
    sum(arr_del15) as route_delayed,
    avg(delay_rate) as route_delay_rate,
    avg(cancel_rate) as route_cancel_rate,
    
    -- For ML features (lag calculations)
    sum(arr_delay) as route_total_delay,
    avg(avg_delay_per_flight) as route_avg_delay,
    
    -- Quality
    avg(data_quality_score) as quality_score,
    
    -- Metadata
    max(processed_at) as last_updated
    
FROM flights_silver
GROUP BY year, month, carrier, airport;

-- ───────────────────────────────────────────────────────────────
-- GOLD 5: Real-time Monitoring (Last 24 hours)
-- ───────────────────────────────────────────────────────────────

CREATE MATERIALIZED VIEW IF NOT EXISTS gold_realtime_stats
ENGINE = AggregatingMergeTree()
ORDER BY ingestion_hour
POPULATE
AS SELECT
    toStartOfHour(processed_at) as ingestion_hour,
    
    -- Processing stats
    count() as records_processed,
    sum(arr_flights) as flights_ingested,
    avg(delay_rate) as current_delay_rate,
    
    -- Data quality
    avg(data_quality_score) as avg_quality,
    countIf(data_quality_score < 70) as low_quality_count,
    
    -- Performance
    max(processed_at) as last_record_time,
    count(DISTINCT carrier) as active_carriers,
    count(DISTINCT airport) as active_airports
    
FROM flights_silver
WHERE processed_at >= now() - INTERVAL 24 HOUR
GROUP BY ingestion_hour;

-- ═══════════════════════════════════════════════════════════════
-- HELPER VIEWS FOR API & DASHBOARDS
-- ═══════════════════════════════════════════════════════════════

-- Latest month snapshot (for current state queries)
CREATE VIEW IF NOT EXISTS v_latest_month_performance AS
SELECT
    carrier,
    airport,
    carrier_name,
    airport_name,
    state,
    total_flights,
    total_delayed,
    avg_delay_rate,
    avg_cancel_rate,
    p90_delay_rate,
    last_updated
FROM gold_airport_performance
WHERE (year, month) = (
    SELECT year, month 
    FROM gold_monthly_trends 
    ORDER BY year DESC, month DESC 
    LIMIT 1
)
ORDER BY total_flights DESC;

-- High-risk routes (for ML predictions API)
CREATE VIEW IF NOT EXISTS v_high_risk_routes AS
SELECT
    carrier,
    airport,
    carrier_name,
    airport_name,
    state,
    route_delay_rate,
    route_flights,
    'high_risk' as risk_category
FROM gold_route_performance
WHERE (year, month) = (
    SELECT year, month 
    FROM gold_monthly_trends 
    ORDER BY year DESC, month DESC 
    LIMIT 1
)
AND route_delay_rate > 0.25
AND route_flights > 10
ORDER BY route_delay_rate DESC
LIMIT 100;

-- ═══════════════════════════════════════════════════════════════
-- DATA QUALITY CHECKS
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS data_quality_log (
    check_timestamp DateTime DEFAULT now(),
    check_name String,
    check_status Enum8('pass' = 0, 'warning' = 1, 'fail' = 2),
    affected_records UInt32,
    details String,
    layer Enum8('bronze' = 0, 'silver' = 1, 'gold' = 2)
) ENGINE = MergeTree()
ORDER BY check_timestamp
TTL check_timestamp + INTERVAL 30 DAY;

-- ═══════════════════════════════════════════════════════════════
-- COMMENTS & DOCUMENTATION
-- ═══════════════════════════════════════════════════════════════

ALTER TABLE flights_bronze COMMENT 'Bronze layer: Raw data from Kafka with 90-day retention';
ALTER TABLE flights_silver COMMENT 'Silver layer: Validated, enriched business data';
ALTER TABLE gold_airport_performance COMMENT 'Gold: Pre-aggregated airport metrics for dashboards';
ALTER TABLE gold_carrier_performance COMMENT 'Gold: Pre-aggregated carrier metrics for dashboards';
ALTER TABLE gold_monthly_trends COMMENT 'Gold: Industry-wide monthly trends for analytics';
ALTER TABLE gold_route_performance COMMENT 'Gold: Carrier-Airport route metrics for ML features';
ALTER TABLE gold_realtime_stats COMMENT 'Gold: Last 24h monitoring metrics';

-- ═══════════════════════════════════════════════════════════════
-- COMPLETED: Medallion Architecture Setup
-- Next Steps:
--   1. Update kafka_to_clickhouse.py → kafka_to_bronze.py
--   2. Create bronze_to_silver.py transformation script
--   3. Update ML pipeline to use gold_route_performance
-- ═══════════════════════════════════════════════════════════════
