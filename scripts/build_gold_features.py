"""
Bronze → Silver → Gold Pipeline
Transforme les données historiques en features ML
"""
import clickhouse_connect
import pandas as pd
from datetime import datetime
import os

# ClickHouse connection
client = clickhouse_connect.get_client(
    host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
    port=int(os.getenv('CLICKHOUSE_HTTP_PORT', '8123')),
    database='airline_data'
)

print("=" * 80)
print("MEDALLION PIPELINE: Bronze → Silver → Gold")
print("=" * 80)

# ============================================================================
# STEP 1: Bronze → Silver (Nettoyage)
# ============================================================================
print("\n[1/3] Bronze → Silver: Nettoyage des données...")

client.command("""
INSERT INTO silver_flights
SELECT 
    id,
    year,
    month,
    carrier,
    carrier_name,
    airport,
    airport_name,
    arr_flights,
    arr_del15,
    CASE 
        WHEN arr_flights > 0 THEN arr_del15 / arr_flights
        ELSE 0
    END as delay_rate,
    carrier_ct,
    weather_ct,
    nas_ct,
    security_ct,
    late_aircraft_ct,
    arr_cancelled,
    arr_diverted,
    now() as ingestion_timestamp
FROM flights
WHERE arr_flights > 0 -- Filtre qualité
""")

silver_count = client.query("SELECT count() FROM silver_flights").result_rows[0][0]
print(f"✅ Silver: {silver_count:,} records")

# ============================================================================
# STEP 2: Silver → Gold (Feature Engineering)
# ============================================================================
print("\n[2/3] Silver → Gold: Feature engineering...")

# Créer les lag features et agrégations
client.command("""
INSERT INTO gold_ml_features
WITH 
-- Base data
base AS (
    SELECT 
        carrier,
        airport as origin_airport,
        year,
        month,
        delay_rate,
        arr_flights,
        arr_del15
    FROM silver_flights
    WHERE year >= 2010  -- Assez de données pour les lags
),

-- Lag features par paire (carrier + airport)
pair_lags AS (
    SELECT 
        carrier,
        origin_airport,
        year,
        month,
        lagInFrame(delay_rate, 1) OVER (
            PARTITION BY carrier, origin_airport 
            ORDER BY year, month
        ) as pair_lag1,
        lagInFrame(delay_rate, 2) OVER (
            PARTITION BY carrier, origin_airport 
            ORDER BY year, month
        ) as pair_lag2,
        lagInFrame(delay_rate, 3) OVER (
            PARTITION BY carrier, origin_airport 
            ORDER BY year, month
        ) as pair_lag3
    FROM base
),

-- Moyennes carrier
carrier_stats AS (
    SELECT 
        carrier,
        year,
        month,
        avg(delay_rate) as carrier_avg,
        lagInFrame(avg(delay_rate), 1) OVER (
            PARTITION BY carrier 
            ORDER BY year, month
        ) as carrier_lag1_mean,
        lagInFrame(avg(delay_rate), 2) OVER (
            PARTITION BY carrier 
            ORDER BY year, month
        ) as carrier_lag2_mean,
        lagInFrame(avg(delay_rate), 3) OVER (
            PARTITION BY carrier 
            ORDER BY year, month
        ) as carrier_lag3_mean
    FROM base
    GROUP BY carrier, year, month
),

-- Moyennes airport
airport_stats AS (
    SELECT 
        origin_airport,
        year,
        month,
        lagInFrame(avg(delay_rate), 1) OVER (
            PARTITION BY origin_airport 
            ORDER BY year, month
        ) as airport_lag1,
        lagInFrame(avg(delay_rate), 2) OVER (
            PARTITION BY origin_airport 
            ORDER BY year, month
        ) as airport_lag2,
        lagInFrame(avg(delay_rate), 3) OVER (
            PARTITION BY origin_airport 
            ORDER BY year, month
        ) as airport_lag3
    FROM base
    GROUP BY origin_airport, year, month
),

-- Rolling averages
rolling_stats AS (
    SELECT 
        carrier,
        origin_airport,
        year,
        month,
        -- Carrier rolling 3m et 6m
        avg(delay_rate) OVER (
            PARTITION BY carrier 
            ORDER BY toDate(concat(toString(year), '-', toString(month), '-01'))
            ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
        ) as carrier_rolling_3m,
        avg(delay_rate) OVER (
            PARTITION BY carrier 
            ORDER BY toDate(concat(toString(year), '-', toString(month), '-01'))
            ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING
        ) as carrier_rolling_6m,
        -- Airport rolling 3m et 6m
        avg(delay_rate) OVER (
            PARTITION BY origin_airport 
            ORDER BY toDate(concat(toString(year), '-', toString(month), '-01'))
            ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
        ) as airport_rolling_3m,
        avg(delay_rate) OVER (
            PARTITION BY origin_airport 
            ORDER BY toDate(concat(toString(year), '-', toString(month), '-01'))
            ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING
        ) as airport_rolling_6m
    FROM base
)

SELECT 
    b.carrier,
    b.origin_airport,
    b.year,
    b.month,
    b.delay_rate,
    b.arr_flights,
    b.arr_del15,
    
    -- Lag features
    COALESCE(pl.pair_lag1, 0) as pair_lag1,
    COALESCE(pl.pair_lag2, 0) as pair_lag2,
    COALESCE(pl.pair_lag3, 0) as pair_lag3,
    
    COALESCE(cs.carrier_lag1_mean, 0) as carrier_lag1_mean,
    COALESCE(cs.carrier_lag2_mean, 0) as carrier_lag2_mean,
    COALESCE(cs.carrier_lag3_mean, 0) as carrier_lag3_mean,
    
    COALESCE(ast.airport_lag1, 0) as airport_lag1,
    COALESCE(ast.airport_lag2, 0) as airport_lag2,
    COALESCE(ast.airport_lag3, 0) as airport_lag3,
    
    -- Rolling averages
    COALESCE(rs.carrier_rolling_3m, 0) as carrier_rolling_3m,
    COALESCE(rs.carrier_rolling_6m, 0) as carrier_rolling_6m,
    COALESCE(rs.airport_rolling_3m, 0) as airport_rolling_3m,
    COALESCE(rs.airport_rolling_6m, 0) as airport_rolling_6m,
    
    -- Temporal features
    toUInt8(month IN (6, 7, 8)) as is_summer,
    toUInt8(month IN (12, 1, 2)) as is_winter,
    toUInt8(month IN (11, 12)) as is_holiday_season,
    
    now() as created_at
    
FROM base b
LEFT JOIN pair_lags pl ON 
    b.carrier = pl.carrier AND 
    b.origin_airport = pl.origin_airport AND 
    b.year = pl.year AND 
    b.month = pl.month
LEFT JOIN carrier_stats cs ON 
    b.carrier = cs.carrier AND 
    b.year = cs.year AND 
    b.month = cs.month
LEFT JOIN airport_stats ast ON 
    b.origin_airport = ast.origin_airport AND 
    b.year = ast.year AND 
    b.month = ast.month
LEFT JOIN rolling_stats rs ON 
    b.carrier = rs.carrier AND 
    b.origin_airport = rs.origin_airport AND 
    b.year = rs.year AND 
    b.month = rs.month
WHERE b.year >= 2012  -- Avoir assez de lags (2010-2011 pour calculer)
""")

gold_count = client.query("SELECT count() FROM gold_ml_features").result_rows[0][0]
print(f"✅ Gold: {gold_count:,} records avec features ML")

# ============================================================================
# STEP 3: Statistiques
# ============================================================================
print("\n[3/3] Statistiques:")

stats = client.query("""
SELECT 
    uniq(carrier) as carriers,
    uniq(origin_airport) as airports,
    min(year) as min_year,
    max(year) as max_year,
    min(month) as min_month,
    max(month) as max_month,
    avg(delay_rate) as avg_delay_rate,
    countIf(delay_rate >= 0.3) as high_delay_routes
FROM gold_ml_features
""").result_rows[0]

print(f"""
📊 Dataset ML prêt:
   - Carriers: {stats[0]}
   - Airports: {stats[1]}
   - Période: {stats[2]}/{stats[4]} → {stats[3]}/{stats[5]}
   - Delay rate moyen: {stats[6]:.1%}
   - Routes haut risque (≥30%): {stats[7]:,}
""")

# Sample
print("\n📋 Sample des features:")
sample = client.query("SELECT * FROM gold_ml_features LIMIT 3").result_rows
for row in sample:
    print(f"   {row[0]} → {row[1]} | {row[2]}-{row[3]:02d} | delay_rate={row[4]:.1%}")

print("\n" + "=" * 80)
print("✅ PIPELINE TERMINÉ - Données prêtes pour entraînement ML")
print("=" * 80)
print(f"\n💡 Next: Entraîner modèle sur gold_ml_features ({gold_count:,} rows)")
print("💡 Prédictions iront dans ml_predictions (table séparée)")
