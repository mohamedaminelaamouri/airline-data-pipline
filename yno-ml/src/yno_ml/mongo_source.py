"""
MongoDB Data Source for ML Pipeline
Loads aggregated airline delay data from MongoDB instead of CSV.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd
from pymongo import MongoClient

from .schema import validate_required_columns


@dataclass(frozen=True)
class MongoSource:
    """MongoDB connection configuration"""
    host: str = "localhost"
    port: int = 27017
    database: str = "airline_cache"
    collection: str = "monthly_trends"
    
    # Optional filters
    min_year: Optional[int] = None
    max_year: Optional[int] = None


def load_aggregated_mongo(source: MongoSource) -> pd.DataFrame:
    """
    Load aggregated airline delay data from MongoDB.
    
    Expected MongoDB document structure (from monthly_trends):
    {
        "_id": "2025-01",
        "year": 2025,
        "month": 1,
        "total_flights": 1940142,
        "delayed_flights": 411217,
        "cancelled_flights": 12345,
        "diverted_flights": 678,
        "delay_rate": 21.18,
        "avg_delay_minutes": 15.23
    }
    
    For per-carrier or per-airport data, we need to query delay_causes collection
    which has carrier and airport breakdowns.
    
    Args:
        source: MongoDB connection configuration
        
    Returns:
        DataFrame with required columns: year, month, carrier, airport, arr_flights, arr_del15
    """
    
    client = MongoClient(source.host, source.port, serverSelectionTimeoutMS=5000)
    
    try:
        db = client[source.database]
        
        # Build query filter
        query = {}
        if source.min_year is not None:
            query['year'] = {'$gte': source.min_year}
        if source.max_year is not None:
            if 'year' in query:
                query['year']['$lte'] = source.max_year
            else:
                query['year'] = {'$lte': source.max_year}
        
        # Load from delay_causes collection (has carrier/airport breakdown)
        # This is better than monthly_trends which is aggregated globally
        collection = db['delay_causes']
        
        # Query MongoDB
        cursor = collection.find(query)
        data = list(cursor)
        
        if not data:
            raise ValueError(
                f"No data found in MongoDB collection '{source.collection}' "
                f"with filters: {query}"
            )
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Check if we have the minimum required fields
        required_mongo_fields = ['carrier', 'airport', 'total_flights']
        missing = [f for f in required_mongo_fields if f not in df.columns]
        if missing:
            raise ValueError(
                f"MongoDB collection missing required fields: {missing}. "
                f"Available columns: {df.columns.tolist()}"
            )
        
        # Extract year/month from _id if not present
        if 'year' not in df.columns or 'month' not in df.columns:
            # Try to parse from carrier_name or airport_name if they contain date info
            # Or use a default approach
            if '_id' in df.columns:
                # If _id is like "ORD-AA", we can't extract date
                # Need to query a different way
                pass
        
        # Map MongoDB fields to expected ML pipeline format
        result = pd.DataFrame({
            'year': df.get('year', pd.NA),
            'month': df.get('month', pd.NA),
            'carrier': df['carrier'].astype(str),
            'carrier_name': df.get('carrier_name', df['carrier']).astype(str),
            'airport': df['airport'].astype(str),
            'airport_name': df.get('airport_name', df['airport']).astype(str),
            'arr_flights': pd.to_numeric(df['total_flights'], errors='coerce').fillna(0),
            # Calculate arr_del15 from delay_rate if available
            'arr_del15': pd.NA,  # Will be calculated below
        })
        
        # If we don't have year/month, we need to get it from a different source
        # Query monthly_trends to get the time dimension
        if result['year'].isna().any() or result['month'].isna().any():
            # This means delay_causes doesn't have temporal info
            # We need to join with another collection or use ClickHouse directly
            raise ValueError(
                "MongoDB delay_causes collection doesn't contain year/month information. "
                "Consider querying ClickHouse directly or restructuring MongoDB cache."
            )
        
        # Calculate arr_del15 from delay statistics if not present
        if 'arr_del15' not in df.columns or df['arr_del15'].isna().all():
            # Use delay_rate if available
            if 'delay_rate' in df.columns:
                result['arr_del15'] = (
                    result['arr_flights'] * df['delay_rate'] / 100.0
                ).round().astype('Int64')
            else:
                # Calculate from delay minutes
                carrier_delay = pd.to_numeric(df.get('carrier_delay_minutes', 0), errors='coerce').fillna(0)
                weather_delay = pd.to_numeric(df.get('weather_delay_minutes', 0), errors='coerce').fillna(0)
                nas_delay = pd.to_numeric(df.get('nas_delay_minutes', 0), errors='coerce').fillna(0)
                security_delay = pd.to_numeric(df.get('security_delay_minutes', 0), errors='coerce').fillna(0)
                late_aircraft_delay = pd.to_numeric(df.get('late_aircraft_delay_minutes', 0), errors='coerce').fillna(0)
                
                total_delay_minutes = (
                    carrier_delay + weather_delay + nas_delay + 
                    security_delay + late_aircraft_delay
                )
                
                # Rough estimate: assume avg 60 min per delayed flight
                result['arr_del15'] = (total_delay_minutes / 60.0).round().astype('Int64')
        else:
            result['arr_del15'] = pd.to_numeric(df['arr_del15'], errors='coerce').fillna(0).astype('Int64')
        
        # Keep only required columns for ML pipeline
        result = result[['year', 'month', 'carrier', 'carrier_name', 'airport', 'airport_name', 'arr_flights', 'arr_del15']]
        
        # Remove rows with missing critical data
        result = result.dropna(subset=['year', 'month', 'carrier', 'airport'])
        result = result[result['arr_flights'] > 0]
        
        # Validate schema
        validate_required_columns(result.columns.tolist())
        
        return result
        
    finally:
        client.close()


def load_from_clickhouse_via_pymongo(
    host: str = "localhost",
    port: int = 8123,
    database: str = "airline_data",
    min_year: Optional[int] = None,
    max_year: Optional[int] = None,
) -> pd.DataFrame:
    """
    Alternative: Load directly from ClickHouse using HTTP interface.
    This is more reliable than MongoDB for ML training since ClickHouse
    has the complete temporal data.
    
    This function is a fallback if MongoDB doesn't have proper temporal indexing.
    """
    import clickhouse_connect
    
    client = clickhouse_connect.get_client(host=host, port=port, database=database)
    
    query = """
        SELECT 
            year,
            month,
            carrier,
            carrier_name,
            airport,
            airport_name,
            arr_flights,
            arr_del15
        FROM flights
        WHERE 1=1
    """
    
    conditions = []
    if min_year is not None:
        conditions.append(f"AND year >= {min_year}")
    if max_year is not None:
        conditions.append(f"AND year <= {max_year}")
    
    if conditions:
        query += " " + " ".join(conditions)
    
    query += " ORDER BY year, month, carrier, airport"
    
    result = client.query(query)
    
    df = pd.DataFrame(result.result_rows, columns=result.column_names)
    
    # Validate schema
    validate_required_columns(df.columns.tolist())
    
    return df
