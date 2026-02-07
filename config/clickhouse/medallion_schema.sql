-- ============================================================================
-- MEDALLION ARCHITECTURE: Bronze → Silver → Gold
-- ============================================================================
--
--  ┌─────────────┐      ┌─────────────┐      ┌─────────────────────────┐
--  │   BRONZE    │─────▶│   SILVER    │─────▶│          GOLD           │
--  │  (Raw Data) │      │  (Cleaned)  │      │  ┌─────────┬─────────┐  │
--  │             │      │             │      │  │ gold_bi │ gold_ml │  │
--  │ • Nulls OK  │      │ • NOT NULL  │      │  │(PowerBI)│(XGBoost)│  │
--  │ • Doublons  │      │ • Validé    │      │  └─────────┴─────────┘  │
--  │ • Erreurs   │      │ • Typé      │      │           │             │
--  └─────────────┘      └─────────────┘      └───────────┼─────────────┘
--                                                        ▼
--                                               ┌─────────────────┐
--                                               │  ml_predictions │
--                                               └─────────────────┘
--
-- ============================================================================

CREATE DATABASE IF NOT EXISTS airline_data;
USE airline_data;

-- ============================================================================
-- BRONZE: Données brutes (telles quelles du CSV)
-- ============================================================================
-- Objectif: Conserver les données originales sans transformation
-- Source: CSV importé via NiFi/Kafka ou script Python
-- ============================================================================

CREATE TABLE IF NOT EXISTS bronze_flights (
    -- Identifiant
    id String DEFAULT generateUUIDv4(),
    
    -- Données temporelles (peuvent être NULL)
    year Nullable(UInt16),
    month Nullable(UInt8),
    
    -- Compagnie (peuvent être NULL ou vides)
    carrier Nullable(String),
    carrier_name Nullable(String),
    
    -- Aéroport (peuvent être NULL ou vides)
    airport Nullable(String),
    airport_name Nullable(String),
    
    -- Métriques de vol (peuvent être NULL)
    arr_flights Nullable(UInt32),
    arr_del15 Nullable(UInt32),
    carrier_ct Nullable(Float32),
    weather_ct Nullable(Float32),
    nas_ct Nullable(Float32),
    security_ct Nullable(Float32),
    late_aircraft_ct Nullable(Float32),
    arr_cancelled Nullable(UInt32),
    arr_diverted Nullable(UInt32),
    arr_delay Nullable(Float32),
    carrier_delay Nullable(Float32),
    weather_delay Nullable(Float32),
    nas_delay Nullable(Float32),
    security_delay Nullable(Float32),
    late_aircraft_delay Nullable(Float32),
    
    -- Métadonnées d'ingestion
    source_file String DEFAULT '',
    ingestion_timestamp DateTime DEFAULT now()
    
) ENGINE = MergeTree()
ORDER BY (ingestion_timestamp, id)
SETTINGS index_granularity = 8192;

-- ============================================================================
-- SILVER: Données nettoyées et validées
-- ============================================================================
-- Objectif: Données propres, typées, sans NULL, sans doublons
-- Transformations:
--   • Suppression des lignes avec NULL sur colonnes critiques
--   • Déduplication par (year, month, carrier, airport)
--   • Calcul du delay_rate
--   • Validation des plages de valeurs
-- ============================================================================

CREATE TABLE IF NOT EXISTS silver_flights (
    -- Identifiant unique
    id String,
    
    -- Données temporelles (validées)
    year UInt16,
    month UInt8,
    
    -- Compagnie (nettoyée)
    carrier String,
    carrier_name String,
    
    -- Aéroport (nettoyé)
    airport String,
    airport_name String,
    
    -- Métriques de vol (validées, défaut 0)
    arr_flights UInt32,
    arr_del15 UInt32,
    
    -- Taux de retard calculé
    delay_rate Float32,  -- = arr_del15 / arr_flights (0 si arr_flights = 0)
    
    -- Causes de retard
    carrier_ct Float32 DEFAULT 0,
    weather_ct Float32 DEFAULT 0,
    nas_ct Float32 DEFAULT 0,
    security_ct Float32 DEFAULT 0,
    late_aircraft_ct Float32 DEFAULT 0,
    
    -- Autres métriques
    arr_cancelled UInt32 DEFAULT 0,
    arr_diverted UInt32 DEFAULT 0,
    arr_delay Float32 DEFAULT 0,
    
    -- Qualité des données
    data_quality_score Float32 DEFAULT 1.0,  -- 0-1, basé sur complétude
    
    -- Métadonnées
    bronze_id String,  -- Référence vers bronze
    cleaned_at DateTime DEFAULT now()
    
) ENGINE = ReplacingMergeTree(cleaned_at)
ORDER BY (year, month, carrier, airport)
PARTITION BY year
SETTINGS index_granularity = 8192;

-- ============================================================================
-- GOLD BI: Données agrégées pour Power BI / Reporting
-- ============================================================================
-- Objectif: KPIs précalculés pour visualisation rapide
-- Granularité: Par carrier, airport, année, mois
-- Usage: Power BI, Dashboards, Reports
-- ============================================================================

CREATE TABLE IF NOT EXISTS gold_bi (
    -- Dimensions
    carrier String,
    carrier_name String,
    airport String,
    airport_name String,
    year UInt16,
    month UInt8,
    
    -- KPIs principaux
    total_flights UInt32,
    delayed_flights UInt32,
    delay_rate Float32,              -- % de vols en retard
    on_time_rate Float32,            -- % de vols à l'heure (1 - delay_rate)
    
    -- KPIs détaillés par cause
    carrier_delay_pct Float32,       -- % retards dus à la compagnie
    weather_delay_pct Float32,       -- % retards météo
    nas_delay_pct Float32,           -- % retards système national
    security_delay_pct Float32,      -- % retards sécurité
    late_aircraft_delay_pct Float32, -- % retards avion précédent
    
    -- Métriques de volume
    cancelled_flights UInt32,
    diverted_flights UInt32,
    cancel_rate Float32,
    divert_rate Float32,
    
    -- Métriques de temps (en minutes)
    total_delay_minutes Float32,
    avg_delay_per_flight Float32,
    avg_delay_per_delayed Float32,
    
    -- Comparaisons temporelles (vs mois précédent)
    delay_rate_mom_change Float32,   -- Month-over-Month change
    flights_mom_change Float32,
    
    -- Comparaisons annuelles (vs même mois année précédente)
    delay_rate_yoy_change Float32,   -- Year-over-Year change
    flights_yoy_change Float32,
    
    -- Rankings
    carrier_rank_by_delay UInt16,    -- 1 = meilleur (moins de retards)
    airport_rank_by_delay UInt16,
    
    -- Métadonnées
    created_at DateTime DEFAULT now(),
    updated_at DateTime DEFAULT now()
    
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (year, month, carrier, airport)
PARTITION BY year
SETTINGS index_granularity = 8192;

-- ============================================================================
-- GOLD ML: Features pour Machine Learning (Single Source of Truth)
-- ============================================================================
-- Objectif: Features engineered pour entraînement XGBoost
-- Granularité: Par carrier, airport, année, mois
-- Usage: Training ML, Feature Store MongoDB, Prédictions
--
-- IMPORTANT: Cette table est la SOURCE UNIQUE de vérité pour les features ML.
-- Aucun feature engineering ne doit être fait en Python.
-- ============================================================================

CREATE TABLE IF NOT EXISTS gold_ml_features (
    -- =================================================================
    -- IDENTIFIANTS (clés primaires)
    -- =================================================================
    carrier String,                       -- Code compagnie (ex: 'AA', 'DL')
    origin_airport String,                -- Code aéroport (ex: 'ATL', 'ORD')
    year UInt16,                          -- Année (2003-2026)
    month UInt8,                          -- Mois (1-12)
    
    -- =================================================================
    -- ENCODAGE STABLE (remplace LabelEncoder)
    -- =================================================================
    -- Hash déterministe pour encoding catégoriel, stable entre sessions
    carrier_id UInt32,                    -- cityHash64(carrier) % 100000
    airport_id UInt32,                    -- cityHash64(origin_airport) % 100000
    
    -- =================================================================
    -- TARGET VARIABLE (variable à prédire)
    -- =================================================================
    delay_rate Float32,                   -- arr_del15 / arr_flights
    is_delayed UInt8,                     -- 1 si delay_rate > 0.20 (seuil ML)
    
    -- =================================================================
    -- FEATURES DE VOLUME
    -- =================================================================
    arr_flights UInt32,                   -- Nombre total de vols arrivés
    arr_del15 UInt32,                     -- Nombre de vols en retard (>15 min)
    log_arr_flights Float32,              -- log(1 + arr_flights) - normalisation
    
    -- =================================================================
    -- LAG FEATURES: Couple (Carrier + Airport)
    -- Historique des retards pour cette paire spécifique
    -- =================================================================
    pair_lag1 Float32,                    -- delay_rate du mois M-1
    pair_lag3_mean Float32,               -- Moyenne delay_rate des 3 derniers mois
    pair_expanding_mean Float32,          -- Moyenne cumulative historique
    
    -- =================================================================
    -- LAG FEATURES: Niveau Airport
    -- Tendance globale de l'aéroport
    -- =================================================================
    airport_lag1 Float32,                 -- delay_rate aéroport mois M-1
    airport_lag3_mean Float32,            -- Moyenne aéroport 3 derniers mois
    airport_expanding_mean Float32,       -- Moyenne aéroport historique
    
    -- =================================================================
    -- LAG FEATURES: Niveau Carrier
    -- Tendance globale de la compagnie
    -- =================================================================
    carrier_lag1 Float32,                 -- delay_rate carrier mois M-1
    carrier_lag3_mean Float32,            -- Moyenne carrier 3 derniers mois
    carrier_expanding_mean Float32,       -- Moyenne carrier historique
    
    -- =================================================================
    -- FEATURES TEMPORELLES / CYCLIQUES
    -- Encodage cyclique pour capturer la saisonnalité
    -- =================================================================
    month_sin Float32,                    -- sin(2π × month/12) - cycle mois
    month_cos Float32,                    -- cos(2π × month/12) - cycle mois
    
    -- =================================================================
    -- FEATURES SAISONNIÈRES (One-Hot)
    -- Indicateurs de périodes à haut risque de retards
    -- =================================================================
    is_summer UInt8,                      -- 1 si mois ∈ {6, 7, 8}
    is_winter UInt8,                      -- 1 si mois ∈ {12, 1, 2}
    is_holiday_season UInt8,              -- 1 si mois ∈ {11, 12}
    
    -- =================================================================
    -- MÉTADONNÉES
    -- =================================================================
    feature_version String DEFAULT 'v3', -- Version des features
    created_at DateTime DEFAULT now()     -- Timestamp de création
    
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY (carrier, origin_airport, year, month)
PARTITION BY year
SETTINGS index_granularity = 8192;

-- ============================================================================
-- ML PREDICTIONS: Résultats des prédictions
-- ============================================================================
-- Objectif: Stocker les prédictions du modèle pour 2026
-- Source: Script train_model_2026.py
-- Usage: API FastAPI, Dashboard React
-- ============================================================================

CREATE TABLE IF NOT EXISTS ml_predictions (
    -- Identifiants
    carrier String,
    origin_airport String,
    year UInt16,
    month UInt8,
    
    -- Prédictions
    predicted_delay_rate Float32,
    prediction_lower Float32,        -- Intervalle confiance bas
    prediction_upper Float32,        -- Intervalle confiance haut
    
    -- Score de risque
    risk_score Float32,              -- 0-1, basé sur predicted_delay_rate
    risk_category String,            -- 'low', 'medium', 'high'
    
    -- Volume estimé
    arr_flights UInt32,
    
    -- Explicabilité (SHAP values)
    top_feature_1 String,
    top_feature_1_importance Float32,
    top_feature_2 String,
    top_feature_2_importance Float32,
    top_feature_3 String,
    top_feature_3_importance Float32,
    
    -- Métadonnées modèle
    model_version String,
    model_type String DEFAULT 'xgboost',
    confidence Float32,
    
    -- Timestamps
    prediction_date DateTime DEFAULT now(),
    created_at DateTime DEFAULT now()
    
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY (carrier, origin_airport, year, month)
PARTITION BY year
SETTINGS index_granularity = 8192;

