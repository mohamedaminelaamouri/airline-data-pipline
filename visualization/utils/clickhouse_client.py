"""
ClickHouse Client - Direct database access for analytics queries
Optimized for read-heavy operations on gold layer
"""
import clickhouse_connect
import pandas as pd
from typing import Optional, List, Dict, Any
import os

class ClickHouseClient:
    """
    Client for direct ClickHouse access from Streamlit
    Use for analytics queries on bronze/silver/gold tables
    """
    
    def __init__(self):
        self.host = os.getenv('CLICKHOUSE_HOST', 'localhost')
        self.port = int(os.getenv('CLICKHOUSE_HTTP_PORT', '8123'))
        self.database = os.getenv('CLICKHOUSE_DATABASE', 'airline_data')
        
        self.client = clickhouse_connect.get_client(
            host=self.host,
            port=self.port,
            database=self.database
        )
    
    def get_predictions(
        self, 
        risk_threshold: float = 0.0,
        carrier: Optional[str] = None,
        airport: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> pd.DataFrame:
        """
        Get predictions from gold layer with filters
        
        Args:
            risk_threshold: Minimum risk score (0-1)
            carrier: Filter by carrier code
            airport: Filter by origin airport
            limit: Max rows to return
            offset: Pagination offset
            
        Returns:
            DataFrame with predictions
        """
        where_clauses = [f"predicted_delay_rate >= {risk_threshold}"]
        
        if carrier:
            where_clauses.append(f"carrier = '{carrier}'")
        
        if airport:
            where_clauses.append(f"origin_airport = '{airport}'")
        
        where_sql = " AND ".join(where_clauses)
        
        query = f"""
        SELECT 
            carrier,
            origin_airport,
            year,
            month,
            predicted_delay_rate,
            arr_flights,
            created_at
        FROM gold_predictions
        WHERE {where_sql}
        ORDER BY predicted_delay_rate DESC
        LIMIT {limit}
        OFFSET {offset}
        """
        
        return self.client.query_df(query)
    
    def get_high_risk_predictions(self, threshold: float = 0.8) -> pd.DataFrame:
        """
        Get high risk predictions (risk >= threshold)
        """
        query = f"""
        SELECT 
            carrier,
            origin_airport,
            year,
            month,
            predicted_delay_rate,
            arr_flights
        FROM gold_predictions
        WHERE predicted_delay_rate >= {threshold}
        ORDER BY predicted_delay_rate DESC
        LIMIT 100
        """
        
        return self.client.query_df(query)
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Get global summary statistics
        
        Returns:
            Dict with total_predictions, avg_risk_score, high_risk_count, etc.
        """
        query = """
        SELECT 
            count() as total_predictions,
            avg(predicted_delay_rate) as avg_risk_score,
            countIf(predicted_delay_rate >= 0.8) as high_risk_count,
            uniq(carrier) as unique_carriers,
            uniq(origin_airport) as unique_airports,
            max(created_at) as last_prediction_date
        FROM gold_predictions
        """
        
        result = self.client.query_df(query)
        return result.to_dict('records')[0] if len(result) > 0 else {}
    
    def get_carrier_performance(self) -> pd.DataFrame:
        """
        Get performance metrics by carrier
        """
        query = """
        SELECT 
            carrier,
            count() as total_routes,
            avg(predicted_delay_rate) as avg_risk,
            countIf(predicted_delay_rate >= 0.8) as high_risk_routes,
            sum(arr_flights) as total_flights
        FROM gold_predictions
        GROUP BY carrier
        ORDER BY avg_risk DESC
        """
        
        return self.client.query_df(query)
    
    def get_airport_performance(self) -> pd.DataFrame:
        """
        Get performance metrics by airport
        """
        query = """
        SELECT 
            origin_airport as airport,
            count() as total_routes,
            avg(predicted_delay_rate) as avg_risk,
            countIf(predicted_delay_rate >= 0.8) as high_risk_routes,
            sum(arr_flights) as total_flights
        FROM gold_predictions
        GROUP BY origin_airport
        ORDER BY avg_risk DESC
        """
        
        return self.client.query_df(query)
    
    def get_temporal_trends(self, days: int = 30) -> pd.DataFrame:
        """
        Get risk score trends over time
        
        Args:
            days: Number of days to look back
            
        Returns:
            DataFrame with daily aggregates
        """
        query = f"""
        SELECT 
            toDate(created_at) as date,
            avg(predicted_delay_rate) as avg_risk,
            count() as predictions_count,
            countIf(predicted_delay_rate >= 0.8) as high_risk_count
        FROM gold_predictions
        WHERE created_at >= now() - INTERVAL {days} DAY
        GROUP BY date
        ORDER BY date ASC
        """
        
        return self.client.query_df(query)
    
    def get_risk_distribution(self) -> pd.DataFrame:
        """
        Get distribution of risk scores in buckets
        """
        query = """
        SELECT 
            CASE 
                WHEN predicted_delay_rate < 0.2 THEN 'Low (0-20%)'
                WHEN predicted_delay_rate < 0.5 THEN 'Medium (20-50%)'
                WHEN predicted_delay_rate < 0.8 THEN 'High (50-80%)'
                ELSE 'Critical (80-100%)'
            END as risk_level,
            count() as count
        FROM gold_predictions
        GROUP BY risk_level
        ORDER BY 
            CASE risk_level
                WHEN 'Low (0-20%)' THEN 1
                WHEN 'Medium (20-50%)' THEN 2
                WHEN 'High (50-80%)' THEN 3
                WHEN 'Critical (80-100%)' THEN 4
            END
        """
        
        return self.client.query_df(query)
    
    def get_prediction_by_route(self, carrier: str, airport: str) -> Optional[Dict[str, Any]]:
        """
        Get latest prediction for specific route
        
        Args:
            carrier: Carrier code (e.g. 'AA')
            airport: Airport code (e.g. 'JFK')
            
        Returns:
            Dict with prediction or None
        """
        query = f"""
        SELECT 
            carrier,
            origin_airport,
            year,
            month,
            predicted_delay_rate,
            arr_flights,
            created_at
        FROM gold_predictions
        WHERE carrier = '{carrier}' 
          AND origin_airport = '{airport}'
        ORDER BY created_at DESC
        LIMIT 1
        """
        
        result = self.client.query_df(query)
        return result.to_dict('records')[0] if len(result) > 0 else None
    
    def get_top_risky_routes(self, limit: int = 10) -> pd.DataFrame:
        """
        Get top N routes by risk score
        """
        query = f"""
        SELECT 
            carrier,
            origin_airport,
            predicted_delay_rate as risk_score,
            arr_flights
        FROM gold_predictions
        ORDER BY predicted_delay_rate DESC
        LIMIT {limit}
        """
        
        return self.client.query_df(query)
    
    def get_carriers_list(self) -> List[str]:
        """
        Get unique list of carriers
        """
        query = "SELECT DISTINCT carrier FROM gold_predictions ORDER BY carrier"
        result = self.client.query_df(query)
        return result['carrier'].tolist()
    
    def get_airports_list(self) -> List[str]:
        """
        Get unique list of airports
        """
        query = "SELECT DISTINCT origin_airport FROM gold_predictions ORDER BY origin_airport"
        result = self.client.query_df(query)
        return result['origin_airport'].tolist()
    
    def health_check(self) -> bool:
        """
        Check if ClickHouse connection is healthy
        """
        try:
            result = self.client.query("SELECT 1")
            return True
        except Exception as e:
            print(f"ClickHouse health check failed: {e}")
            return False

# Singleton instance
ch_client = ClickHouseClient()
