"""
Script: Load Historical Data to ClickHouse
Loads historical airline delay data (2003-2022) from CSV into ClickHouse.

This script complements the NiFi streaming pipeline by loading real historical data,
creating a complete dataset spanning 2003-2025 for ML training.

Data source: data/Airline_Delay_Cause_Cpt.csv (318,019 records)
Destination: ClickHouse airline_data.flights table
Expected time: 5-10 minutes
"""

import os
import csv
import time
from datetime import datetime
from typing import Dict, List
import clickhouse_connect
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

# Data source
DATA_FILE = 'data/Airline_Delay_Cause_Cpt.csv'

# Batch size for bulk inserts (tune based on memory)
BATCH_SIZE = 5000

# Setup logging
os.makedirs("logs", exist_ok=True)
logger.add("logs/load_historical_data.log", rotation="100 MB", retention="10 days")

# ClickHouse type limits
UINT8_MAX = 2**8 - 1
UINT16_MAX = 2**16 - 1
UINT32_MAX = 2**32 - 1


class HistoricalDataLoader:
    """Loads historical CSV data into ClickHouse"""

    def __init__(self):
        self.clickhouse_client = None
        self.total_loaded = 0
        self.total_skipped = 0
        self.initialize_connection()

    def initialize_connection(self):
        """Initialize ClickHouse client"""
        self.clickhouse_client = clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            username=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
            database=CLICKHOUSE_DATABASE
        )
        logger.info(f"ClickHouse client initialized: {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}")

    def safe_int(self, value, default=0, max_value=None):
        """Convert value to int with bounds checking"""
        if value == '' or value is None:
            return default
        try:
            result = int(float(value))
            if result < 0:
                return 0
            if max_value and result > max_value:
                return max_value
            return result
        except (ValueError, TypeError):
            return default

    def safe_float(self, value, default=0.0):
        """Convert value to float with validation"""
        if value == '' or value is None:
            return default
        try:
            result = float(value)
            return result if result >= 0 else 0.0
        except (ValueError, TypeError):
            return default

    def safe_string(self, value, default=''):
        """Convert value to string safely"""
        if value is None:
            return default
        return str(value).strip()

    def process_row(self, row: Dict) -> Dict:
        """Transform CSV row to ClickHouse format"""
        try:
            # Generate unique ID based on year, month, carrier, airport
            year = self.safe_int(row.get('year', 0), max_value=UINT16_MAX)
            month = self.safe_int(row.get('month', 0), max_value=UINT8_MAX)
            carrier = self.safe_string(row.get('carrier', ''))
            airport = self.safe_string(row.get('airport', ''))
            
            # Create deterministic ID for deduplication
            unique_id = f"{year}{month:02d}{carrier}{airport}"
            
            processed = {
                'id': unique_id,
                'year': year,
                'month': month,
                'carrier': carrier,
                'carrier_name': self.safe_string(row.get('carrier_name', '')),
                'airport': airport,
                'airport_name': self.safe_string(row.get('airport_name', '')),
                'arr_flights': self.safe_int(row.get('arr_flights', 0), max_value=UINT32_MAX),
                'arr_del15': self.safe_int(row.get('arr_del15', 0), max_value=UINT32_MAX),
                'carrier_ct': self.safe_float(row.get('carrier_ct', 0.0)),
                'weather_ct': self.safe_float(row.get('weather_ct', 0.0)),
                'nas_ct': self.safe_float(row.get('nas_ct', 0.0)),
                'security_ct': self.safe_float(row.get('security_ct', 0.0)),
                'late_aircraft_ct': self.safe_float(row.get('late_aircraft_ct', 0.0)),
                'arr_cancelled': self.safe_int(row.get('arr_cancelled', 0), max_value=UINT32_MAX),
                'arr_diverted': self.safe_int(row.get('arr_diverted', 0), max_value=UINT32_MAX),
                'arr_delay': self.safe_int(row.get('arr_delay', 0), max_value=UINT32_MAX),
                'carrier_delay': self.safe_int(row.get('carrier_delay', 0), max_value=UINT32_MAX),
                'weather_delay': self.safe_int(row.get('weather_delay', 0), max_value=UINT32_MAX),
                'nas_delay': self.safe_int(row.get('nas_delay', 0), max_value=UINT32_MAX),
                'security_delay': self.safe_int(row.get('security_delay', 0), max_value=UINT32_MAX),
                'late_aircraft_delay': self.safe_int(row.get('late_aircraft_delay', 0), max_value=UINT32_MAX),
            }
            
            return processed
        except Exception as e:
            logger.error(f"Error processing row: {e}")
            return None

    def insert_batch(self, batch: List[Dict]):
        """Insert batch of records into ClickHouse"""
        if not batch:
            return

        try:
            # Prepare data for insertion
            columns = list(batch[0].keys())
            data = [[record[col] for col in columns] for record in batch]

            # Insert into ClickHouse
            self.clickhouse_client.insert(
                'flights',
                data,
                column_names=columns
            )

            self.total_loaded += len(batch)
            logger.info(f"Inserted batch of {len(batch)} records. Total loaded: {self.total_loaded:,}")

        except Exception as e:
            logger.error(f"Error inserting batch: {e}")
            raise

    def check_existing_data(self):
        """Check what data already exists in ClickHouse"""
        try:
            result = self.clickhouse_client.query(
                "SELECT MIN(year) as min_year, MAX(year) as max_year, COUNT(*) as total FROM flights"
            )
            row = result.result_rows[0]
            logger.info(f"Existing data in ClickHouse: {row[2]:,} records ({row[0]}-{row[1]})")
            return row[2]
        except Exception as e:
            logger.warning(f"Could not check existing data: {e}")
            return 0

    def load_data(self):
        """Load historical data from CSV file"""
        logger.info("="*80)
        logger.info("Starting historical data load...")
        logger.info(f"Source file: {DATA_FILE}")
        logger.info(f"Batch size: {BATCH_SIZE:,}")
        logger.info("="*80)
        
        start_time = time.time()
        
        # Check existing data
        existing_count = self.check_existing_data()
        
        # Verify file exists
        if not os.path.exists(DATA_FILE):
            logger.error(f"Data file not found: {DATA_FILE}")
            return
        
        # Count total lines for progress tracking
        logger.info("Counting total lines...")
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            total_lines = sum(1 for _ in f) - 1  # Subtract header
        logger.info(f"Total records to process: {total_lines:,}")
        
        # Process CSV file
        batch = []
        processed_count = 0
        
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                for row in reader:
                    processed_count += 1
                    
                    # Process row
                    processed_row = self.process_row(row)
                    
                    if processed_row:
                        batch.append(processed_row)
                    else:
                        self.total_skipped += 1
                    
                    # Insert batch when size reached
                    if len(batch) >= BATCH_SIZE:
                        self.insert_batch(batch)
                        progress_pct = (processed_count / total_lines) * 100
                        elapsed = time.time() - start_time
                        rate = processed_count / elapsed if elapsed > 0 else 0
                        eta = (total_lines - processed_count) / rate if rate > 0 else 0
                        logger.info(f"Progress: {progress_pct:.1f}% | Rate: {rate:.0f} rec/s | ETA: {eta/60:.1f} min")
                        batch = []
                
                # Insert remaining records
                if batch:
                    self.insert_batch(batch)
                    batch = []
            
            elapsed_total = time.time() - start_time
            
            # Final statistics
            logger.info("="*80)
            logger.info("Historical data load completed!")
            logger.info(f"Total records processed: {processed_count:,}")
            logger.info(f"Total records loaded: {self.total_loaded:,}")
            logger.info(f"Total records skipped: {self.total_skipped:,}")
            logger.info(f"Time elapsed: {elapsed_total/60:.2f} minutes")
            logger.info(f"Average rate: {processed_count/elapsed_total:.0f} records/second")
            
            # Verify final count
            new_count = self.check_existing_data()
            logger.info(f"Records added: {new_count - existing_count:,}")
            logger.info("="*80)
            
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            raise

    def verify_data_quality(self):
        """Run data quality checks after load"""
        logger.info("\n" + "="*80)
        logger.info("Running data quality checks...")
        logger.info("="*80)
        
        try:
            # Check 1: Year distribution
            result = self.clickhouse_client.query(
                "SELECT year, COUNT(*) as count FROM flights GROUP BY year ORDER BY year"
            )
            logger.info("\nRecords by year:")
            for row in result.result_rows:
                logger.info(f"  {row[0]}: {row[1]:,} records")
            
            # Check 2: Top airports
            result = self.clickhouse_client.query(
                "SELECT airport, airport_name, COUNT(*) as count FROM flights GROUP BY airport, airport_name ORDER BY count DESC LIMIT 10"
            )
            logger.info("\nTop 10 airports by record count:")
            for row in result.result_rows:
                logger.info(f"  {row[0]} ({row[1]}): {row[2]:,} records")
            
            # Check 3: Top carriers
            result = self.clickhouse_client.query(
                "SELECT carrier, carrier_name, COUNT(*) as count FROM flights GROUP BY carrier, carrier_name ORDER BY count DESC LIMIT 10"
            )
            logger.info("\nTop 10 carriers by record count:")
            for row in result.result_rows:
                logger.info(f"  {row[0]} ({row[1]}): {row[2]:,} records")
            
            # Check 4: Overall statistics
            result = self.clickhouse_client.query("""
                SELECT 
                    SUM(arr_flights) as total_flights,
                    SUM(arr_del15) as total_delayed,
                    ROUND(SUM(arr_del15) * 100.0 / SUM(arr_flights), 2) as delay_rate,
                    SUM(arr_cancelled) as total_cancelled,
                    ROUND(SUM(arr_cancelled) * 100.0 / SUM(arr_flights), 2) as cancel_rate
                FROM flights
            """)
            row = result.result_rows[0]
            logger.info("\nOverall statistics:")
            logger.info(f"  Total flights: {row[0]:,}")
            logger.info(f"  Total delayed (15+ min): {row[1]:,}")
            logger.info(f"  Overall delay rate: {row[2]}%")
            logger.info(f"  Total cancelled: {row[3]:,}")
            logger.info(f"  Overall cancel rate: {row[4]}%")
            
            logger.info("="*80)
            logger.info("Data quality checks completed!")
            logger.info("="*80 + "\n")
            
        except Exception as e:
            logger.error(f"Error during quality checks: {e}")


if __name__ == "__main__":
    loader = HistoricalDataLoader()
    
    try:
        # Load historical data
        loader.load_data()
        
        # Verify data quality
        loader.verify_data_quality()
        
        logger.info("\n✅ Historical data load completed successfully!")
        logger.info("Next steps:")
        logger.info("  1. Start NiFi flow to generate 2023-2025 data")
        logger.info("  2. Run Script 2: python scripts/clickhouse_to_mongodb.py")
        logger.info("  3. Run Script 3: python scripts/mongodb_to_ml.py (to be created)")
        
    except KeyboardInterrupt:
        logger.info("\nLoad interrupted by user")
    except Exception as e:
        logger.error(f"\n❌ Load failed: {e}")
        raise
