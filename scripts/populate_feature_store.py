"""
Feature Store Population Script (v3)
====================================
Populates MongoDB feature_store collection from ClickHouse gold_ml_features.

IMPORTANT: This script performs a DIRECT COPY from ClickHouse.
No feature engineering is done in Python - all features are pre-computed in SQL.

Usage:
    python scripts/populate_feature_store.py
"""
import os
import sys
from datetime import datetime

import clickhouse_connect
from pymongo import MongoClient


# Feature columns that must exist in gold_ml_features
REQUIRED_FEATURE_COLUMNS = [
    'carrier', 'origin_airport', 'year', 'month',
    'carrier_id', 'airport_id',
    'delay_rate', 'is_delayed',
    'arr_flights', 'arr_del15', 'log_arr_flights',
    'pair_lag1', 'pair_lag3_mean', 'pair_expanding_mean',
    'airport_lag1', 'airport_lag3_mean', 'airport_expanding_mean',
    'carrier_lag1', 'carrier_lag3_mean', 'carrier_expanding_mean',
    'month_sin', 'month_cos',
    'is_summer', 'is_winter', 'is_holiday_season'
]

# Feature columns to store in MongoDB (for ML serving)
FEATURE_COLUMNS_FOR_MONGO = [
    'year', 'month', 'month_sin', 'month_cos',
    'is_summer', 'is_winter', 'is_holiday_season',
    'carrier_id', 'airport_id',
    'arr_flights', 'log_arr_flights',
    'pair_lag1', 'pair_lag3_mean', 'pair_expanding_mean',
    'airport_lag1', 'airport_lag3_mean', 'airport_expanding_mean',
    'carrier_lag1', 'carrier_lag3_mean', 'carrier_expanding_mean',
    'delay_rate', 'is_delayed'
]


def validate_schema(ch_client):
    """Validate that gold_ml_features has all required columns."""
    print("\n[1/5] Validating ClickHouse schema...")
    
    columns = ch_client.query("DESCRIBE gold_ml_features").result_rows
    column_names = {col[0] for col in columns}
    
    missing = set(REQUIRED_FEATURE_COLUMNS) - column_names
    if missing:
        raise ValueError(f"Missing columns in gold_ml_features: {sorted(missing)}")
    
    print(f"   ✅ Schema valid: {len(column_names)} columns found")
    return column_names


def main():
    print("=" * 80)
    print("FEATURE STORE POPULATION v3 - ClickHouse -> MongoDB")
    print("Direct copy, no Python feature engineering")
    print("=" * 80)
    
    # =========================================================================
    # Connect to databases
    # =========================================================================
    print("\n[2/5] Connecting to databases...")
    
    # ClickHouse
    ch_client = clickhouse_connect.get_client(
        host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
        port=int(os.getenv('CLICKHOUSE_HTTP_PORT', '8123')),
        database='airline_data'
    )
    
    # MongoDB
    mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
    mongo_client = MongoClient(mongo_uri)
    mongo_db = mongo_client['airline_ml']
    feature_store = mongo_db['feature_store']
    
    print("   ✅ ClickHouse and MongoDB connected")
    
    # =========================================================================
    # Validate schema
    # =========================================================================
    validate_schema(ch_client)
    
    # =========================================================================
    # Load data from ClickHouse (direct query, no Python processing)
    # =========================================================================
    print("\n[3/5] Loading features from ClickHouse gold_ml_features...")
    
    # Build column list for query
    columns_sql = ', '.join(REQUIRED_FEATURE_COLUMNS)
    
    query = f"""
    SELECT {columns_sql}
    FROM gold_ml_features
    ORDER BY year, month, carrier, origin_airport
    """
    
    result = ch_client.query(query)
    rows = result.result_rows
    column_names = result.column_names
    
    print(f"   ✅ Loaded {len(rows):,} records from ClickHouse")
    
    if len(rows) == 0:
        print("   ⚠️  No data in gold_ml_features. Run medallion_pipeline.py first.")
        return
    
    # =========================================================================
    # Insert into MongoDB
    # =========================================================================
    print("\n[4/5] Inserting into MongoDB feature_store...")
    
    # Clear existing data
    delete_result = feature_store.delete_many({})
    print(f"   Cleared {delete_result.deleted_count:,} existing documents")
    
    # Prepare documents
    documents = []
    col_idx = {name: i for i, name in enumerate(column_names)}
    
    for row in rows:
        # Build features dict from feature columns
        features = {}
        for col in FEATURE_COLUMNS_FOR_MONGO:
            if col in col_idx:
                val = row[col_idx[col]]
                # Convert to Python types
                if hasattr(val, 'item'):  # numpy types
                    val = val.item()
                features[col] = val
        
        doc = {
            "carrier": row[col_idx['carrier']],
            "airport": row[col_idx['origin_airport']],
            "year": int(row[col_idx['year']]),
            "month": int(row[col_idx['month']]),
            "features": features,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "feature_version": "v3"
        }
        documents.append(doc)
    
    # Batch insert
    batch_size = 5000
    total_inserted = 0
    
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        feature_store.insert_many(batch)
        total_inserted += len(batch)
        print(f"   Inserted {total_inserted:,} / {len(documents):,}")
    
    # Create indexes
    print("\n   Creating indexes...")
    feature_store.create_index(
        [("carrier", 1), ("airport", 1), ("year", -1), ("month", -1)],
        unique=True
    )
    feature_store.create_index([("year", -1), ("month", -1)])
    
    # =========================================================================
    # Validation
    # =========================================================================
    print("\n[5/5] Validating integrity...")
    
    ch_count = ch_client.command("SELECT count() FROM gold_ml_features")
    mongo_count = feature_store.count_documents({})
    
    if ch_count != mongo_count:
        print(f"   ⚠️  Count mismatch: ClickHouse={ch_count:,}, MongoDB={mongo_count:,}")
    else:
        print(f"   ✅ Count match: {mongo_count:,} documents")
    
    # Sample verification
    sample = feature_store.find_one()
    sample_features = sample.get('features', {}) if sample else {}
    expected_features = set(FEATURE_COLUMNS_FOR_MONGO)
    actual_features = set(sample_features.keys())
    
    if expected_features != actual_features:
        missing = expected_features - actual_features
        extra = actual_features - expected_features
        print(f"   ⚠️  Feature mismatch: missing={missing}, extra={extra}")
    else:
        print(f"   ✅ Feature columns match: {len(sample_features)} features per document")
    
    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 80)
    print("[SUCCESS] FEATURE STORE POPULATION COMPLETE")
    print("=" * 80)
    
    unique_carriers = feature_store.distinct("carrier")
    unique_airports = feature_store.distinct("airport")
    years = feature_store.distinct("year")
    
    print(f"""
Summary:
   - Total documents: {mongo_count:,}
   - Carriers: {len(unique_carriers)}
   - Airports: {len(unique_airports)}
   - Year range: {min(years)} - {max(years)}
   - Features per doc: {len(sample_features)}
   - Feature version: v3 (ClickHouse-computed)
   
Sample document:
   - Carrier: {sample['carrier']}
   - Airport: {sample['airport']}
   - Year/Month: {sample['year']}/{sample['month']}
   
Ready for ML serving!
""")


if __name__ == "__main__":
    main()
