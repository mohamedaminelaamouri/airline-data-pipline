-- ClickHouse Initialization Script
-- Creates database and tables for airline delay data

-- Create database
CREATE DATABASE IF NOT EXISTS airline_data;

USE airline_data;

-- Airport GPS lookup table with geographic coordinates
CREATE TABLE IF NOT EXISTS airports_gps (
    airport_code String,
    airport_full_name String,
    city String,
    state String,
    country_code String,
    latitude Float64,
    longitude Float64
) ENGINE = MergeTree()
ORDER BY airport_code;

-- Main flights table with all delay information
CREATE TABLE IF NOT EXISTS flights (
    id String,
    year UInt16,
    month UInt8,
    carrier String,
    carrier_name String,
    airport String,
    airport_name String,
    arr_flights UInt32,
    arr_del15 UInt32,
    carrier_ct Float32,
    weather_ct Float32,
    nas_ct Float32,
    security_ct Float32,
    late_aircraft_ct Float32,
    arr_cancelled UInt32,
    arr_diverted UInt32,
    arr_delay UInt32,
    carrier_delay UInt32,
    weather_delay UInt32,
    nas_delay UInt32,
    security_delay UInt32,
    late_aircraft_delay UInt32,
    ingestion_timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (year, month, carrier, airport)
PARTITION BY toYYYYMM(toDate(concat(toString(year), '-', toString(month), '-01')))
SETTINGS index_granularity = 8192;





