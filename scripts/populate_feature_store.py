"""
Feature Store Population Script
===============================
Populates MongoDB feature_store collection with pre-computed features
from ClickHouse gold_ml_features table.

This is a ONE-TIME sync script to enable MongoDB-only inference.

Usage:
    python scripts/populate_feature_store.py
"""
import os
import sys
from datetime import datetime

import clickhouse_connect
import numpy as np
import pandas as pd
from pymongo import MongoClient


def main():
    print("=" * 80)
    print("FEATURE STORE POPULATION - ClickHouse -> MongoDB")
    print("=" * 80)
    
    # =========================================================================
    # Connect to databases
    # =========================================================================
    print("\n[1/4] Connecting to databases...")
    
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
    
    print("[OK] ClickHouse and MongoDB connected")
    
    # =========================================================================
    # Load data from ClickHouse
    # =========================================================================
    print("\n[2/4] Loading data from ClickHouse gold_ml_features...")
    
    query = """
    SELECT 
        carrier,
        origin_airport as airport,
        year,
        month,
        delay_rate,
        arr_flights,
        arr_del15,
        is_summer,
        is_winter,
        is_holiday_season
    FROM gold_ml_features
    ORDER BY year, month, carrier, origin_airport
    """
    
    df = ch_client.query_df(query)
    print(f"[OK] Loaded {len(df):,} records")
    
    # =========================================================================
    # Compute lag features
    # =========================================================================
    print("\n[3/4] Computing lag features...")
    
    # Sort for temporal calculations
    df = df.sort_values(['carrier', 'airport', 'year', 'month'])
    
    # Period for sorting
    df['period'] = df['year'] * 12 + df['month']
    
    # Lag features per pair (carrier + airport)
    df['pair_lag1'] = df.groupby(['carrier', 'airport'])['delay_rate'].shift(1)
    df['pair_lag3_mean'] = df.groupby(['carrier', 'airport'])['delay_rate'].transform(
        lambda x: x.shift(1).rolling(3, min_periods=1).mean()
    )
    df['pair_expanding_mean'] = df.groupby(['carrier', 'airport'])['delay_rate'].transform(
        lambda x: x.shift(1).expanding(min_periods=1).mean()
    )
    
    # Airport-level lags
    df['airport_lag1'] = df.groupby('airport')['delay_rate'].shift(1)
    df['airport_lag3_mean'] = df.groupby('airport')['delay_rate'].transform(
        lambda x: x.shift(1).rolling(3, min_periods=1).mean()
    )
    df['airport_expanding_mean'] = df.groupby('airport')['delay_rate'].transform(
        lambda x: x.shift(1).expanding(min_periods=1).mean()
    )
    
    # Carrier-level lags
    df['carrier_lag1'] = df.groupby('carrier')['delay_rate'].shift(1)
    df['carrier_lag3_mean'] = df.groupby('carrier')['delay_rate'].transform(
        lambda x: x.shift(1).rolling(3, min_periods=1).mean()
    )
    df['carrier_expanding_mean'] = df.groupby('carrier')['delay_rate'].transform(
        lambda x: x.shift(1).expanding(min_periods=1).mean()
    )
    
    # Log of arr_flights
    df['log_arr_flights'] = np.log1p(df['arr_flights'].clip(lower=0))
    
    # Seasonality sin/cos
    df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
    df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
    
    # Fill NaN with global mean
    global_mean = df['delay_rate'].mean()
    lag_cols = [
        'pair_lag1', 'pair_lag3_mean', 'pair_expanding_mean',
        'airport_lag1', 'airport_lag3_mean', 'airport_expanding_mean',
        'carrier_lag1', 'carrier_lag3_mean', 'carrier_expanding_mean'
    ]
    
    for col in lag_cols:
        df[col] = df[col].fillna(global_mean)
    
    print(f"[OK] Features computed: {len(df.columns)} columns")
    
    # =========================================================================
    # Insert into MongoDB
    # =========================================================================
    print("\n[4/4] Inserting into MongoDB feature_store...")
    
    # Clear existing data
    feature_store.delete_many({})
    print("   Cleared existing feature_store")
    
    # Prepare documents
    feature_columns = [
        'year', 'month', 'month_sin', 'month_cos',
        'is_summer', 'is_winter', 'is_holiday_season',
        'arr_flights', 'log_arr_flights',
        'pair_lag1', 'pair_lag3_mean', 'pair_expanding_mean',
        'airport_lag1', 'airport_lag3_mean', 'airport_expanding_mean',
        'carrier_lag1', 'carrier_lag3_mean', 'carrier_expanding_mean',
        'delay_rate'  # Keep for reference
    ]
    
    documents = []
    for _, row in df.iterrows():
        doc = {
            "carrier": row['carrier'],
            "airport": row['airport'],
            "year": int(row['year']),
            "month": int(row['month']),
            "features": {col: float(row[col]) if isinstance(row[col], (int, float, np.number)) else row[col] 
                        for col in feature_columns if col in row},
            "created_at": datetime.utcnow().isoformat() + "Z"
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
    # Summary
    # =========================================================================
    print("\n" + "=" * 80)
    print("[SUCCESS] FEATURE STORE POPULATION COMPLETE")
    print("=" * 80)
    
    # Verification
    count = feature_store.count_documents({})
    sample = feature_store.find_one()
    
    print(f"""
Summary:
   - Total documents: {count:,}
   - Carriers: {df['carrier'].nunique()}
   - Airports: {df['airport'].nunique()}
   - Year range: {df['year'].min()} - {df['year'].max()}
   
Sample document:
   - Carrier: {sample['carrier']}
   - Airport: {sample['airport']}
   - Year/Month: {sample['year']}/{sample['month']}
   - Features: {len(sample['features'])} columns
   
Ready for inference!
""")


if __name__ == "__main__":
    main()
