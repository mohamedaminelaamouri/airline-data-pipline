"""
MEDALLION PIPELINE: Bronze → Silver → Gold
==========================================
Transforme les données brutes en données prêtes pour BI et ML

Usage:
    python scripts/medallion_pipeline.py

Architecture:
    bronze_flights (raw) → silver_flights (clean) → gold_bi (PowerBI)
                                                  → gold_ml_features (XGBoost)
"""

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
print("MEDALLION PIPELINE: Bronze → Silver → Gold")
print("=" * 80)

# Connexion ClickHouse
client = clickhouse_connect.get_client(
    host=CLICKHOUSE_HOST,
    port=CLICKHOUSE_PORT,
    database=CLICKHOUSE_DB
)
print(f"✅ Connecté à ClickHouse: {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}")


# ============================================================================
# STEP 1: Bronze → Silver (Nettoyage)
# ============================================================================
def bronze_to_silver():
    """Nettoie les données brutes et les insère dans silver_flights."""
    print("\n" + "=" * 60)
    print("[1/3] BRONZE → SILVER: Nettoyage des données")
    print("=" * 60)
    
    # Vérifier si bronze a des données
    bronze_count = client.command("SELECT count() FROM bronze_flights")
    print(f"  📊 Lignes dans bronze_flights: {bronze_count:,}")
    
    if bronze_count == 0:
        print("  ⚠️  Bronze vide, chargement depuis airline_delays...")
        # Charger depuis la table existante airline_delays vers bronze
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
                security_delay, late_aircraft_delay, 'airline_delays_migration'
            FROM airline_delays
        """)
        bronze_count = client.command("SELECT count() FROM bronze_flights")
        print(f"  ✅ Migré {bronze_count:,} lignes vers bronze")
    
    # Nettoyer et insérer dans silver
    print("\n  🧹 Nettoyage en cours...")
    
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
    
    print(f"  ✅ Silver créé: {silver_count:,} lignes")
    print(f"  ❌ Lignes rejetées: {rejected:,} ({rejected/bronze_count*100:.1f}%)")
    
    # Stats de qualité
    stats = client.query("""
        SELECT 
            min(year) as min_year, max(year) as max_year,
            countDistinct(carrier) as carriers,
            countDistinct(airport) as airports,
            avg(delay_rate) as avg_delay
        FROM silver_flights
    """).result_rows[0]
    
    print(f"\n  📈 Statistiques Silver:")
    print(f"     Période: {stats[0]} - {stats[1]}")
    print(f"     Compagnies: {stats[2]}")
    print(f"     Aéroports: {stats[3]}")
    print(f"     Taux retard moyen: {stats[4]*100:.1f}%")


# ============================================================================
# STEP 2: Silver → Gold BI (Agrégations pour Power BI)
# ============================================================================
def silver_to_gold_bi():
    """Crée les KPIs agrégés pour Power BI."""
    print("\n" + "=" * 60)
    print("[2/3] SILVER → GOLD BI: Agrégations Power BI")
    print("=" * 60)
    
    client.command("TRUNCATE TABLE gold_bi")
    
    # Insertion des agrégations
    client.command("""
        INSERT INTO gold_bi (
            carrier, carrier_name, airport, airport_name, year, month,
            total_flights, delayed_flights, delay_rate, on_time_rate,
            carrier_delay_pct, weather_delay_pct, nas_delay_pct,
            security_delay_pct, late_aircraft_delay_pct,
            cancelled_flights, diverted_flights, cancel_rate, divert_rate,
            total_delay_minutes, avg_delay_per_flight, avg_delay_per_delayed
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
            END AS divert_rate,
            
            -- Temps de retard
            sum(arr_delay) AS total_delay_minutes,
            
            CASE WHEN sum(arr_flights) > 0 
                THEN sum(arr_delay) / sum(arr_flights) 
                ELSE 0 
            END AS avg_delay_per_flight,
            
            CASE WHEN sum(arr_del15) > 0 
                THEN sum(arr_delay) / sum(arr_del15) 
                ELSE 0 
            END AS avg_delay_per_delayed
            
        FROM silver_flights
        GROUP BY carrier, airport, year, month
    """)
    
    gold_bi_count = client.command("SELECT count() FROM gold_bi")
    print(f"  ✅ Gold BI créé: {gold_bi_count:,} agrégations")
    
    # Stats
    stats = client.query("""
        SELECT 
            avg(delay_rate) as avg_delay,
            max(delay_rate) as max_delay,
            sum(total_flights) as total_flights
        FROM gold_bi
    """).result_rows[0]
    
    print(f"\n  📈 Statistiques Gold BI:")
    print(f"     Taux retard moyen: {stats[0]*100:.1f}%")
    print(f"     Taux retard max: {stats[1]*100:.1f}%")
    print(f"     Vols totaux: {stats[2]:,}")


# ============================================================================
# STEP 3: Silver → Gold ML (Features pour Machine Learning)
# ============================================================================
def silver_to_gold_ml():
    """Crée les features ML avec lag et rolling averages."""
    print("\n" + "=" * 60)
    print("[3/3] SILVER → GOLD ML: Features Machine Learning")
    print("=" * 60)
    
    # D'abord, créer une table temporaire avec les agrégations de base
    print("  📊 Création des agrégations de base...")
    
    client.command("DROP TABLE IF EXISTS temp_base_agg")
    client.command("""
        CREATE TABLE temp_base_agg ENGINE = MergeTree() ORDER BY (carrier, airport, year, month) AS
        SELECT
            carrier,
            airport AS origin_airport,
            year,
            month,
            sum(arr_flights) AS arr_flights,
            sum(arr_del15) AS arr_del15,
            CASE WHEN sum(arr_flights) > 0 THEN sum(arr_del15) / sum(arr_flights) ELSE 0 END AS delay_rate
        FROM silver_flights
        GROUP BY carrier, airport, year, month
    """)
    
    # Créer les features avec lag
    print("  🔄 Calcul des features lag...")
    
    client.command("TRUNCATE TABLE gold_ml_features")
    client.command("""
        INSERT INTO gold_ml_features (
            carrier, origin_airport, year, month,
            delay_rate, arr_flights, arr_del15, log_flights,
            pair_lag1, pair_lag2, pair_lag3, pair_lag6, pair_lag12,
            month_sin, month_cos,
            is_summer, is_winter, is_holiday_season, is_spring_break
        )
        SELECT
            t1.carrier,
            t1.origin_airport,
            t1.year,
            t1.month,
            t1.delay_rate,
            t1.arr_flights,
            t1.arr_del15,
            log(t1.arr_flights + 1) AS log_flights,
            
            -- Lag features (mois précédents)
            COALESCE(
                (SELECT delay_rate FROM temp_base_agg t2 
                 WHERE t2.carrier = t1.carrier AND t2.origin_airport = t1.origin_airport
                 AND (t2.year * 12 + t2.month) = (t1.year * 12 + t1.month - 1)),
                t1.delay_rate
            ) AS pair_lag1,
            
            COALESCE(
                (SELECT delay_rate FROM temp_base_agg t2 
                 WHERE t2.carrier = t1.carrier AND t2.origin_airport = t1.origin_airport
                 AND (t2.year * 12 + t2.month) = (t1.year * 12 + t1.month - 2)),
                t1.delay_rate
            ) AS pair_lag2,
            
            COALESCE(
                (SELECT delay_rate FROM temp_base_agg t2 
                 WHERE t2.carrier = t1.carrier AND t2.origin_airport = t1.origin_airport
                 AND (t2.year * 12 + t2.month) = (t1.year * 12 + t1.month - 3)),
                t1.delay_rate
            ) AS pair_lag3,
            
            COALESCE(
                (SELECT delay_rate FROM temp_base_agg t2 
                 WHERE t2.carrier = t1.carrier AND t2.origin_airport = t1.origin_airport
                 AND (t2.year * 12 + t2.month) = (t1.year * 12 + t1.month - 6)),
                t1.delay_rate
            ) AS pair_lag6,
            
            COALESCE(
                (SELECT delay_rate FROM temp_base_agg t2 
                 WHERE t2.carrier = t1.carrier AND t2.origin_airport = t1.origin_airport
                 AND (t2.year * 12 + t2.month) = (t1.year * 12 + t1.month - 12)),
                t1.delay_rate
            ) AS pair_lag12,
            
            -- Features cycliques pour le mois
            sin(2 * pi() * t1.month / 12) AS month_sin,
            cos(2 * pi() * t1.month / 12) AS month_cos,
            
            -- Features saisonnières
            CASE WHEN t1.month IN (6, 7, 8) THEN 1 ELSE 0 END AS is_summer,
            CASE WHEN t1.month IN (12, 1, 2) THEN 1 ELSE 0 END AS is_winter,
            CASE WHEN t1.month IN (11, 12) THEN 1 ELSE 0 END AS is_holiday_season,
            CASE WHEN t1.month = 3 THEN 1 ELSE 0 END AS is_spring_break
            
        FROM temp_base_agg t1
    """)
    
    # Calculer les moyennes carrier et airport
    print("  📊 Calcul des rolling averages...")
    
    client.command("""
        ALTER TABLE gold_ml_features UPDATE
            carrier_lag1_mean = (
                SELECT avg(delay_rate) FROM temp_base_agg t2 
                WHERE t2.carrier = gold_ml_features.carrier 
                AND (t2.year * 12 + t2.month) = (gold_ml_features.year * 12 + gold_ml_features.month - 1)
            ),
            airport_lag1 = (
                SELECT avg(delay_rate) FROM temp_base_agg t2 
                WHERE t2.origin_airport = gold_ml_features.origin_airport 
                AND (t2.year * 12 + t2.month) = (gold_ml_features.year * 12 + gold_ml_features.month - 1)
            )
        WHERE 1=1
    """)
    
    # Nettoyer
    client.command("DROP TABLE IF EXISTS temp_base_agg")
    
    gold_ml_count = client.command("SELECT count() FROM gold_ml_features")
    print(f"  ✅ Gold ML créé: {gold_ml_count:,} features")
    
    # Stats
    stats = client.query("""
        SELECT 
            countDistinct(carrier) as carriers,
            countDistinct(origin_airport) as airports,
            min(year) as min_year,
            max(year) as max_year
        FROM gold_ml_features
    """).result_rows[0]
    
    print(f"\n  📈 Statistiques Gold ML:")
    print(f"     Carriers: {stats[0]}")
    print(f"     Airports: {stats[1]}")
    print(f"     Période: {stats[2]} - {stats[3]}")


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    start = datetime.now()
    
    try:
        bronze_to_silver()
        silver_to_gold_bi()
        silver_to_gold_ml()
        
        elapsed = (datetime.now() - start).total_seconds()
        
        print("\n" + "=" * 80)
        print("✅ PIPELINE MEDALLION TERMINÉ")
        print("=" * 80)
        print(f"   Temps total: {elapsed:.1f} secondes")
        print("\n   Tables créées:")
        
        for table in ['bronze_flights', 'silver_flights', 'gold_bi', 'gold_ml_features']:
            count = client.command(f"SELECT count() FROM {table}")
            print(f"   • {table}: {count:,} lignes")
        
        print("\n   Prochaines étapes:")
        print("   1. Power BI: Connecter à la table 'gold_bi'")
        print("   2. ML: Exécuter 'python scripts/train_model_2026.py'")
        
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        raise
