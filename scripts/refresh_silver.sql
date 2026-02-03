-- Rafraîchir silver_flights depuis flights (Bronze → Silver)

TRUNCATE TABLE IF EXISTS airline_data.silver_flights;

INSERT INTO airline_data.silver_flights
SELECT 
    generateUUIDv4() AS id,
    year,
    month,
    carrier,
    carrier_name,
    airport,
    airport_name,
    arr_flights,
    arr_del15,
    CASE WHEN arr_flights > 0 THEN arr_del15 / arr_flights ELSE 0 END AS delay_rate,
    carrier_ct,
    weather_ct,
    nas_ct,
    security_ct,
    late_aircraft_ct,
    arr_cancelled,
    arr_diverted,
    arr_delay,
    1.0 AS data_quality_score,
    '' AS bronze_id,
    now() AS cleaned_at
FROM airline_data.flights
WHERE arr_flights > 0;
