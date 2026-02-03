#!/usr/bin/env python3
"""
Créer et rafraîchir silver_flights depuis flights (Bronze → Silver)
"""
import clickhouse_connect

# Connexion ClickHouse
client = clickhouse_connect.get_client(host='localhost', port=8123, database='airline_data')

print("=== Création et Rafraîchissement Silver ===")

# 1. Créer silver_flights
print("1. Création de silver_flights...")
create_sql = """
CREATE TABLE IF NOT EXISTS silver_flights (
    id String,
    year UInt16,
    month UInt8,
    carrier String,
    carrier_name String,
    airport String,
    airport_name String,
    arr_flights UInt32,
    arr_del15 UInt32,
    delay_rate Float32,
    carrier_ct Float32 DEFAULT 0,
    weather_ct Float32 DEFAULT 0,
    nas_ct Float32 DEFAULT 0,
    security_ct Float32 DEFAULT 0,
    late_aircraft_ct Float32 DEFAULT 0,
    arr_cancelled UInt32 DEFAULT 0,
    arr_diverted UInt32 DEFAULT 0,
    arr_delay Float32 DEFAULT 0,
    data_quality_score Float32 DEFAULT 1.0,
    bronze_id String,
    cleaned_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(cleaned_at)
ORDER BY (year, month, carrier, airport)
PARTITION BY year
"""

try:
    client.command(create_sql)
    print("✓ Table créée")
except Exception as e:
    print(f"Table existe déjà ou erreur: {e}")

# 2. Vider silver_flights
print("2. Vidage de silver_flights...")
client.command("TRUNCATE TABLE IF EXISTS silver_flights")

# 2. Insérer depuis flights
print("3. Insertion des données nettoyées...")
query = """
INSERT INTO silver_flights
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
FROM flights
WHERE arr_flights > 0
"""

client.command(query)

# 4. Vérifier le résultat
count = client.query("SELECT count() FROM silver_flights").result_rows[0][0]
print(f"✓ {count:,} lignes insérées dans silver_flights")

# 5. Stats
result = client.query("""
SELECT 
    count() AS total,
    count(DISTINCT carrier) AS carriers,
    count(DISTINCT airport) AS airports,
    min(year) AS year_min,
    max(year) AS year_max,
    avg(delay_rate) AS avg_delay_rate
FROM silver_flights
""")

stats = result.result_rows[0]
print(f"\nStatistiques Silver:")
print(f"  - Total lignes: {stats[0]:,}")
print(f"  - Carriers: {stats[1]}")
print(f"  - Airports: {stats[2]}")
print(f"  - Années: {stats[3]}-{stats[4]}")
print(f"  - Delay rate moyen: {stats[5]:.2%}")

print("\n✓ Rafraîchissement terminé!")
