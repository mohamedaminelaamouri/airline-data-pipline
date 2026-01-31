"""
Script 2: ClickHouse to MongoDB Cache
Periodically extracts aggregations from ClickHouse and caches them in MongoDB
for faster dashboard queries and improved response times.
"""

import os
import time
from datetime import datetime
from typing import Dict, List
import clickhouse_connect
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import BulkWriteError
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ClickHouse Configuration
CLICKHOUSE_HOST = os.getenv('CLICKHOUSE_HOST', 'localhost')
CLICKHOUSE_PORT = int(os.getenv('CLICKHOUSE_HTTP_PORT', '8123'))
CLICKHOUSE_USER = os.getenv('CLICKHOUSE_USER', 'default')
CLICKHOUSE_PASSWORD = os.getenv('CLICKHOUSE_PASSWORD', '')
CLICKHOUSE_DATABASE = os.getenv('CLICKHOUSE_DATABASE', 'airline_data')

# MongoDB Configuration
MONGODB_HOST = os.getenv('MONGODB_HOST', 'localhost')
MONGODB_PORT = int(os.getenv('MONGODB_PORT', '27017'))
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'airline_cache')
MONGODB_COLLECTION = os.getenv('MONGODB_COLLECTION', 'aggregated_delays')

# Cache update interval (seconds)
CACHE_UPDATE_INTERVAL = int(os.getenv('CACHE_UPDATE_INTERVAL', '300'))  # 5 minutes

# Setup logging
os.makedirs("logs", exist_ok=True)
logger.add("logs/clickhouse_to_mongodb.log", rotation="100 MB", retention="10 days")


class ClickHouseToMongoDBCache:
    """Caches ClickHouse aggregations in MongoDB for fast dashboard queries"""

    def __init__(self):
        self.clickhouse_client = None
        self.mongo_client = None
        self.db = None
        self.collections = {}
        self.initialize_connections()

    def initialize_connections(self):
        """Initialize ClickHouse and MongoDB connections"""
        # ClickHouse Client
        self.clickhouse_client = clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            username=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
            database=CLICKHOUSE_DATABASE
        )
        logger.info(f"ClickHouse client initialized: {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}")

        # MongoDB Client
        self.mongo_client = MongoClient(
            host=MONGODB_HOST,
            port=MONGODB_PORT,
            serverSelectionTimeoutMS=5000
        )
        self.db = self.mongo_client[MONGODB_DATABASE]
        
        # Create collections with indexes
        self._setup_collections()
        
        logger.info(f"MongoDB client initialized: {MONGODB_HOST}:{MONGODB_PORT}")

    def _setup_collections(self):
        """Setup MongoDB collections with appropriate indexes"""
        # Collection 1: Airport Performance Summary
        self.collections['airport_performance'] = self.db['airport_performance']
        self.collections['airport_performance'].create_index([('airport', ASCENDING)])
        self.collections['airport_performance'].create_index([('delay_rate', DESCENDING)])
        self.collections['airport_performance'].create_index([('updated_at', DESCENDING)])
        
        # Collection 2: Carrier Performance Summary
        self.collections['carrier_performance'] = self.db['carrier_performance']
        self.collections['carrier_performance'].create_index([('carrier', ASCENDING)])
        self.collections['carrier_performance'].create_index([('delay_rate', DESCENDING)])
        self.collections['carrier_performance'].create_index([('updated_at', DESCENDING)])
        
        # Collection 3: Monthly Trends
        self.collections['monthly_trends'] = self.db['monthly_trends']
        self.collections['monthly_trends'].create_index([('year', ASCENDING), ('month', ASCENDING)])
        self.collections['monthly_trends'].create_index([('updated_at', DESCENDING)])
        
        # Collection 4: Delay Causes Summary
        self.collections['delay_causes'] = self.db['delay_causes']
        self.collections['delay_causes'].create_index([('airport', ASCENDING)])
        self.collections['delay_causes'].create_index([('carrier', ASCENDING)])
        self.collections['delay_causes'].create_index([('updated_at', DESCENDING)])
        
        # Collection 5: Top Performers
        self.collections['top_performers'] = self.db['top_performers']
        self.collections['top_performers'].create_index([('category', ASCENDING)])
        self.collections['top_performers'].create_index([('updated_at', DESCENDING)])
        
        logger.info("MongoDB collections and indexes created")

    def cache_airport_performance(self):
        """Cache airport performance metrics"""
        logger.info("Caching airport performance data...")
        
        query = """
        SELECT 
            f.airport,
            f.airport_name,
            g.city,
            g.state,
            g.latitude,
            g.longitude,
            SUM(f.arr_flights) as total_flights,
            SUM(f.arr_del15) as delayed_flights,
            SUM(f.arr_cancelled) as cancelled_flights,
            SUM(f.arr_diverted) as diverted_flights,
            ROUND(SUM(f.arr_del15) * 100.0 / SUM(f.arr_flights), 2) as delay_rate,
            ROUND(SUM(f.arr_delay) / SUM(f.arr_flights), 2) as avg_delay_minutes,
            ROUND(SUM(f.arr_cancelled) * 100.0 / SUM(f.arr_flights), 2) as cancel_rate
        FROM flights f
        LEFT JOIN airports_gps g ON f.airport = g.airport_code
        GROUP BY 
            f.airport, 
            f.airport_name,
            g.city,
            g.state,
            g.latitude,
            g.longitude
        HAVING total_flights > 0
        ORDER BY total_flights DESC
        """
        
        result = self.clickhouse_client.query(query)
        rows = result.result_rows
        columns = result.column_names
        
        documents = []
        for row in rows:
            doc = dict(zip(columns, row))
            doc['updated_at'] = datetime.utcnow()
            doc['_id'] = doc['airport']  # Use airport code as _id
            documents.append(doc)
        
        if documents:
            try:
                # Use bulk write with ReplaceOne operations
                from pymongo import ReplaceOne
                operations = [
                    ReplaceOne(
                        filter={'_id': doc['_id']},
                        replacement=doc,
                        upsert=True
                    )
                    for doc in documents
                ]
                result = self.collections['airport_performance'].bulk_write(operations, ordered=False)
                logger.info(f"Cached {len(documents)} airport performance records (upserted: {result.upserted_count + result.modified_count})")
            except BulkWriteError as e:
                logger.warning(f"Bulk write warning: {e.details}")

    def cache_carrier_performance(self):
        """Cache carrier performance metrics"""
        logger.info("Caching carrier performance data...")
        
        query = """
        SELECT 
            carrier,
            carrier_name,
            SUM(arr_flights) as total_flights,
            SUM(arr_del15) as delayed_flights,
            SUM(arr_cancelled) as cancelled_flights,
            SUM(arr_diverted) as diverted_flights,
            ROUND(SUM(arr_del15) * 100.0 / SUM(arr_flights), 2) as delay_rate,
            ROUND(SUM(arr_delay) / SUM(arr_flights), 2) as avg_delay_minutes,
            ROUND(SUM(arr_cancelled) * 100.0 / SUM(arr_flights), 2) as cancel_rate
        FROM flights
        GROUP BY carrier, carrier_name
        HAVING total_flights > 0
        ORDER BY total_flights DESC
        """
        
        result = self.clickhouse_client.query(query)
        rows = result.result_rows
        columns = result.column_names
        
        documents = []
        for row in rows:
            doc = dict(zip(columns, row))
            doc['updated_at'] = datetime.utcnow()
            doc['_id'] = doc['carrier']  # Use carrier code as _id
            documents.append(doc)
        
        if documents:
            try:
                from pymongo import ReplaceOne
                operations = [
                    ReplaceOne(
                        filter={'_id': doc['_id']},
                        replacement=doc,
                        upsert=True
                    )
                    for doc in documents
                ]
                result = self.collections['carrier_performance'].bulk_write(operations, ordered=False)
                logger.info(f"Cached {len(documents)} carrier performance records (upserted: {result.upserted_count + result.modified_count})")
            except BulkWriteError as e:
                logger.warning(f"Bulk write warning: {e.details}")

    def cache_monthly_trends(self):
        """Cache monthly trend data"""
        logger.info("Caching monthly trends data...")
        
        query = """
        SELECT 
            year,
            month,
            SUM(arr_flights) as total_flights,
            SUM(arr_del15) as delayed_flights,
            SUM(arr_cancelled) as cancelled_flights,
            SUM(arr_diverted) as diverted_flights,
            ROUND(SUM(arr_del15) * 100.0 / SUM(arr_flights), 2) as delay_rate,
            ROUND(SUM(arr_delay) / SUM(arr_flights), 2) as avg_delay_minutes
        FROM flights
        GROUP BY year, month
        ORDER BY year DESC, month DESC
        """
        
        result = self.clickhouse_client.query(query)
        rows = result.result_rows
        columns = result.column_names
        
        documents = []
        for row in rows:
            doc = dict(zip(columns, row))
            doc['updated_at'] = datetime.utcnow()
            doc['_id'] = f"{doc['year']}-{doc['month']:02d}"  # Use year-month as _id
            documents.append(doc)
        
        if documents:
            try:
                from pymongo import ReplaceOne
                operations = [
                    ReplaceOne(
                        filter={'_id': doc['_id']},
                        replacement=doc,
                        upsert=True
                    )
                    for doc in documents
                ]
                result = self.collections['monthly_trends'].bulk_write(operations, ordered=False)
                logger.info(f"Cached {len(documents)} monthly trend records (upserted: {result.upserted_count + result.modified_count})")
            except BulkWriteError as e:
                logger.warning(f"Bulk write warning: {e.details}")

    def cache_delay_causes(self):
        """Cache delay causes by airport and carrier"""
        logger.info("Caching delay causes data...")
        
        query = """
        SELECT 
            airport,
            airport_name,
            carrier,
            carrier_name,
            SUM(arr_flights) as total_flights,
            SUM(carrier_delay) as carrier_delay_minutes,
            SUM(weather_delay) as weather_delay_minutes,
            SUM(nas_delay) as nas_delay_minutes,
            SUM(security_delay) as security_delay_minutes,
            SUM(late_aircraft_delay) as late_aircraft_delay_minutes,
            ROUND(SUM(carrier_delay) * 100.0 / (SUM(carrier_delay) + SUM(weather_delay) + SUM(nas_delay) + SUM(security_delay) + SUM(late_aircraft_delay) + 0.001), 2) as carrier_delay_pct,
            ROUND(SUM(weather_delay) * 100.0 / (SUM(carrier_delay) + SUM(weather_delay) + SUM(nas_delay) + SUM(security_delay) + SUM(late_aircraft_delay) + 0.001), 2) as weather_delay_pct,
            ROUND(SUM(nas_delay) * 100.0 / (SUM(carrier_delay) + SUM(weather_delay) + SUM(nas_delay) + SUM(security_delay) + SUM(late_aircraft_delay) + 0.001), 2) as nas_delay_pct,
            ROUND(SUM(security_delay) * 100.0 / (SUM(carrier_delay) + SUM(weather_delay) + SUM(nas_delay) + SUM(security_delay) + SUM(late_aircraft_delay) + 0.001), 2) as security_delay_pct,
            ROUND(SUM(late_aircraft_delay) * 100.0 / (SUM(carrier_delay) + SUM(weather_delay) + SUM(nas_delay) + SUM(security_delay) + SUM(late_aircraft_delay) + 0.001), 2) as late_aircraft_delay_pct
        FROM flights
        GROUP BY airport, airport_name, carrier, carrier_name
        HAVING total_flights > 10
        ORDER BY total_flights DESC
        LIMIT 1000
        """
        
        result = self.clickhouse_client.query(query)
        rows = result.result_rows
        columns = result.column_names
        
        documents = []
        for row in rows:
            doc = dict(zip(columns, row))
            doc['updated_at'] = datetime.utcnow()
            doc['_id'] = f"{doc['airport']}-{doc['carrier']}"  # Use airport-carrier as _id
            documents.append(doc)
        
        if documents:
            try:
                from pymongo import ReplaceOne
                operations = [
                    ReplaceOne(
                        filter={'_id': doc['_id']},
                        replacement=doc,
                        upsert=True
                    )
                    for doc in documents
                ]
                result = self.collections['delay_causes'].bulk_write(operations, ordered=False)
                logger.info(f"Cached {len(documents)} delay causes records (upserted: {result.upserted_count + result.modified_count})")
            except BulkWriteError as e:
                logger.warning(f"Bulk write warning: {e.details}")

    def cache_top_performers(self):
        """Cache top and bottom performers across different categories"""
        logger.info("Caching top performers data...")
        
        # Top 10 best airports (lowest delay rate)
        query_best_airports = """
        SELECT 
            airport,
            airport_name,
            SUM(arr_flights) as total_flights,
            ROUND(SUM(arr_del15) * 100.0 / SUM(arr_flights), 2) as delay_rate
        FROM flights
        GROUP BY airport, airport_name
        HAVING total_flights > 1000
        ORDER BY delay_rate ASC
        LIMIT 10
        """
        
        # Top 10 worst airports (highest delay rate)
        query_worst_airports = """
        SELECT 
            airport,
            airport_name,
            SUM(arr_flights) as total_flights,
            ROUND(SUM(arr_del15) * 100.0 / SUM(arr_flights), 2) as delay_rate
        FROM flights
        GROUP BY airport, airport_name
        HAVING total_flights > 1000
        ORDER BY delay_rate DESC
        LIMIT 10
        """
        
        # Best carriers
        query_best_carriers = """
        SELECT 
            carrier,
            carrier_name,
            SUM(arr_flights) as total_flights,
            ROUND(SUM(arr_del15) * 100.0 / SUM(arr_flights), 2) as delay_rate
        FROM flights
        GROUP BY carrier, carrier_name
        HAVING total_flights > 1000
        ORDER BY delay_rate ASC
        LIMIT 10
        """
        
        # Worst carriers
        query_worst_carriers = """
        SELECT 
            carrier,
            carrier_name,
            SUM(arr_flights) as total_flights,
            ROUND(SUM(arr_del15) * 100.0 / SUM(arr_flights), 2) as delay_rate
        FROM flights
        GROUP BY carrier, carrier_name
        HAVING total_flights > 1000
        ORDER BY delay_rate DESC
        LIMIT 10
        """
        
        categories = {
            'best_airports': query_best_airports,
            'worst_airports': query_worst_airports,
            'best_carriers': query_best_carriers,
            'worst_carriers': query_worst_carriers
        }
        
        for category, query in categories.items():
            result = self.clickhouse_client.query(query)
            rows = result.result_rows
            columns = result.column_names
            
            items = [dict(zip(columns, row)) for row in rows]
            
            doc = {
                '_id': category,
                'category': category,
                'items': items,
                'updated_at': datetime.utcnow()
            }
            
            self.collections['top_performers'].replace_one(
                {'_id': category},
                doc,
                upsert=True
            )
        
        logger.info(f"Cached {len(categories)} top performers categories")

    def update_cache(self):
        """Update all cache collections"""
        logger.info("=" * 60)
        logger.info("Starting cache update cycle...")
        start_time = time.time()
        
        try:
            self.cache_airport_performance()
            self.cache_carrier_performance()
            self.cache_monthly_trends()
            self.cache_delay_causes()
            self.cache_top_performers()
            
            elapsed = time.time() - start_time
            logger.info(f"Cache update completed in {elapsed:.2f} seconds")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Error during cache update: {e}")
            raise

    def run(self):
        """Main loop - periodically update cache"""
        logger.info(f"Starting ClickHouse to MongoDB cache service...")
        logger.info(f"Update interval: {CACHE_UPDATE_INTERVAL} seconds")
        
        try:
            while True:
                self.update_cache()
                logger.info(f"Sleeping for {CACHE_UPDATE_INTERVAL} seconds...")
                time.sleep(CACHE_UPDATE_INTERVAL)
                
        except KeyboardInterrupt:
            logger.info("Shutting down cache service...")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        finally:
            if self.mongo_client:
                self.mongo_client.close()
            logger.info("Cache service stopped")


if __name__ == "__main__":
    cache_service = ClickHouseToMongoDBCache()
    cache_service.run()
