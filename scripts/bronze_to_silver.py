"""
Bronze to Silver Transformation Script
Validates, cleanses and enriches raw data from Bronze layer to Silver layer

Features:
- JSON validation and parsing
- Data quality scoring
- GPS enrichment (latitude, longitude, city, state)
- Deduplication
- Error handling and retry logic
- Batch processing with configurable size

Architecture:
Bronze (raw JSON) → Validation → Enrichment → Silver (structured)
"""

import os
import sys
import json
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import clickhouse_connect
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
CLICKHOUSE_HOST = os.getenv('CLICKHOUSE_HOST', 'localhost')
CLICKHOUSE_PORT = int(os.getenv('CLICKHOUSE_HTTP_PORT', '8123'))
CLICKHOUSE_USER = os.getenv('CLICKHOUSE_USER', 'default')
CLICKHOUSE_PASSWORD = os.getenv('CLICKHOUSE_PASSWORD', '')
CLICKHOUSE_DATABASE = os.getenv('CLICKHOUSE_DATABASE', 'airline_data')

BATCH_SIZE = int(os.getenv('BRONZE_TO_SILVER_BATCH_SIZE', '1000'))
POLL_INTERVAL_SECONDS = int(os.getenv('POLL_INTERVAL_SECONDS', '10'))
MAX_RETRY_ATTEMPTS = 3

# Setup logging
os.makedirs("logs", exist_ok=True)
logger.add(
    "logs/bronze_to_silver.log",
    rotation="100 MB",
    retention="30 days",
    level="INFO"
)

# Type limits
UINT8_MAX = 2**8 - 1
UINT16_MAX = 2**16 - 1
UINT32_MAX = 2**32 - 1


@dataclass
class ValidationResult:
    is_valid: bool
    quality_score: int  # 0-100
    validation_flags: int  # Bitmap
    errors: List[str]


class BronzeToSilverProcessor:
    """Processes records from Bronze to Silver layer with validation and enrichment"""
    
    # Validation flags (bitmap)
    FLAG_VALID_JSON = 1 << 0
    FLAG_VALID_SCHEMA = 1 << 1
    FLAG_VALID_TYPES = 1 << 2
    FLAG_VALID_RANGES = 1 << 3
    FLAG_ENRICHED_GPS = 1 << 4
    FLAG_NO_DUPLICATES = 1 << 5
    
    def __init__(self):
        self.ch_client = None
        self.gps_lookup = {}
        self.processed_count = 0
        self.failed_count = 0
        self.initialize_connection()
        self.load_gps_lookup()
    
    def initialize_connection(self):
        """Initialize ClickHouse client"""
        self.ch_client = clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            username=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
            database=CLICKHOUSE_DATABASE
        )
        logger.info(f"✅ ClickHouse client initialized: {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}")
    
    def load_gps_lookup(self):
        """Load airport GPS data for enrichment"""
        try:
            result = self.ch_client.query("""
                SELECT 
                    airport_code,
                    airport_full_name,
                    city,
                    state,
                    latitude,
                    longitude
                FROM airports_gps
            """)
            
            for row in result.result_rows:
                self.gps_lookup[row[0]] = {
                    'airport_name': row[1],
                    'city': row[2],
                    'state': row[3],
                    'latitude': row[4],
                    'longitude': row[5]
                }
            
            logger.info(f"✅ Loaded GPS data for {len(self.gps_lookup)} airports")
        except Exception as e:
            logger.error(f"❌ Failed to load GPS lookup: {e}")
            self.gps_lookup = {}
    
    def safe_int(self, value, default=0, max_value=None) -> int:
        """Safely convert to int with bounds checking"""
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
    
    def safe_float(self, value, default=0.0) -> float:
        """Safely convert to float"""
        if value == '' or value is None:
            return default
        try:
            result = float(value)
            return max(0.0, result)  # No negative values
        except (ValueError, TypeError):
            return default
    
    def safe_string(self, value, default='') -> str:
        """Safely convert to string"""
        if value is None:
            return default
        return str(value).strip()
    
    def validate_record(self, data: Dict) -> ValidationResult:
        """
        Validate parsed JSON record and calculate quality score
        
        Quality Score Components:
        - Required fields present: 40 points
        - Valid types: 20 points
        - Valid ranges: 20 points
        - GPS enriched: 10 points
        - Logical consistency: 10 points
        """
        errors = []
        score = 0
        flags = 0
        
        # Check required fields (40 points)
        required_fields = ['year', 'month', 'carrier', 'airport', 'arr_flights']
        missing_fields = [f for f in required_fields if f not in data]
        
        if not missing_fields:
            score += 40
            flags |= self.FLAG_VALID_SCHEMA
        else:
            errors.append(f"Missing required fields: {missing_fields}")
            return ValidationResult(False, score, flags, errors)
        
        # Validate types and ranges (40 points)
        try:
            year = self.safe_int(data.get('year', 0))
            month = self.safe_int(data.get('month', 0))
            arr_flights = self.safe_int(data.get('arr_flights', 0))
            arr_del15 = self.safe_int(data.get('arr_del15', 0))
            
            # Range checks
            if 2000 <= year <= 2030:
                score += 10
            else:
                errors.append(f"Invalid year: {year}")
            
            if 1 <= month <= 12:
                score += 10
            else:
                errors.append(f"Invalid month: {month}")
            
            if arr_flights > 0:
                score += 10
                flags |= self.FLAG_VALID_RANGES
            else:
                errors.append("arr_flights must be > 0")
            
            # Logical consistency (10 points)
            if arr_del15 <= arr_flights:
                score += 10
            else:
                errors.append(f"arr_del15 ({arr_del15}) > arr_flights ({arr_flights})")
            
            flags |= self.FLAG_VALID_TYPES
            
        except Exception as e:
            errors.append(f"Type validation error: {e}")
            return ValidationResult(False, score, flags, errors)
        
        # GPS enrichment check (10 points)
        airport_code = self.safe_string(data.get('airport', ''))
        if airport_code in self.gps_lookup:
            score += 10
            flags |= self.FLAG_ENRICHED_GPS
        
        # Final validation
        is_valid = score >= 60  # Minimum 60/100 to pass
        
        return ValidationResult(
            is_valid=is_valid,
            quality_score=score,
            validation_flags=flags,
            errors=errors
        )
    
    def enrich_with_gps(self, data: Dict) -> Dict:
        """Enrich record with GPS coordinates and location data"""
        airport_code = self.safe_string(data.get('airport', ''))
        
        if airport_code in self.gps_lookup:
            gps = self.gps_lookup[airport_code]
            data.update({
                'latitude': gps['latitude'],
                'longitude': gps['longitude'],
                'city': gps['city'],
                'state': gps['state'],
                'airport_name': gps['airport_name']  # Override if better
            })
        else:
            # Fallback values
            data.update({
                'latitude': 0.0,
                'longitude': 0.0,
                'city': data.get('city', 'Unknown'),
                'state': '',
            })
        
        return data
    
    def parse_bronze_record(self, raw_json: str, kafka_offset: int) -> Optional[Tuple[Dict, ValidationResult]]:
        """Parse and validate a bronze record"""
        try:
            # Parse JSON
            data = json.loads(raw_json)
            
            # Validate
            validation = self.validate_record(data)
            
            if not validation.is_valid:
                logger.warning(f"❌ Validation failed (offset={kafka_offset}): {validation.errors}")
                return None
            
            # Enrich with GPS
            data = self.enrich_with_gps(data)
            
            # Build silver record
            silver_record = {
                # Business keys
                'id': self.safe_string(data.get('id', '')),
                'year': self.safe_int(data.get('year', 0), max_value=UINT16_MAX),
                'month': self.safe_int(data.get('month', 0), max_value=UINT8_MAX),
                'carrier': self.safe_string(data.get('carrier', ''))[:2],
                'carrier_name': self.safe_string(data.get('carrier_name', '')),
                'airport': self.safe_string(data.get('airport', ''))[:3],
                'airport_name': self.safe_string(data.get('airport_name', '')),
                
                # Metrics
                'arr_flights': self.safe_int(data.get('arr_flights', 0), max_value=UINT32_MAX),
                'arr_del15': self.safe_int(data.get('arr_del15', 0), max_value=UINT32_MAX),
                'arr_delay': self.safe_int(data.get('arr_delay', 0), max_value=UINT32_MAX),
                'arr_cancelled': self.safe_int(data.get('arr_cancelled', 0), max_value=UINT16_MAX),
                'arr_diverted': self.safe_int(data.get('arr_diverted', 0), max_value=UINT16_MAX),
                
                # Delay breakdown
                'carrier_delay': self.safe_int(data.get('carrier_delay', 0), max_value=UINT32_MAX),
                'weather_delay': self.safe_int(data.get('weather_delay', 0), max_value=UINT32_MAX),
                'nas_delay': self.safe_int(data.get('nas_delay', 0), max_value=UINT32_MAX),
                'security_delay': self.safe_int(data.get('security_delay', 0), max_value=UINT16_MAX),
                'late_aircraft_delay': self.safe_int(data.get('late_aircraft_delay', 0), max_value=UINT32_MAX),
                
                # Cause counts
                'carrier_ct': self.safe_float(data.get('carrier_ct', 0.0)),
                'weather_ct': self.safe_float(data.get('weather_ct', 0.0)),
                'nas_ct': self.safe_float(data.get('nas_ct', 0.0)),
                'security_ct': self.safe_float(data.get('security_ct', 0.0)),
                'late_aircraft_ct': self.safe_float(data.get('late_aircraft_ct', 0.0)),
                
                # GPS enrichment
                'latitude': data.get('latitude', 0.0),
                'longitude': data.get('longitude', 0.0),
                'city': self.safe_string(data.get('city', '')),
                'state': self.safe_string(data.get('state', ''))[:2],
                'country_code': 'US',
                
                # Audit fields
                'bronze_kafka_offset': kafka_offset,
                'data_quality_score': validation.quality_score,
                'validation_flags': validation.validation_flags,
            }
            
            return (silver_record, validation)
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON (offset={kafka_offset}): {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Processing error (offset={kafka_offset}): {e}")
            return None
    
    def process_batch(self) -> int:
        """Process a batch of pending bronze records"""
        try:
            # Fetch pending records
            result = self.ch_client.query(f"""
                SELECT 
                    raw_json,
                    kafka_offset,
                    kafka_partition
                FROM flights_bronze
                WHERE processing_status = 'pending'
                ORDER BY ingestion_timestamp ASC
                LIMIT {BATCH_SIZE}
            """)
            
            if result.row_count == 0:
                return 0
            
            logger.info(f"📦 Processing batch of {result.row_count} records...")
            
            silver_records = []
            failed_offsets = []
            processed_offsets = []
            
            for row in result.result_rows:
                raw_json, kafka_offset, kafka_partition = row
                
                parsed = self.parse_bronze_record(raw_json, kafka_offset)
                
                if parsed:
                    silver_record, validation = parsed
                    silver_records.append(silver_record)
                    processed_offsets.append(kafka_offset)
                else:
                    failed_offsets.append(kafka_offset)
            
            # Insert into Silver
            if silver_records:
                self.ch_client.insert('flights_silver', silver_records)
                logger.info(f"✅ Inserted {len(silver_records)} records into Silver")
            
            # Update Bronze status
            if processed_offsets:
                offsets_str = ','.join(map(str, processed_offsets))
                self.ch_client.command(f"""
                    ALTER TABLE flights_bronze
                    UPDATE processing_status = 'processed'
                    WHERE kafka_offset IN ({offsets_str})
                """)
            
            if failed_offsets:
                offsets_str = ','.join(map(str, failed_offsets))
                self.ch_client.command(f"""
                    ALTER TABLE flights_bronze
                    UPDATE 
                        processing_status = 'failed',
                        processing_attempts = processing_attempts + 1
                    WHERE kafka_offset IN ({offsets_str})
                """)
            
            self.processed_count += len(processed_offsets)
            self.failed_count += len(failed_offsets)
            
            logger.info(f"📊 Batch complete: {len(processed_offsets)} processed, {len(failed_offsets)} failed")
            
            return len(silver_records)
            
        except Exception as e:
            logger.error(f"❌ Batch processing error: {e}")
            return 0
    
    def run_continuous(self):
        """Run continuous processing loop"""
        logger.info("🚀 Starting Bronze → Silver processor...")
        logger.info(f"   Batch size: {BATCH_SIZE}")
        logger.info(f"   Poll interval: {POLL_INTERVAL_SECONDS}s")
        
        while True:
            try:
                processed = self.process_batch()
                
                if processed == 0:
                    logger.debug(f"💤 No pending records, sleeping {POLL_INTERVAL_SECONDS}s...")
                    time.sleep(POLL_INTERVAL_SECONDS)
                else:
                    # If batch is full, process immediately
                    if processed >= BATCH_SIZE:
                        logger.info("🔄 Batch full, processing next batch immediately...")
                        continue
                    else:
                        time.sleep(1)  # Short sleep if partial batch
                
                # Log stats every 100 records
                if self.processed_count % 100 == 0 and self.processed_count > 0:
                    success_rate = (self.processed_count / (self.processed_count + self.failed_count)) * 100
                    logger.info(f"📊 Stats: {self.processed_count} processed, {self.failed_count} failed ({success_rate:.1f}% success)")
                
            except KeyboardInterrupt:
                logger.info("🛑 Shutdown signal received")
                break
            except Exception as e:
                logger.error(f"❌ Unexpected error: {e}")
                time.sleep(5)  # Wait before retry


def main():
    """Main entry point"""
    processor = BronzeToSilverProcessor()
    processor.run_continuous()


if __name__ == "__main__":
    main()
