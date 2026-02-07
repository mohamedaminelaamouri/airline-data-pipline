#!/usr/bin/env python3
"""
Feature Store Validation Script
===============================
Validates that training and serving use identical features.

Checks:
1. Schema match: gold_ml_features has all required columns
2. Feature parity: Training FEATURE_COLUMNS == Serving FEATURE_COLUMNS  
3. MongoDB sync: feature_store count matches ClickHouse
4. Sample data integrity

Usage:
    python scripts/validate_feature_store.py
"""
import os
import sys
import json
from pathlib import Path

import clickhouse_connect
from pymongo import MongoClient


# ===========================================================================
# EXPECTED FEATURE COLUMNS (single source of truth)
# ===========================================================================
EXPECTED_FEATURE_COLUMNS = [
    "year", "month", "month_sin", "month_cos",
    "is_summer", "is_winter", "is_holiday_season",
    "carrier_id", "airport_id",
    "arr_flights", "log_arr_flights",
    "pair_lag1", "pair_lag3_mean", "pair_expanding_mean",
    "airport_lag1", "airport_lag3_mean", "airport_expanding_mean",
    "carrier_lag1", "carrier_lag3_mean", "carrier_expanding_mean",
]

REQUIRED_CLICKHOUSE_COLUMNS = EXPECTED_FEATURE_COLUMNS + [
    "carrier", "origin_airport", "delay_rate", "is_delayed", "arr_del15"
]


def validate_clickhouse_schema(client):
    """Check that gold_ml_features has all required columns."""
    print("\n[1/4] Validating ClickHouse schema...")
    
    columns = client.query("DESCRIBE gold_ml_features").result_rows
    column_names = {col[0] for col in columns}
    
    missing = set(REQUIRED_CLICKHOUSE_COLUMNS) - column_names
    
    if missing:
        print(f"   ❌ Missing columns: {sorted(missing)}")
        return False
    
    print(f"   ✅ All {len(REQUIRED_CLICKHOUSE_COLUMNS)} required columns present")
    
    # Check data types for critical columns
    col_types = {col[0]: col[1] for col in columns}
    
    type_checks = {
        'carrier_id': 'UInt32',
        'airport_id': 'UInt32',
        'is_delayed': 'UInt8',
        'delay_rate': 'Float32',
    }
    
    for col, expected_type in type_checks.items():
        actual_type = col_types.get(col, 'MISSING')
        if expected_type not in actual_type:
            print(f"   ⚠️ Column {col}: expected {expected_type}, got {actual_type}")
    
    return True


def validate_feature_parity():
    """Check that training and serving use same features."""
    print("\n[2/4] Validating feature parity (training == serving)...")
    
    project_root = Path(__file__).parent.parent
    
    # Try to import serving features
    sys.path.insert(0, str(project_root))
    try:
        from ml_api.utils.ml_inference import FEATURE_COLUMNS as SERVING_FEATURES
    except ImportError as e:
        print(f"   ⚠️ Could not import serving features: {e}")
        SERVING_FEATURES = None
    
    # Try to read training features from config
    train_config_path = project_root / "ml" / "models" / "runs" / "production" / "feature_config.json"
    if train_config_path.exists():
        with open(train_config_path) as f:
            train_config = json.load(f)
        TRAINING_FEATURES = train_config.get('feature_columns', [])
    else:
        print(f"   ⚠️ Training config not found at {train_config_path}")
        TRAINING_FEATURES = EXPECTED_FEATURE_COLUMNS  # Use expected
    
    # Compare
    if SERVING_FEATURES and TRAINING_FEATURES:
        if list(SERVING_FEATURES) == list(TRAINING_FEATURES):
            print(f"   ✅ Feature parity verified ({len(SERVING_FEATURES)} features)")
            return True
        else:
            diff = set(TRAINING_FEATURES) ^ set(SERVING_FEATURES)
            print(f"   ❌ Feature mismatch: {diff}")
            return False
    
    # Compare against expected
    if SERVING_FEATURES:
        if list(SERVING_FEATURES) == EXPECTED_FEATURE_COLUMNS:
            print(f"   ✅ Serving features match expected ({len(SERVING_FEATURES)})")
            return True
        else:
            diff = set(EXPECTED_FEATURE_COLUMNS) ^ set(SERVING_FEATURES)
            print(f"   ❌ Serving mismatch vs expected: {diff}")
            return False
    
    print("   ⚠️ Could not verify feature parity (imports failed)")
    return False


def validate_mongodb_sync(ch_client, mongo_collection):
    """Check MongoDB feature_store matches ClickHouse."""
    print("\n[3/4] Validating MongoDB sync with ClickHouse...")
    
    ch_count = ch_client.command("SELECT count() FROM gold_ml_features")
    mongo_count = mongo_collection.count_documents({})
    
    if mongo_count == 0:
        print(f"   ⚠️ MongoDB feature_store is empty. Run populate_feature_store.py")
        return False
    
    if abs(ch_count - mongo_count) < 10:
        print(f"   ✅ Counts match: ClickHouse={ch_count:,}, MongoDB={mongo_count:,}")
    else:
        print(f"   ⚠️ Count mismatch: ClickHouse={ch_count:,}, MongoDB={mongo_count:,}")
        return False
    
    # Check sample document has expected features
    sample = mongo_collection.find_one()
    if sample and 'features' in sample:
        stored_features = set(sample['features'].keys())
        expected = set(EXPECTED_FEATURE_COLUMNS + ['delay_rate', 'is_delayed'])
        missing = expected - stored_features
        
        if missing:
            print(f"   ⚠️ MongoDB sample missing features: {missing}")
            return False
        else:
            print(f"   ✅ MongoDB sample has all {len(stored_features)} features")
    
    return True


def validate_sample_data(ch_client):
    """Validate sample data integrity."""
    print("\n[4/4] Validating sample data integrity...")
    
    # Check for nulls in critical features
    query = """
    SELECT
        count() as total,
        countIf(carrier_id IS NULL) as null_carrier_id,
        countIf(airport_id IS NULL) as null_airport_id,
        countIf(pair_lag1 IS NULL) as null_pair_lag1,
        avg(delay_rate) as avg_delay_rate,
        avg(is_delayed) as avg_is_delayed
    FROM gold_ml_features
    """
    result = ch_client.query(query).result_rows[0]
    
    total, null_carrier, null_airport, null_lag, avg_delay, avg_delayed = result
    
    print(f"   Total records: {total:,}")
    print(f"   Null carrier_id: {null_carrier}")
    print(f"   Null airport_id: {null_airport}")
    print(f"   Null pair_lag1: {null_lag}")
    print(f"   Avg delay_rate: {avg_delay:.4f}")
    print(f"   Avg is_delayed: {avg_delayed:.4f}")
    
    if null_carrier > 0 or null_airport > 0:
        print("   ❌ Critical null values detected")
        return False
    
    # Check is_delayed threshold
    threshold_check = ch_client.query("""
        SELECT 
            countIf(delay_rate > 0.20 AND is_delayed = 0) as wrong_0,
            countIf(delay_rate <= 0.20 AND is_delayed = 1) as wrong_1
        FROM gold_ml_features
    """).result_rows[0]
    
    if threshold_check[0] > 0 or threshold_check[1] > 0:
        print(f"   ❌ is_delayed threshold mismatch: {threshold_check}")
        return False
    
    print("   ✅ Data integrity verified")
    return True


def main():
    print("=" * 70)
    print("FEATURE STORE VALIDATION")
    print("=" * 70)
    
    # Connect to databases
    ch_client = clickhouse_connect.get_client(
        host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
        port=int(os.getenv('CLICKHOUSE_HTTP_PORT', '8123')),
        database='airline_data'
    )
    
    mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
    mongo_client = MongoClient(mongo_uri)
    feature_store = mongo_client['airline_ml']['feature_store']
    
    # Run validations
    results = []
    results.append(("ClickHouse Schema", validate_clickhouse_schema(ch_client)))
    results.append(("Feature Parity", validate_feature_parity()))
    results.append(("MongoDB Sync", validate_mongodb_sync(ch_client, feature_store)))
    results.append(("Data Integrity", validate_sample_data(ch_client)))
    
    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("ALL VALIDATIONS PASSED!")
    else:
        print("SOME VALIDATIONS FAILED - Please review above")
    print("=" * 70)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
