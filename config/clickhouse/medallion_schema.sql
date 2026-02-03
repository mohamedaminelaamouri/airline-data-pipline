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
-- GOLD ML: Features pour Machine Learning
-- ============================================================================
-- Objectif: Features engineered pour entraînement XGBoost
-- Granularité: Par carrier, airport, année, mois
-- Usage: Training ML, Prédictions
-- ============================================================================

CREATE TABLE IF NOT EXISTS gold_ml_features (
    -- Identifiants
    carrier String,
    origin_airport String,
    year UInt16,
    month UInt8,
    
    -- TARGET (variable à prédire)
    delay_rate Float32,
    
    -- Features de volume
    arr_flights UInt32,
    arr_del15 UInt32,
    log_flights Float32,             -- log(arr_flights + 1) pour normalisation
    
    -- Lag Features (historique du couple carrier-airport)
    pair_lag1 Float32,               -- delay_rate mois M-1
    pair_lag2 Float32,               -- delay_rate mois M-2
    pair_lag3 Float32,               -- delay_rate mois M-3
    pair_lag6 Float32,               -- delay_rate mois M-6
    pair_lag12 Float32,              -- delay_rate même mois année précédente
    
    -- Lag Features Carrier (moyenne de la compagnie)
    carrier_lag1_mean Float32,
    carrier_lag2_mean Float32,
    carrier_lag3_mean Float32,
    
    -- Lag Features Airport (moyenne de l'aéroport)
    airport_lag1 Float32,
    airport_lag2 Float32,
    airport_lag3 Float32,
    
    -- Rolling Averages (moyennes mobiles)
    carrier_rolling_3m Float32,      -- Moyenne 3 derniers mois carrier
    carrier_rolling_6m Float32,      -- Moyenne 6 derniers mois carrier
    carrier_rolling_12m Float32,     -- Moyenne 12 derniers mois carrier
    airport_rolling_3m Float32,
    airport_rolling_6m Float32,
    airport_rolling_12m Float32,
    pair_rolling_3m Float32,
    pair_rolling_6m Float32,
    
    -- Features temporelles
    month_sin Float32,               -- sin(2*pi*month/12) pour cyclicité
    month_cos Float32,               -- cos(2*pi*month/12)
    is_summer UInt8,                 -- Juin-Août
    is_winter UInt8,                 -- Décembre-Février
    is_holiday_season UInt8,         -- Nov-Dec (Thanksgiving, Noël)
    is_spring_break UInt8,           -- Mars
    
    -- Features de tendance
    carrier_trend_3m Float32,        -- Pente sur 3 mois
    airport_trend_3m Float32,
    
    -- Features d'interaction
    carrier_x_month Float32,         -- Interaction carrier performance × mois
    airport_x_month Float32,
    
    -- Métadonnées
    feature_version String DEFAULT 'v2',
    created_at DateTime DEFAULT now()
    
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

