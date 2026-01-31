#!/usr/bin/env python3
"""
Quick test to verify ML pipeline prerequisites
"""

import sys
import os

print("=" * 80)
print("ML Pipeline Prerequisites Test")
print("=" * 80)

# Test 1: ClickHouse connection
print("\n1️⃣  Testing ClickHouse connection...")
try:
    import clickhouse_connect
    client = clickhouse_connect.get_client(host='localhost', port=8123, database='airline_data')
    result = client.query("SELECT count(*) as cnt FROM flights")
    count = result.result_rows[0][0]
    print(f"   ✅ ClickHouse: {count:,} records in flights table")
    client.close()
except Exception as e:
    print(f"   ❌ ClickHouse error: {e}")
    sys.exit(1)

# Test 2: MongoDB connection
print("\n2️⃣  Testing MongoDB connection...")
try:
    from pymongo import MongoClient
    mongo_client = MongoClient(host='localhost', port=27017, serverSelectionTimeoutMS=5000)
    db = mongo_client['airline_cache']
    
    # Test collections
    collections = db.list_collection_names()
    print(f"   ✅ MongoDB: {len(collections)} collections")
    
    # Check monthly_trends
    if 'monthly_trends' in collections:
        count = db['monthly_trends'].count_documents({})
        print(f"      - monthly_trends: {count:,} documents")
    
    mongo_client.close()
except Exception as e:
    print(f"   ❌ MongoDB error: {e}")
    sys.exit(1)

# Test 3: yno-ml imports
print("\n3️⃣  Testing yno-ml imports...")
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'yno-ml', 'src'))
    
    from yno_ml.mongo_source import load_from_clickhouse_via_pymongo
    from yno_ml.train import train_from_csv, TrainConfig
    from yno_ml.alerting import score_month_to_csv
    from yno_ml.data import load_aggregated_csv
    
    print("   ✅ yno-ml imports successful")
    print("      - mongo_source")
    print("      - train")
    print("      - alerting")
    print("      - data")
except ImportError as e:
    print(f"   ❌ yno-ml import error: {e}")
    sys.exit(1)

# Test 4: ML dependencies
print("\n4️⃣  Testing ML dependencies...")
try:
    import pandas as pd
    import numpy as np
    import sklearn
    import xgboost as xgb
    from loguru import logger
    
    print("   ✅ ML dependencies installed")
    print(f"      - pandas {pd.__version__}")
    print(f"      - numpy {np.__version__}")
    print(f"      - scikit-learn {sklearn.__version__}")
    print(f"      - xgboost {xgb.__version__}")
except ImportError as e:
    print(f"   ❌ ML dependency error: {e}")
    print("   Run: pip install -r requirements.txt")
    sys.exit(1)

# Test 5: Extract small sample from ClickHouse
print("\n5️⃣  Testing data extraction...")
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'yno-ml', 'src'))
    from yno_ml.mongo_source import load_from_clickhouse_via_pymongo
    
    df = load_from_clickhouse_via_pymongo(
        host='localhost',
        port=8123,
        database='airline_data',
        min_year=2024,
        max_year=2025,
    )
    
    print(f"   ✅ Extracted {len(df):,} records")
    print(f"      - Columns: {', '.join(df.columns[:5])}...")
    print(f"      - Date range: {df['year'].min()}-{df['month'].min():02d} to {df['year'].max()}-{df['month'].max():02d}")
    print(f"      - Carriers: {df['carrier'].nunique()}")
    print(f"      - Airports: {df['airport'].nunique()}")
except Exception as e:
    print(f"   ❌ Data extraction error: {e}")
    sys.exit(1)

print("\n" + "=" * 80)
print("✅ All tests passed! Ready to run ML pipeline.")
print("=" * 80)
print("\nNext steps:")
print("  1. Run full training: make ml-train")
print("  2. Or manually: python scripts/ml_training_pipeline.py")
print("  3. Check results in MongoDB: ml_predictions, ml_alerts collections")
print()
