"""
MEDALLION PIPELINE: Bronze → Silver → Gold
==========================================
Transforme les données brutes en données prêtes pour BI et ML

Usage:
    python scripts/medallion_pipeline.py

Architecture:
    bronze_flights (raw) -> silver_flights (clean) -> gold_bi (PowerBI)
                                                  -> gold_ml_features (XGBoost)
"""

import argparse
import clickhouse_connect
import pandas as pd
import numpy as np
import os
from datetime import datetime

# Configuration
CLICKHOUSE_HOST = os.getenv('CLICKHOUSE_HOST', 'localhost')
CLICKHOUSE_PORT = int(os.getenv('CLICKHOUSE_HTTP_PORT', '8123'))
CLICKHOUSE_DB = 'airline_data'

print("=" * 80)
print("MEDALLION PIPELINE: Bronze -> Silver -> Gold")
print("=" * 80)

# Connexion ClickHouse
client = clickhouse_connect.get_client(
    host=CLICKHOUSE_HOST,
    port=CLICKHOUSE_PORT,
    database=CLICKHOUSE_DB
)
print(f"✅ Connecté à ClickHouse: {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}")


print(f"Connected to ClickHouse: {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}")


# ============================================================================
# STEP 1: Bronze -> Silver (Nettoyage)
# ============================================================================
def bronze_to_silver():
    """Nettoyage des données brutes et insertion dans silver_flights."""
    print("\n" + "=" * 60)
    print("[1/3] BRONZE -> SILVER: Nettoyage des données")
    print("=" * 60)
    
    # Synchroniser depuis la table flights (source NiFi)
    flights_count = client.command("SELECT count() FROM flights")
    bronze_count = client.command("SELECT count() FROM bronze_flights")
    print(f"  Lines in flights (source): {flights_count:,}")
    print(f"  Lines in bronze_flights: {bronze_count:,}")
    
    if flights_count > bronze_count:
        print(f"  Synchronizing {flights_count - bronze_count:,} new lines from flights...")
        # Vider bronze et recharger depuis flights
        client.command("TRUNCATE TABLE bronze_flights")
        client.command("""
            INSERT INTO bronze_flights (
                year, month, carrier, carrier_name, airport, airport_name,
                arr_flights, arr_del15, carrier_ct, weather_ct, nas_ct,
                security_ct, late_aircraft_ct, arr_cancelled, arr_diverted,
                arr_delay, carrier_delay, weather_delay, nas_delay,
                security_delay, late_aircraft_delay, source_file
            )
            SELECT 
                year, month, carrier, carrier_name, airport, airport_name,
                arr_flights, arr_del15, carrier_ct, weather_ct, nas_ct,
                security_ct, late_aircraft_ct, arr_cancelled, arr_diverted,
                arr_delay, carrier_delay, weather_delay, nas_delay,
                security_delay, late_aircraft_delay, 'flights_nifi_ingestion'
            FROM flights
        """)
        bronze_count = client.command("SELECT count() FROM bronze_flights")
        print(f"  Bronze synchronized: {bronze_count:,} lines")
    
    # Nettoyer et insérer dans silver
    print("\n  Cleaning in progress...")
    
    client.command("TRUNCATE TABLE silver_flights")
    
    client.command("""
        INSERT INTO silver_flights (
            id, year, month, carrier, carrier_name, airport, airport_name,
            arr_flights, arr_del15, delay_rate, carrier_ct, weather_ct,
            nas_ct, security_ct, late_aircraft_ct, arr_cancelled, arr_diverted,
            arr_delay, data_quality_score, bronze_id
        )
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
            -- Calcul delay_rate avec protection division par zéro
            CASE 
                WHEN arr_flights > 0 THEN arr_del15 / arr_flights 
                ELSE 0 
            END AS delay_rate,
            COALESCE(carrier_ct, 0),
            COALESCE(weather_ct, 0),
            COALESCE(nas_ct, 0),
            COALESCE(security_ct, 0),
            COALESCE(late_aircraft_ct, 0),
            COALESCE(arr_cancelled, 0),
            COALESCE(arr_diverted, 0),
            COALESCE(arr_delay, 0),
            -- Score qualité basé sur complétude
            CASE
                WHEN arr_flights IS NOT NULL AND arr_del15 IS NOT NULL THEN 1.0
                ELSE 0.5
            END AS data_quality_score,
            id AS bronze_id
        FROM bronze_flights
        WHERE 
            -- Filtres de nettoyage
            year IS NOT NULL 
            AND month IS NOT NULL 
            AND month BETWEEN 1 AND 12
            AND carrier IS NOT NULL 
            AND carrier != ''
            AND airport IS NOT NULL 
            AND airport != ''
            AND arr_flights IS NOT NULL
            AND arr_flights > 0
    """)
    
    silver_count = client.command("SELECT count() FROM silver_flights")
    rejected = bronze_count - silver_count
    
    print(f"  Silver created: {silver_count:,} lines")
    print(f"  Rejected lines: {rejected:,} ({rejected/bronze_count*100:.1f}%)")
    
    # Stats de qualité
    stats = client.query("""
        SELECT 
            min(year) as min_year, max(year) as max_year,
            countDistinct(carrier) as carriers,
            countDistinct(airport) as airports,
            avg(delay_rate) as avg_delay
        FROM silver_flights
    """).result_rows[0]
    
    print(f"\n  Silver Statistics:")
    print(f"     Period: {stats[0]} - {stats[1]}")
    print(f"     Carriers: {stats[2]}")
    print(f"     Airports: {stats[3]}")
    print(f"     Average delay rate: {stats[4]*100:.1f}%")


# ============================================================================
# STEP 2: Silver -> Gold BI (Agrégations pour Power BI)
# ============================================================================
def silver_to_gold_bi():
    """Crée les KPIs agrégés pour Power BI."""
    print("\n" + "=" * 60)
    print("[2/3] SILVER -> GOLD BI: Agrégations Power BI")
    print("=" * 60)
    
    client.command("TRUNCATE TABLE gold_bi")
    
    # Insertion des agrégations
    client.command("""
        INSERT INTO gold_bi (
            carrier, carrier_name, airport, airport_name, year, month,
            total_flights, delayed_flights, delay_rate, on_time_rate,
            carrier_delay_pct, weather_delay_pct, nas_delay_pct,
            security_delay_pct, late_aircraft_delay_pct,
            cancelled_flights, diverted_flights, cancel_rate, divert_rate
        )
        SELECT
            carrier,
            any(carrier_name) AS carrier_name,
            airport,
            any(airport_name) AS airport_name,
            year,
            month,
            
            -- Volumes
            sum(arr_flights) AS total_flights,
            sum(arr_del15) AS delayed_flights,
            
            -- Taux
            CASE WHEN sum(arr_flights) > 0 
                THEN sum(arr_del15) / sum(arr_flights) 
                ELSE 0 
            END AS delay_rate,
            
            CASE WHEN sum(arr_flights) > 0 
                THEN 1 - (sum(arr_del15) / sum(arr_flights))
                ELSE 1 
            END AS on_time_rate,
            
            -- Répartition des causes (% du total des retards)
            CASE WHEN sum(arr_del15) > 0 
                THEN sum(carrier_ct) / sum(arr_del15) 
                ELSE 0 
            END AS carrier_delay_pct,
            
            CASE WHEN sum(arr_del15) > 0 
                THEN sum(weather_ct) / sum(arr_del15) 
                ELSE 0 
            END AS weather_delay_pct,
            
            CASE WHEN sum(arr_del15) > 0 
                THEN sum(nas_ct) / sum(arr_del15) 
                ELSE 0 
            END AS nas_delay_pct,
            
            CASE WHEN sum(arr_del15) > 0 
                THEN sum(security_ct) / sum(arr_del15) 
                ELSE 0 
            END AS security_delay_pct,
            
            CASE WHEN sum(arr_del15) > 0 
                THEN sum(late_aircraft_ct) / sum(arr_del15) 
                ELSE 0 
            END AS late_aircraft_delay_pct,
            
            -- Annulations et détournements
            sum(arr_cancelled) AS cancelled_flights,
            sum(arr_diverted) AS diverted_flights,
            
            CASE WHEN sum(arr_flights) > 0 
                THEN sum(arr_cancelled) / sum(arr_flights) 
                ELSE 0 
            END AS cancel_rate,
            
            CASE WHEN sum(arr_flights) > 0 
                THEN sum(arr_diverted) / sum(arr_flights) 
                ELSE 0 
            END AS divert_rate
        FROM silver_flights
        GROUP BY carrier, airport, year, month
    """)
    
    gold_bi_count = client.command("SELECT count() FROM gold_bi")
    print(f"  Gold BI created: {gold_bi_count:,} aggregations")
    
    # Stats
    stats = client.query("""
        SELECT 
            avg(delay_rate) as avg_delay,
            max(delay_rate) as max_delay,
            sum(total_flights) as total_flights
        FROM gold_bi
    """).result_rows[0]
    
    print(f"\n  Gold BI Statistics:")
    print(f"     Average delay rate: {stats[0]*100:.1f}%")
    print(f"     Max delay rate: {stats[1]*100:.1f}%")
    print(f"     Total flights: {stats[2]:,}")


# ============================================================================
# STEP 3: Silver -> Gold ML (Features pour Machine Learning)
# ============================================================================
def silver_to_gold_ml():
    """
    Crée les features ML avec tous les lag features et encoding stable.
    
    IMPORTANT: Cette fonction est la SOURCE UNIQUE de vérité pour les features ML.
    Aucun feature engineering ne doit être fait en Python (ni dans training, ni dans serving).
    
    Features générées:
    - carrier_id, airport_id: Encoding hash stable (remplace LabelEncoder)
    - month_sin, month_cos: Encoding cyclique du mois
    - is_summer, is_winter, is_holiday_season: Indicateurs saisonniers
    - pair_lag1, pair_lag3_mean, pair_expanding_mean: Lags niveau paire
    - airport_lag1, airport_lag3_mean, airport_expanding_mean: Lags niveau aéroport
    - carrier_lag1, carrier_lag3_mean, carrier_expanding_mean: Lags niveau carrier
    - is_delayed: Target binaire (delay_rate > 0.20)
    """
    print("\n" + "=" * 60)
    print("[3/3] SILVER -> GOLD ML: Features Machine Learning (v3)")
    print("=" * 60)
    
    # Recréer la table avec le nouveau schéma
    print("  Creating gold_ml_features v3 schema...")
    
    client.command("DROP TABLE IF EXISTS gold_ml_features")
    client.command("""
        CREATE TABLE gold_ml_features (
            -- Identifiants
            carrier String,
            origin_airport String,
            year UInt16,
            month UInt8,
            
            -- Encoding stable (remplace LabelEncoder)
            carrier_id UInt32,
            airport_id UInt32,
            
            -- Target
            delay_rate Float32,
            is_delayed UInt8,
            
            -- Volume
            arr_flights UInt32,
            arr_del15 UInt32,
            log_arr_flights Float32,
            
            -- Lag features paire
            pair_lag1 Float32,
            pair_lag3_mean Float32,
            pair_expanding_mean Float32,
            
            -- Lag features airport
            airport_lag1 Float32,
            airport_lag3_mean Float32,
            airport_expanding_mean Float32,
            
            -- Lag features carrier
            carrier_lag1 Float32,
            carrier_lag3_mean Float32,
            carrier_expanding_mean Float32,
            
            -- Temporel cyclique
            month_sin Float32,
            month_cos Float32,
            
            -- Saisonnier
            is_summer UInt8,
            is_winter UInt8,
            is_holiday_season UInt8,
            
            -- Métadonnées
            feature_version String DEFAULT 'v3',
            created_at DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree(created_at)
        ORDER BY (carrier, origin_airport, year, month)
        PARTITION BY year
    """)

    # Créer une table temporaire avec les agrégations de base
    print("  Creating base aggregations...")
    
    client.command("DROP TABLE IF EXISTS temp_base_agg")
    client.command("""
        CREATE TABLE temp_base_agg (
            carrier String,
            origin_airport String,
            year UInt16,
            month UInt8,
            arr_flights UInt32,
            arr_del15 UInt32,
            delay_rate Float32
        ) ENGINE = MergeTree()
        ORDER BY (carrier, origin_airport, year, month)
    """)

    client.command("""
        INSERT INTO temp_base_agg
        SELECT
            carrier,
            airport as origin_airport,
            year,
            month,
            toUInt32(total_flights) as arr_flights,
            toUInt32(total_delays) as arr_del15,
            CASE WHEN total_flights > 0 THEN total_delays / total_flights ELSE 0 END AS delay_rate
        FROM (
            SELECT
                carrier,
                airport,
                year,
                month,
                sum(arr_flights) as total_flights,
                sum(arr_del15) as total_delays
            FROM silver_flights
            GROUP BY carrier, airport, year, month
        )
    """)
    
    # Calculer les moyennes par carrier pour les lag features carrier
    print("  🔄 Calcul des moyennes carrier/airport...")
    
    client.command("DROP TABLE IF EXISTS temp_carrier_means")
    client.command("""
        CREATE TABLE temp_carrier_means (
            carrier String,
            year UInt16,
            month UInt8,
            carrier_mean_delay Float32
        ) ENGINE = MergeTree()
        ORDER BY (carrier, year, month)
    """)
    
    client.command("""
        INSERT INTO temp_carrier_means
        SELECT 
            carrier,
            year,
            month,
            avg(delay_rate) as carrier_mean_delay
        FROM temp_base_agg
        GROUP BY carrier, year, month
    """)
    
    client.command("DROP TABLE IF EXISTS temp_airport_means")
    client.command("""
        CREATE TABLE temp_airport_means (
            origin_airport String,
            year UInt16,
            month UInt8,
            airport_mean_delay Float32
        ) ENGINE = MergeTree()
        ORDER BY (origin_airport, year, month)
    """)
    
    client.command("""
        INSERT INTO temp_airport_means
        SELECT 
            origin_airport,
            year,
            month,
            avg(delay_rate) as airport_mean_delay
        FROM temp_base_agg
        GROUP BY origin_airport, year, month
    """)
    
    # Insérer les features complètes avec window functions
    print("  🔄 Calcul des lag features et insertion...")
    
    client.command("""
        INSERT INTO gold_ml_features (
            carrier, origin_airport, year, month,
            carrier_id, airport_id,
            delay_rate, is_delayed,
            arr_flights, arr_del15, log_arr_flights,
            pair_lag1, pair_lag3_mean, pair_expanding_mean,
            airport_lag1, airport_lag3_mean, airport_expanding_mean,
            carrier_lag1, carrier_lag3_mean, carrier_expanding_mean,
            month_sin, month_cos,
            is_summer, is_winter, is_holiday_season
        )
        WITH 
        -- Calcul des lag features niveau paire avec window functions
        pair_features AS (
            SELECT
                carrier,
                origin_airport,
                year,
                month,
                delay_rate,
                arr_flights,
                arr_del15,
                -- Lag 1 mois (valeur du mois précédent)
                lagInFrame(delay_rate, 1) OVER w AS pair_lag1_raw,
                -- Moyenne des 3 derniers mois (M-1, M-2, M-3)
                avg(delay_rate) OVER (
                    PARTITION BY carrier, origin_airport 
                    ORDER BY year, month 
                    ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
                ) AS pair_lag3_mean_raw,
                -- Moyenne cumulative (tous les mois précédents)
                avg(delay_rate) OVER (
                    PARTITION BY carrier, origin_airport 
                    ORDER BY year, month 
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ) AS pair_expanding_mean_raw
            FROM temp_base_agg
            WINDOW w AS (PARTITION BY carrier, origin_airport ORDER BY year, month)
        ),
        -- Calcul des lag features niveau carrier
        carrier_features AS (
            SELECT
                carrier,
                year,
                month,
                lagInFrame(carrier_mean_delay, 1) OVER w AS carrier_lag1_raw,
                avg(carrier_mean_delay) OVER (
                    PARTITION BY carrier 
                    ORDER BY year, month 
                    ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
                ) AS carrier_lag3_mean_raw,
                avg(carrier_mean_delay) OVER (
                    PARTITION BY carrier 
                    ORDER BY year, month 
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ) AS carrier_expanding_mean_raw
            FROM temp_carrier_means
            WINDOW w AS (PARTITION BY carrier ORDER BY year, month)
        ),
        -- Calcul des lag features niveau airport
        airport_features AS (
            SELECT
                origin_airport,
                year,
                month,
                lagInFrame(airport_mean_delay, 1) OVER w AS airport_lag1_raw,
                avg(airport_mean_delay) OVER (
                    PARTITION BY origin_airport 
                    ORDER BY year, month 
                    ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
                ) AS airport_lag3_mean_raw,
                avg(airport_mean_delay) OVER (
                    PARTITION BY origin_airport 
                    ORDER BY year, month 
                    ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                ) AS airport_expanding_mean_raw
            FROM temp_airport_means
            WINDOW w AS (PARTITION BY origin_airport ORDER BY year, month)
        )
        SELECT
            pf.carrier,
            pf.origin_airport,
            pf.year,
            pf.month,
            
            -- Encoding stable (hash déterministe)
            toUInt32(cityHash64(pf.carrier) % 100000) AS carrier_id,
            toUInt32(cityHash64(pf.origin_airport) % 100000) AS airport_id,
            
            -- Target
            pf.delay_rate,
            CASE WHEN pf.delay_rate > 0.20 THEN 1 ELSE 0 END AS is_delayed,
            
            -- Volume
            pf.arr_flights,
            pf.arr_del15,
            toFloat32(log(pf.arr_flights + 1)) AS log_arr_flights,
            
            -- Pair lag features (avec fallback sur delay_rate courant si NULL)
            toFloat32(ifNull(pf.pair_lag1_raw, pf.delay_rate)) AS pair_lag1,
            toFloat32(ifNull(pf.pair_lag3_mean_raw, pf.delay_rate)) AS pair_lag3_mean,
            toFloat32(ifNull(pf.pair_expanding_mean_raw, pf.delay_rate)) AS pair_expanding_mean,
            
            -- Airport lag features
            toFloat32(ifNull(af.airport_lag1_raw, pf.delay_rate)) AS airport_lag1,
            toFloat32(ifNull(af.airport_lag3_mean_raw, pf.delay_rate)) AS airport_lag3_mean,
            toFloat32(ifNull(af.airport_expanding_mean_raw, pf.delay_rate)) AS airport_expanding_mean,
            
            -- Carrier lag features
            toFloat32(ifNull(cf.carrier_lag1_raw, pf.delay_rate)) AS carrier_lag1,
            toFloat32(ifNull(cf.carrier_lag3_mean_raw, pf.delay_rate)) AS carrier_lag3_mean,
            toFloat32(ifNull(cf.carrier_expanding_mean_raw, pf.delay_rate)) AS carrier_expanding_mean,
            
            -- Encoding cyclique du mois
            toFloat32(sin(2 * pi() * pf.month / 12)) AS month_sin,
            toFloat32(cos(2 * pi() * pf.month / 12)) AS month_cos,
            
            -- Indicateurs saisonniers
            CASE WHEN pf.month IN (6, 7, 8) THEN 1 ELSE 0 END AS is_summer,
            CASE WHEN pf.month IN (12, 1, 2) THEN 1 ELSE 0 END AS is_winter,
            CASE WHEN pf.month IN (11, 12) THEN 1 ELSE 0 END AS is_holiday_season
            
        FROM pair_features pf
        LEFT JOIN carrier_features cf ON 
            pf.carrier = cf.carrier AND 
            pf.year = cf.year AND 
            pf.month = cf.month
        LEFT JOIN airport_features af ON 
            pf.origin_airport = af.origin_airport AND 
            pf.year = af.year AND 
            pf.month = af.month
    """)
    
    # Nettoyer les tables temporaires
    client.command("DROP TABLE IF EXISTS temp_base_agg")
    client.command("DROP TABLE IF EXISTS temp_carrier_means")
    client.command("DROP TABLE IF EXISTS temp_airport_means")
    
    gold_ml_count = client.command("SELECT count() FROM gold_ml_features")
    print(f"  [OK] Gold ML cree: {gold_ml_count:,} features (version v3)")
    
    # Stats
    stats = client.query("""
        SELECT 
            countDistinct(carrier) as carriers,
            countDistinct(origin_airport) as airports,
            min(year) as min_year,
            max(year) as max_year,
            avg(delay_rate) as avg_delay_rate,
            countIf(is_delayed = 1) as delayed_count,
            count() as total
        FROM gold_ml_features
    """).result_rows[0]
    
    print(f"\n  [..] Statistiques Gold ML v3:")
    print(f"     Carriers: {stats[0]}")
    print(f"     Airports: {stats[1]}")
    print(f"     Période: {stats[2]} - {stats[3]}")
    print(f"     Taux retard moyen: {stats[4]*100:.1f}%")
    print(f"     Lignes is_delayed=1: {stats[5]:,} / {stats[6]:,} ({stats[5]/stats[6]*100:.1f}%)")


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Medallion pipeline")
    parser.add_argument(
        "--silver-only",
        action="store_true",
        help="Rafraîchir uniquement Bronze → Silver (sans Gold)",
    )
    args = parser.parse_args()

    start = datetime.now()
    
    try:
        bronze_to_silver()
        if not args.silver_only:
            silver_to_gold_bi()
            silver_to_gold_ml()
        
        elapsed = (datetime.now() - start).total_seconds()
        
        print("\n" + "=" * 80)
        print("✅ PIPELINE MEDALLION TERMINÉ")
        print("=" * 80)
        print(f"   Temps total: {elapsed:.1f} secondes")
        print("\n   Tables créées:")

        tables = ['bronze_flights', 'silver_flights']
        if not args.silver_only:
            tables += ['gold_bi', 'gold_ml_features']

        for table in tables:
            count = client.command(f"SELECT count() FROM {table}")
            print(f"   • {table}: {count:,} lignes")
        
        if not args.silver_only:
            print("\n   Prochaines étapes:")
            print("   1. Power BI: Connecter à la table 'gold_bi'")
            print("   2. ML: Exécuter 'python scripts/train_model_2026.py'")
        
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        raise
