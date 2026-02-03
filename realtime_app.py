"""
Airline Delays Analytics Dashboard v3.2
Professional Real-time Data Pipeline Visualization
Built with Streamlit, ClickHouse & Kafka

Technical Features:
- Resilient Kafka consumer with retry logic
- ClickHouse connection pooling and error recovery
- Data validation and type safety
- Comprehensive logging and error handling
- Thread-safe session state management
"""

from __future__ import annotations
import json
import os
import sys
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, List, Optional, Tuple

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from confluent_kafka import Consumer, KafkaError
import clickhouse_connect

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG to see more details
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ============================================================================
# STREAMLIT KAFKA STATE (shared across reruns via cache_resource)
# ============================================================================

@st.cache_resource
def get_kafka_buffer() -> Deque[KafkaEvent]:
    """Shared Kafka buffer that survives Streamlit reruns."""
    buf = deque(maxlen=5000)
    logger.info(f"Created cached Kafka buffer (id={id(buf)})")
    return buf


@st.cache_resource
def get_kafka_stop_event() -> threading.Event:
    """Shared stop event for the Kafka consumer thread."""
    stop = threading.Event()
    logger.info(f"Created cached Kafka stop event (id={id(stop)})")
    return stop


class _KafkaThreadHolder:
    thread: Optional[threading.Thread] = None
    start_time: Optional[datetime] = None


@st.cache_resource
def get_kafka_thread_holder() -> _KafkaThreadHolder:
    return _KafkaThreadHolder()


def get_kafka_thread() -> Optional[threading.Thread]:
    holder = get_kafka_thread_holder()
    return holder.thread


def set_kafka_thread(thread: Optional[threading.Thread]) -> None:
    holder = get_kafka_thread_holder()
    holder.thread = thread


def set_kafka_start_time(start_time: datetime) -> None:
    holder = get_kafka_thread_holder()
    holder.start_time = start_time


def get_kafka_start_time() -> Optional[datetime]:
    holder = get_kafka_thread_holder()
    return holder.start_time


# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Airline Delays Analytics",
    page_icon="chart_with_upwards_trend",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

APP_VERSION = "3.2.0"
APP_TITLE = "Airline Delays Analytics"

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April", 
    5: "May", 6: "June", 7: "July", 8: "August", 
    9: "September", 10: "October", 11: "November", 12: "December",
}

QUARTERS = {
    "Q1": [1, 2, 3],
    "Q2": [4, 5, 6],
    "Q3": [7, 8, 9],
    "Q4": [10, 11, 12],
}

# Professional color palette
COLOR_PRIMARY = "#0066CC"
COLOR_SUCCESS = "#00AA44"
COLOR_WARNING = "#FF8800"
COLOR_DANGER = "#CC0000"
COLOR_INFO = "#0088CC"
COLOR_NEUTRAL = "#666666"


def env(name: str, default: str) -> str:
    """Get environment variable with fallback."""
    value = os.getenv(name)
    return default if value is None or value == "" else value


# Environment configuration
# For Docker: use service hostnames, for local: use localhost
KAFKA_HOST = env("KAFKA_HOST", "kafka")  # Changed to kafka for Docker internal network
KAFKA_PORT = int(env("KAFKA_PORT", "29092"))  # Changed to 29092 (PLAINTEXT internal port)
KAFKA_TOPIC = env("KAFKA_TOPIC", "airline-delays")
KAFKA_GROUP_ID = env("STREAMLIT_KAFKA_GROUP_ID", "airline-streamlit-ui")
KAFKA_RETRY_DELAY = 5  # Seconds between connection retries
KAFKA_MAX_RETRIES = 3  # Max connection retries

CLICKHOUSE_HOST = env("CLICKHOUSE_HOST", "clickhouse")  # Changed to clickhouse for Docker
CLICKHOUSE_HTTP_PORT = int(env("CLICKHOUSE_HTTP_PORT", "8123"))
CLICKHOUSE_USER = env("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = env("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DATABASE = env("CLICKHOUSE_DATABASE", "airline_data")
CLICKHOUSE_TIMEOUT = 30  # Seconds
CLICKHOUSE_RETRY_DELAY = 2  # Seconds between retries


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass(frozen=True)
class KafkaEvent:
    received_at: datetime
    record: Dict[str, Any]
    raw: str


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division returning default if denominator is zero."""
    return default if denominator <= 0 else float(numerator) / float(denominator)


def format_number(num: float, decimals: int = 0) -> str:
    """Format number with thousands separator."""
    if decimals == 0:
        return f"{int(num):,}"
    return f"{num:,.{decimals}f}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format value as percentage."""
    return f"{value * 100:.{decimals}f}%"


def format_duration(minutes: float) -> str:
    """Format minutes as human-readable duration."""
    if minutes < 60:
        return f"{int(minutes)} min"
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    return f"{hours}h {mins}m" if mins > 0 else f"{hours}h"


# ============================================================================
# KAFKA FUNCTIONS
# ============================================================================

def parse_nifi_json(parsed: Any) -> Optional[Dict[str, Any]]:
    """Parse NiFi Pretty Print JSON format."""
    if not isinstance(parsed, list) or len(parsed) == 0:
        return None
    if all(isinstance(x, dict) and ("year" in x or "month" in x or "carrier" in x) for x in parsed):
        return parsed[0]

    data: Dict[str, Any] = {}
    for item in parsed:
        if not isinstance(item, dict):
            continue
        for key_str, value_str in item.items():
            if str(key_str).strip() in ["{", "}"]:
                if value_str and ":" in value_str:
                    left, right = value_str.split(":", 1)
                    key = left.strip().strip('"').strip()
                    value = right.strip().strip('"').strip()
                    if key:
                        data[key] = value
            else:
                data[str(key_str)] = value_str
    return data or None


def parse_kafka_payload(raw: str) -> List[Dict[str, Any]]:
    """Parse Kafka message payload - handles both standard JSON and array formats."""
    try:
        parsed = json.loads(raw)
        logger.debug(f"Parsed JSON type: {type(parsed)}, content sample: {str(parsed)[:100]}")
    except Exception as e:
        logger.debug(f"JSON parse error: {str(e)[:50]}")
        return []

    # Standard case: single dictionary
    if isinstance(parsed, dict):
        logger.debug(f"Returning single dict with keys: {list(parsed.keys())[:5]}")
        return [parsed]

    # Array case: multiple records
    if isinstance(parsed, list):
        if len(parsed) == 0:
            logger.debug("Empty list received")
            return []
        
        # If all items are dicts, return them (could be records or NiFi format)
        if all(isinstance(x, dict) for x in parsed):
            # Check if this is NiFi Pretty Print format (has "{" keys)
            has_nifi_format = any("{" in str(k).strip() for d in parsed for k in d.keys())
            
            if has_nifi_format:
                logger.debug("Detected NiFi format, attempting to parse")
                maybe = parse_nifi_json(parsed)
                result = [maybe] if maybe else []
                logger.debug(f"NiFi parse result: {bool(maybe)}")
                return result
            else:
                # Regular array of dicts
                logger.debug(f"Returning array of {len(parsed)} dicts")
                return [d for d in parsed if isinstance(d, dict)]
        else:
            # Try NiFi parsing
            logger.debug("Mixed types in array, trying NiFi parsing")
            maybe = parse_nifi_json(parsed)
            return [maybe] if maybe else []

    logger.debug(f"Unexpected parsed type: {type(parsed)}")
    return []


def kafka_consumer_loop(buffer: Deque[KafkaEvent], stop_event: threading.Event) -> None:
    """Background thread for consuming Kafka messages with robust error handling."""
    consumer = None
    retry_count = 0
    message_count = 0
    
    try:
        while not stop_event.is_set() and retry_count < KAFKA_MAX_RETRIES:
            try:
                conf = {
                    'bootstrap.servers': f"{KAFKA_HOST}:{KAFKA_PORT}",
                    'group.id': KAFKA_GROUP_ID,
                    'auto.offset.reset': 'earliest',  # Read backlog for visibility on reload
                    'enable.auto.commit': False,       # Keep offsets local so reloads still show data
                    'session.timeout.ms': 60000,
                    'connections.max.idle.ms': 540000,
                    'socket.timeout.ms': 10000,
                    'api.version.request.timeout.ms': 10000,
                    'fetch.wait.max.ms': 100,  # Don't wait long between messages
                }
                
                logger.info(f"Kafka consumer connecting to {KAFKA_HOST}:{KAFKA_PORT}")
                consumer = Consumer(conf)
                consumer.subscribe([KAFKA_TOPIC])
                retry_count = 0  # Reset retry count on successful connection
                logger.info(f"Kafka consumer subscribed to topic: {KAFKA_TOPIC} - waiting for new messages...")
                message_count = 0
                
                # Message consumption loop
                poll_count = 0
                while not stop_event.is_set():
                    try:
                        msg = consumer.poll(timeout=3.0)
                        poll_count += 1
                        
                        if msg is None:
                            if poll_count % 10 == 0:
                                logger.debug(f"Kafka poll timeout (no messages) - polling {poll_count} times")
                            continue
                            
                        if msg.error():
                            if msg.error().code() == KafkaError._PARTITION_EOF:
                                continue  # Expected at end of partition
                            else:
                                logger.warning(f"Kafka error: {msg.error()}")
                                continue
                        
                        try:
                            raw = msg.value().decode("utf-8", errors="replace")
                            records = parse_kafka_payload(raw)
                            
                            if records:
                                for record in records:
                                    if record:
                                        buffer.append(KafkaEvent(
                                            received_at=datetime.utcnow(),
                                            record=record,
                                            raw=raw
                                        ))
                                        message_count += 1
                                        if message_count % 10 == 0:
                                            logger.info(f"Kafka: Received {message_count} messages, buffer size: {len(buffer)}")
                                        if message_count == 1:
                                            logger.info(f"First message received! Record keys: {list(record.keys())[:10]}")
                            else:
                                logger.debug(f"Parse returned empty for message at offset {msg.offset()}")
                                    
                        except Exception as e:
                            logger.debug(f"Error parsing message: {str(e)[:100]}")
                            
                    except Exception as e:
                        logger.warning(f"Error in message consumption: {str(e)[:100]}")
                        time.sleep(1.0)
                        continue
                        
            except Exception as e:
                retry_count += 1
                logger.error(f"Kafka connection error (attempt {retry_count}): {str(e)[:100]}")
                if retry_count < KAFKA_MAX_RETRIES and not stop_event.is_set():
                    time.sleep(KAFKA_RETRY_DELAY)
                else:
                    logger.error(f"Kafka connection failed after {retry_count} retries")
                    break
                    
    except Exception as e:
        logger.error(f"Fatal error in Kafka consumer loop: {str(e)}")
    finally:
        if consumer is not None:
            try:
                consumer.close()
                logger.info(f"Kafka consumer closed. Total messages received in this session: {message_count}")
            except Exception as e:
                logger.warning(f"Error closing Kafka consumer: {str(e)}")


def ensure_kafka_thread() -> Tuple[bool, str]:
    """
    Ensure Kafka consumer thread is running (uses global persistent state).
    Returns: (is_running, status_message)
    """
    buf = get_kafka_buffer()
    stop = get_kafka_stop_event()
    thread = get_kafka_thread()
    logger.debug(
        f"ensure_kafka_thread: buffer id={id(buf)}, stop id={id(stop)}, thread_alive={thread.is_alive() if thread else False}"
    )
    
    # Start thread if not running
    if thread is None or not thread.is_alive():
        try:
            new_thread = threading.Thread(
                target=kafka_consumer_loop,
                args=(buf, stop),
                daemon=True,
                name="kafka-consumer",
            )
            new_thread.start()
            set_kafka_thread(new_thread)
            set_kafka_start_time(datetime.utcnow())
            logger.info(
                f"Kafka consumer thread started (buffer id={id(buf)}, thread ident={new_thread.ident})"
            )
            return True, "Connected"
        except Exception as e:
            logger.error(f"Failed to start Kafka thread: {str(e)}")
            return False, f"Failed: {str(e)[:50]}"
    
    # Thread is running, return uptime
    start_time = get_kafka_start_time() or datetime.utcnow()
    set_kafka_start_time(start_time)
    uptime = datetime.utcnow() - start_time
    return True, f"Online ({int(uptime.total_seconds())}s)"


def kafka_messages_per_minute(buffer: Deque[KafkaEvent], window_minutes: int = 1) -> float:
    """Calculate Kafka message rate."""
    if not buffer:
        return 0.0
    cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
    count = sum(1 for e in buffer if e.received_at >= cutoff)
    return float(count) / float(window_minutes)


# ============================================================================
# CLICKHOUSE FUNCTIONS
# ============================================================================

@st.cache_resource(show_spinner=False)
def get_clickhouse_client():
    """Get cached ClickHouse client with connection pooling."""
    try:
        client = clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_HTTP_PORT,
            username=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
            database=CLICKHOUSE_DATABASE,
        )
        logger.info(f"ClickHouse client connected to {CLICKHOUSE_HOST}:{CLICKHOUSE_HTTP_PORT}/{CLICKHOUSE_DATABASE}")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to ClickHouse: {str(e)}")
        raise


def ch_query_df(sql: str, parameters: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """Execute ClickHouse query with retry logic and error handling."""
    max_retries = 2
    retry_count = 0
    last_error = None
    
    while retry_count <= max_retries:
        try:
            client = get_clickhouse_client()
            df = client.query_df(sql, parameters=parameters)
            
            # Validate result
            if not isinstance(df, pd.DataFrame):
                logger.warning(f"Unexpected query result type: {type(df)}")
                return pd.DataFrame()
            
            return df
            
        except Exception as e:
            last_error = e
            retry_count += 1
            logger.warning(f"ClickHouse query error (attempt {retry_count}/{max_retries + 1}): {str(e)[:100]}")
            if retry_count <= max_retries:
                time.sleep(CLICKHOUSE_RETRY_DELAY)
            else:
                logger.error(f"ClickHouse query failed after {max_retries + 1} attempts")
                return pd.DataFrame()
    
    return pd.DataFrame()


@st.cache_data(show_spinner=False, ttl=30)
def ch_years() -> List[int]:
    """Get available years with validation."""
    try:
        df = ch_query_df("SELECT DISTINCT year FROM flights ORDER BY year DESC")
        if df.empty:
            logger.warning("No years found in flights table")
            return []
        years = [int(x) for x in df["year"].tolist() if x is not None]
        return sorted(years, reverse=True)
    except Exception as e:
        logger.error(f"Error fetching years: {str(e)}")
        return []


@st.cache_data(show_spinner=False, ttl=30)
def ch_months(year: int) -> List[int]:
    """Get available months for a year with validation."""
    try:
        df = ch_query_df(
            "SELECT DISTINCT month FROM flights WHERE year = %(year)s ORDER BY month",
            parameters={"year": int(year)},
        )
        if df.empty:
            logger.warning(f"No months found for year {year}")
            return []
        months = [int(x) for x in df["month"].tolist() if x is not None]
        return sorted(months)
    except Exception as e:
        logger.error(f"Error fetching months for year {year}: {str(e)}")
        return []


@st.cache_data(show_spinner=False, ttl=15)
def ch_overview_kpis(year: int, months: Optional[List[int]]) -> Dict[str, float]:
    """Get comprehensive KPIs with data validation."""
    where = "year = %(year)s"
    params: Dict[str, Any] = {"year": int(year)}
    if months:
        where += " AND month IN %(months)s"
        params["months"] = tuple(months)

    try:
        df = ch_query_df(
            f"""
            SELECT
                sum(arr_flights) AS flights,
                sum(arr_del15) AS delayed,
                sum(arr_delay) AS delay_minutes,
                sum(arr_cancelled) AS cancelled,
                sum(arr_diverted) AS diverted,
                avg(arr_delay) AS avg_delay_minutes,
                max(arr_delay) AS max_delay_minutes,
                min(arr_delay) AS min_delay_minutes,
                sum(carrier_delay) AS carrier_delay_minutes,
                sum(weather_delay) AS weather_delay_minutes,
                sum(nas_delay) AS nas_delay_minutes,
                sum(security_delay) AS security_delay_minutes,
                sum(late_aircraft_delay) AS late_aircraft_delay_minutes
            FROM flights
            WHERE {where}
            """,
            parameters=params,
        )

        if df.empty:
            return {k: 0.0 for k in ['flights', 'delayed', 'delay_minutes', 'cancelled', 'diverted',
                                       'on_time', 'delay_rate', 'cancel_rate', 'divert_rate',
                                       'avg_delay_per_flight', 'avg_delay_when_delayed',
                                       'avg_delay_minutes', 'max_delay_minutes', 'min_delay_minutes']}

        flights = float(df.at[0, "flights"] or 0)
        delayed = float(df.at[0, "delayed"] or 0)
        delay_minutes = float(df.at[0, "delay_minutes"] or 0)
        cancelled = float(df.at[0, "cancelled"] or 0)
        diverted = float(df.at[0, "diverted"] or 0)
        on_time = flights - delayed - cancelled - diverted

        return {
            'flights': flights,
            'delayed': delayed,
            'delay_minutes': delay_minutes,
            'cancelled': cancelled,
            'diverted': diverted,
            'on_time': on_time,
            'delay_rate': safe_divide(delayed, flights),
            'cancel_rate': safe_divide(cancelled, flights),
            'divert_rate': safe_divide(diverted, flights),
            'avg_delay_per_flight': safe_divide(delay_minutes, flights),
            'avg_delay_when_delayed': safe_divide(delay_minutes, delayed),
            'avg_delay_minutes': float(df.at[0, "avg_delay_minutes"] or 0),
            'max_delay_minutes': float(df.at[0, "max_delay_minutes"] or 0),
            'min_delay_minutes': float(df.at[0, "min_delay_minutes"] or 0),
        }
    except Exception as e:
        logger.error(f"Error fetching KPIs for year {year}: {str(e)}")
        return {k: 0.0 for k in ['flights', 'delayed', 'delay_minutes', 'cancelled', 'diverted',
                                   'on_time', 'delay_rate', 'cancel_rate', 'divert_rate',
                                   'avg_delay_per_flight', 'avg_delay_when_delayed',
                                   'avg_delay_minutes', 'max_delay_minutes', 'min_delay_minutes']}


@st.cache_data(show_spinner=False, ttl=15)
def ch_delay_trend_by_month(year: int) -> pd.DataFrame:
    """Get monthly delay trends with detailed metrics."""
    df = ch_query_df(
        """
        SELECT
            month,
            count(*) AS record_count,
            sum(arr_flights) AS flights,
            sum(arr_del15) AS delayed,
            sum(arr_delay) AS delay_minutes,
            sum(arr_cancelled) AS cancelled,
            sum(arr_diverted) AS diverted,
            avg(arr_delay) AS avg_delay,
            max(arr_delay) AS max_delay
        FROM flights
        WHERE year = %(year)s
        GROUP BY month
        ORDER BY month
        """,
        parameters={"year": year},
    )
    if df.empty:
        return df
    
    df["delay_rate"] = df.apply(lambda r: safe_divide(float(r["delayed"]), float(r["flights"])), axis=1)
    df["cancel_rate"] = df.apply(lambda r: safe_divide(float(r["cancelled"]), float(r["flights"])), axis=1)
    df["month_name"] = df["month"].map(lambda m: MONTH_NAMES.get(int(m), str(m)))
    return df


@st.cache_data(show_spinner=False, ttl=15)
def ch_cause_breakdown(year: int, months: Optional[List[int]]) -> pd.DataFrame:
    """Get detailed delay cause breakdown."""
    where = "year = %(year)s"
    params: Dict[str, Any] = {"year": year}
    if months:
        where += " AND month IN %(months)s"
        params["months"] = tuple(months)

    df = ch_query_df(
        f"""
        SELECT
            sum(carrier_delay) AS carrier,
            sum(weather_delay) AS weather,
            sum(nas_delay) AS nas,
            sum(security_delay) AS security,
            sum(late_aircraft_delay) AS late_aircraft,
            count(*) AS record_count
        FROM flights
        WHERE {where}
        """,
        parameters=params,
    )
    if df.empty:
        return pd.DataFrame()

    row = df.iloc[0].to_dict()
    total = sum(float(row.get(k, 0) or 0) for k in ['carrier', 'weather', 'nas', 'security', 'late_aircraft'])
    
    out = pd.DataFrame([
        {"cause": "Carrier Issues", "minutes": float(row.get("carrier", 0) or 0)},
        {"cause": "Weather", "minutes": float(row.get("weather", 0) or 0)},
        {"cause": "NAS Issues", "minutes": float(row.get("nas", 0) or 0)},
        {"cause": "Security", "minutes": float(row.get("security", 0) or 0)},
        {"cause": "Late Aircraft", "minutes": float(row.get("late_aircraft", 0) or 0)},
    ])
    out["percentage"] = out["minutes"].apply(lambda x: safe_divide(x, total))
    out = out[out["minutes"] > 0]
    return out.sort_values("minutes", ascending=False)


@st.cache_data(show_spinner=False, ttl=15)
def ch_top_carriers(year: int, months: Optional[List[int]], limit: int = 15) -> pd.DataFrame:
    """Get top carriers by various metrics."""
    where = "year = %(year)s"
    params: Dict[str, Any] = {"year": year, "limit": int(limit)}
    if months:
        where += " AND month IN %(months)s"
        params["months"] = tuple(months)

    return ch_query_df(
        f"""
        SELECT
            carrier,
            any(carrier_name) AS airline_name,
            sum(arr_flights) AS total_flights,
            sum(arr_del15) AS delayed_flights,
            sum(arr_delay) AS total_delay_minutes,
            avg(arr_delay) AS avg_delay,
            round(sum(arr_del15) * 100.0 / nullIf(sum(arr_flights), 0), 2) AS delay_percentage,
            sum(arr_cancelled) AS cancelled,
            sum(arr_diverted) AS diverted
        FROM flights
        WHERE {where}
        GROUP BY carrier
        HAVING total_flights >= 100
        ORDER BY delay_percentage DESC
        LIMIT %(limit)s
        """,
        parameters=params,
    )


@st.cache_data(show_spinner=False, ttl=15)
def ch_top_airports(year: int, months: Optional[List[int]], limit: int = 15) -> pd.DataFrame:
    """Get top airports by various metrics."""
    where = "year = %(year)s"
    params: Dict[str, Any] = {"year": year, "limit": int(limit)}
    if months:
        where += " AND month IN %(months)s"
        params["months"] = tuple(months)

    return ch_query_df(
        f"""
        SELECT
            airport,
            any(airport_name) AS airport_full_name,
            sum(arr_flights) AS total_flights,
            sum(arr_del15) AS delayed_flights,
            sum(arr_delay) AS total_delay_minutes,
            avg(arr_delay) AS avg_delay,
            round(sum(arr_del15) * 100.0 / nullIf(sum(arr_flights), 0), 2) AS delay_percentage,
            sum(arr_cancelled) AS cancelled,
            sum(arr_diverted) AS diverted,
            count(DISTINCT carrier) AS unique_carriers
        FROM flights
        WHERE {where}
        GROUP BY airport
        HAVING total_flights >= 100
        ORDER BY delay_percentage DESC
        LIMIT %(limit)s
        """,
        parameters=params,
    )


@st.cache_data(show_spinner=False, ttl=15)
def ch_year_comparison(year1: int, year2: int, months: Optional[List[int]]) -> Dict[str, Any]:
    """Compare two years."""
    kpis1 = ch_overview_kpis(year1, months)
    kpis2 = ch_overview_kpis(year2, months)
    
    return {
        'year1': year1,
        'year2': year2,
        'flights_change': safe_divide(kpis2['flights'] - kpis1['flights'], kpis1['flights']),
        'delay_rate_change': kpis2['delay_rate'] - kpis1['delay_rate'],
        'kpis1': kpis1,
        'kpis2': kpis2,
    }


@st.cache_data(show_spinner=False, ttl=10)
def ch_realtime_stats() -> pd.DataFrame:
    """Get real-time ingestion statistics."""
    return ch_query_df(
        """
        SELECT
            ingestion_minute,
            countMerge(record_count) AS record_count,
            sumMerge(total_flights) AS total_flights,
            sumMerge(total_delayed) AS total_delayed,
            avgMerge(avg_delay_rate) AS avg_delay_rate
        FROM realtime_stats
        WHERE ingestion_minute >= now() - INTERVAL 60 MINUTE
        GROUP BY ingestion_minute
        ORDER BY ingestion_minute
        """
    )


@st.cache_data(show_spinner=False, ttl=15)
def ch_detailed_carrier_stats(year: int, carrier: str, months: Optional[List[int]]) -> pd.DataFrame:
    """Get detailed statistics for a specific carrier."""
    where = f"year = %(year)s AND carrier = %(carrier)s"
    params: Dict[str, Any] = {"year": year, "carrier": carrier}
    if months:
        where += " AND month IN %(months)s"
        params["months"] = tuple(months)

    return ch_query_df(
        f"""
        SELECT
            month,
            count(*) AS records,
            sum(arr_flights) AS flights,
            sum(arr_del15) AS delayed,
            round(sum(arr_del15) * 100.0 / nullIf(sum(arr_flights), 0), 2) AS delay_pct,
            sum(arr_delay) AS delay_minutes,
            avg(arr_delay) AS avg_delay,
            sum(arr_cancelled) AS cancelled,
            sum(arr_diverted) AS diverted
        FROM flights
        WHERE {where}
        GROUP BY month
        ORDER BY month
        """,
        parameters=params,
    )


# ============================================================================
# UI COMPONENTS
# ============================================================================

def display_metric_box(label: str, value: str, subtext: str = "", color: str = COLOR_PRIMARY):
    """Display a clean metric box without HTML issues."""
    with st.container():
        st.metric(label=label, value=value, delta=subtext if subtext else None)


def display_section_title(title: str):
    """Display section title cleanly."""
    st.markdown(f"## {title}")


def display_subsection_title(title: str):
    """Display subsection title cleanly."""
    st.markdown(f"### {title}")


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main application entry point."""
    
    # Header
    st.markdown("---")
    st.title(f"{APP_TITLE} v{APP_VERSION}")
    st.markdown("Professional Real-time Data Pipeline Analytics Platform")
    st.markdown("---")
    
    # Custom CSS
    st.markdown("""
    <style>
        :root {
            --accent: #0ea5e9;
            --accent-strong: #0284c7;
            --card-bg: #0f243a;
            --card-border: #12385c;
            --text-muted: #cdd7e1;
        }
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0b1f33 0%, #102c49 45%, #0b1f33 100%);
            color: #f8fafc;
        }
        .sidebar-brand {
            padding: 14px 16px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 14px;
            margin-bottom: 12px;
        }
        .brand-title { font-size: 1.1rem; font-weight: 700; letter-spacing: 0.01em; }
        .brand-sub { font-size: 0.9rem; color: var(--text-muted); margin-top: 4px; }
        .brand-badge {
            margin-top: 8px;
            display: inline-block;
            padding: 6px 10px;
            background: rgba(14, 165, 233, 0.18);
            border: 1px solid rgba(14, 165, 233, 0.4);
            border-radius: 10px;
            font-size: 0.85rem;
            font-weight: 600;
            color: #e0f2fe;
        }
        .sidebar-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 12px 14px;
            margin-bottom: 12px;
            box-shadow: 0 6px 16px rgba(0,0,0,0.18);
        }
        .sidebar-card h4 {
            margin: 0 0 8px 0;
            font-size: 0.95rem;
            font-weight: 700;
            letter-spacing: 0.01em;
        }
        .chip-row button {
            border-radius: 12px;
            width: 100%;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
        }
        .chip-row button:hover {
            background: rgba(14,165,233,0.12);
            border-color: rgba(14,165,233,0.35);
        }
        .metric-mini {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.9rem;
            padding: 8px 10px;
            border-radius: 10px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            margin-bottom: 6px;
        }
        .stTabs [data-baseweb="tab-list"] { gap: 1.5rem; }
        h1, h2, h3 { color: #1f2937; }
    </style>
    """, unsafe_allow_html=True)
    
    # Sidebar configuration
    with st.sidebar:
        st.markdown(
            f"""
            <div class="sidebar-brand">
                <div class="brand-title">{APP_TITLE}</div>
                <div class="brand-sub">Monitoring, quality & reliability</div>
                <div class="brand-badge">Version {APP_VERSION}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Load available years and connection health
        years: List[int] = []
        clickhouse_ok = True
        try:
            years = ch_years()
            logger.info(f"Successfully fetched {len(years)} available years")
        except Exception as e:
            clickhouse_ok = False
            logger.error(f"ClickHouse connection failed: {str(e)}")
            st.error(f"ClickHouse connection failed: {str(e)[:80]}")
        
        # System status section
        st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
        st.markdown("<h4>System Status</h4>", unsafe_allow_html=True)
        
        status_color = "#22c55e" if clickhouse_ok else "#ef4444"
        status_label = "Online" if clickhouse_ok else "Offline"
        st.markdown(
            f"""
            <div class="metric-mini">
                <span>ClickHouse</span>
                <span style="color:{status_color};font-weight:700;">{status_label}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div class="metric-mini">
                <span>Kafka</span>
                <span style="color:#22c55e;font-weight:700;">Running</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        if clickhouse_ok and years:
            st.markdown(
                f"""
                <div class="metric-mini">
                    <span>Data Available</span>
                    <span style="color:#06b6d4;font-weight:700;">{len(years)} years</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        with st.expander("Configuration & Endpoints", expanded=False):
            st.write("**ClickHouse Configuration**")
            st.write(f"Host: {CLICKHOUSE_HOST}:{CLICKHOUSE_HTTP_PORT}")
            st.write(f"Database: {CLICKHOUSE_DATABASE}")
            st.divider()
            st.write("**Kafka Configuration**")
            st.write(f"Broker: {KAFKA_HOST}:{KAFKA_PORT}")
            st.write(f"Topic: {KAFKA_TOPIC}")
            st.write(f"Consumer Group: {KAFKA_GROUP_ID}")
        
        # Filters card
        with st.container():
            st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
            st.markdown("<h4>Period & Filters</h4>", unsafe_allow_html=True)
            
            if years:
                selected_year = st.selectbox("Year", years, index=len(years) - 1, key="year_select")
                available_months = ch_months(int(selected_year))
                month_labels = [MONTH_NAMES.get(m, str(m)) for m in available_months]
                label_to_month = {label: m for label, m in zip(month_labels, available_months)}

                if "selected_months" not in st.session_state:
                    st.session_state.selected_months = available_months

                def set_months(new_months: List[int]):
                    st.session_state.selected_months = sorted(new_months)
                    st.session_state.month_selector_labels = [MONTH_NAMES.get(m, str(m)) for m in st.session_state.selected_months]

                col_all, col_clear = st.columns(2)
                if col_all.button("All months", width="stretch"):
                    set_months(available_months)
                if col_clear.button("Clear", width="stretch"):
                    set_months([])

                col_q1, col_q2, col_q3, col_q4 = st.columns(4)
                for col, q in zip([col_q1, col_q2, col_q3, col_q4], ["Q1", "Q2", "Q3", "Q4"]):
                    if col.button(q, width="stretch"):
                        set_months([m for m in available_months if m in QUARTERS[q]])

                current_labels = st.session_state.get("month_selector_labels") or [MONTH_NAMES.get(m, str(m)) for m in st.session_state.selected_months]
                selected_month_labels = st.multiselect(
                    "Months",
                    options=month_labels,
                    default=current_labels,
                    key="month_multiselect",
                )
                selected_months = [label_to_month[x] for x in selected_month_labels] if selected_month_labels else None
                st.session_state.selected_months = selected_months if selected_months is not None else []
            else:
                selected_year = datetime.utcnow().year
                selected_months = None
                st.warning("No data available in database")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Refresh card
        with st.container():
            st.markdown('<div class="sidebar-card">', unsafe_allow_html=True)
            st.markdown("<h4>Refresh cadence</h4>", unsafe_allow_html=True)
            auto_refresh = st.toggle("Auto-refresh", value=True, key="auto_refresh_toggle")
            refresh_seconds = st.slider("Interval (seconds)", 5, 60, 15, key="refresh_slider")
            if auto_refresh:
                st_autorefresh(interval=refresh_seconds * 1000, key="auto_refresh")
            st.markdown('</div>', unsafe_allow_html=True)
        
        # System info
        with st.expander("System Information"):
            st.write(f"Version: {APP_VERSION}")
            st.write(f"Python: {os.sys.version_info.major}.{os.sys.version_info.minor}")
            st.write(f"Streamlit: {st.__version__}")
    
    # Main tabs
    tab_overview, tab_analysis, tab_comparison, tab_realtime, tab_reports = st.tabs([
        "Overview",
        "Analysis",
        "Comparison",
        "Real-time",
        "Reports & Export"
    ])
    
    # ========================================================================
    # TAB 1: OVERVIEW
    # ========================================================================
    with tab_overview:
        if not clickhouse_ok or not years:
            st.warning("Please ensure ClickHouse is running and contains data")
            return
        
        kpis = ch_overview_kpis(int(selected_year), selected_months)
        
        display_section_title("Key Performance Indicators")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Flights", format_number(kpis['flights']))
        with col2:
            st.metric("On-Time Flights", format_number(kpis['on_time']), 
                     delta=format_percentage(1 - kpis['delay_rate']))
        with col3:
            st.metric("Delayed Flights", format_number(kpis['delayed']), 
                     delta=format_percentage(kpis['delay_rate']))
        with col4:
            st.metric("Cancelled", format_number(kpis['cancelled']), 
                     delta=format_percentage(kpis['cancel_rate']))
        
        st.divider()
        
        # Delay metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Avg Delay (All Flights)", f"{kpis['avg_delay_per_flight']:.1f} min")
        with col2:
            st.metric("Avg Delay (Delayed Flights)", f"{kpis['avg_delay_when_delayed']:.1f} min")
        with col3:
            st.metric("Max Delay", f"{kpis['max_delay_minutes']:.0f} min")
        with col4:
            st.metric("Diverted Flights", format_number(kpis['diverted']), 
                     delta=format_percentage(kpis['divert_rate']))
        
        st.divider()
        
        # Flight status pie chart
        display_subsection_title("Flight Status Distribution")
        status_data = {
            "Status": ["On-Time", "Delayed", "Cancelled", "Diverted"],
            "Count": [kpis['on_time'], kpis['delayed'], kpis['cancelled'], kpis['diverted']]
        }
        df_status = pd.DataFrame(status_data)
        
        fig = px.pie(
            df_status,
            values="Count",
            names="Status",
            title="Flight Status Breakdown",
            color_discrete_sequence=[COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER, COLOR_INFO]
        )
        fig.update_layout(height=450)
        st.plotly_chart(fig, width="stretch")
    
    # ========================================================================
    # TAB 2: ANALYSIS
    # ========================================================================
    with tab_analysis:
        if not clickhouse_ok or not years:
            st.warning("Data not available")
            return
        
        display_section_title("Detailed Analysis")
        
        # Monthly trends
        display_subsection_title("Monthly Performance Trends")
        df_trend = ch_delay_trend_by_month(int(selected_year))
        
        if not df_trend.empty:
            fig = make_subplots(
                rows=1, cols=1,
                specs=[[{"secondary_y": True}]]
            )
            
            fig.add_trace(
                go.Scatter(
                    x=df_trend["month_name"],
                    y=df_trend["delay_rate"] * 100,
                    name="Delay Rate (%)",
                    mode="lines+markers",
                    line=dict(color=COLOR_DANGER, width=2),
                ),
                secondary_y=False,
            )
            
            fig.add_trace(
                go.Bar(
                    x=df_trend["month_name"],
                    y=df_trend["flights"],
                    name="Total Flights",
                    marker_color=COLOR_INFO,
                    opacity=0.5,
                ),
                secondary_y=True,
            )
            
            fig.update_yaxes(title_text="Delay Rate (%)", secondary_y=False)
            fig.update_yaxes(title_text="Number of Flights", secondary_y=True)
            fig.update_layout(height=450, hovermode="x unified")
            st.plotly_chart(fig, width="stretch")
        
        st.divider()
        
        # Delay causes
        display_subsection_title("Delay Root Cause Analysis")
        df_causes = ch_cause_breakdown(int(selected_year), selected_months)
        
        if not df_causes.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                fig = px.pie(
                    df_causes,
                    values="minutes",
                    names="cause",
                    title="Delay Distribution by Cause",
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, width="stretch")
            
            with col2:
                fig = px.bar(
                    df_causes.sort_values("minutes"),
                    x="minutes",
                    y="cause",
                    orientation='h',
                    title="Delay Minutes by Cause",
                    color="minutes",
                    color_continuous_scale="Reds",
                )
                fig.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig, width="stretch")
            
            # Detailed table
            df_display = df_causes.copy()
            df_display["Duration"] = df_display["minutes"].apply(format_duration)
            df_display["Percentage"] = df_display["percentage"].apply(format_percentage)
            st.dataframe(
                df_display[["cause", "Duration", "Percentage"]].rename(
                    columns={"cause": "Cause", "Duration": "Total Duration", "Percentage": "% of Total"}
                ),
                width="stretch",
                hide_index=True,
            )
    
    # ========================================================================
    # TAB 3: COMPARISON
    # ========================================================================
    with tab_comparison:
        if not clickhouse_ok or not years:
            st.warning("Data not available")
            return
        
        display_section_title("Year-over-Year Comparison")
        
        col1, col2 = st.columns(2)
        with col1:
            year1 = st.selectbox("First Year", years, index=max(0, len(years) - 2))
        with col2:
            year2 = st.selectbox("Second Year", years, index=len(years) - 1)
        
        if year1 != year2:
            comparison = ch_year_comparison(int(year1), int(year2), selected_months)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                flights_change = comparison['flights_change']
                st.metric(
                    f"Flight Volume Change ({year1} -> {year2})",
                    format_percentage(abs(flights_change)),
                    delta=f"{'increase' if flights_change > 0 else 'decrease'}"
                )
            with col2:
                delay_rate_change = comparison['delay_rate_change']
                st.metric(
                    f"Delay Rate Change ({year1} -> {year2})",
                    format_percentage(abs(delay_rate_change)),
                    delta=f"{'worse' if delay_rate_change > 0 else 'better'}"
                )
            with col3:
                st.metric(
                    f"Year {year1} Delay Rate",
                    format_percentage(comparison['kpis1']['delay_rate'])
                )
            
            st.divider()
            
            # Detailed comparison
            st.subheader("Detailed Metrics Comparison")
            
            comparison_data = {
                "Metric": [
                    "Total Flights",
                    "On-Time Flights",
                    "Delayed Flights",
                    "Cancelled Flights",
                    "Delay Rate",
                    "Cancel Rate",
                    "Avg Delay/Flight",
                    "Avg Delay/Delayed",
                ],
                str(year1): [
                    format_number(comparison['kpis1']['flights']),
                    format_number(comparison['kpis1']['on_time']),
                    format_number(comparison['kpis1']['delayed']),
                    format_number(comparison['kpis1']['cancelled']),
                    format_percentage(comparison['kpis1']['delay_rate']),
                    format_percentage(comparison['kpis1']['cancel_rate']),
                    f"{comparison['kpis1']['avg_delay_per_flight']:.1f} min",
                    f"{comparison['kpis1']['avg_delay_when_delayed']:.1f} min",
                ],
                str(year2): [
                    format_number(comparison['kpis2']['flights']),
                    format_number(comparison['kpis2']['on_time']),
                    format_number(comparison['kpis2']['delayed']),
                    format_number(comparison['kpis2']['cancelled']),
                    format_percentage(comparison['kpis2']['delay_rate']),
                    format_percentage(comparison['kpis2']['cancel_rate']),
                    f"{comparison['kpis2']['avg_delay_per_flight']:.1f} min",
                    f"{comparison['kpis2']['avg_delay_when_delayed']:.1f} min",
                ],
            }
            df_comparison = pd.DataFrame(comparison_data)
            st.dataframe(df_comparison, width="stretch", hide_index=True)
    
    # ========================================================================
    # TAB 4: REAL-TIME
    # ========================================================================
    with tab_realtime:
        display_section_title("Real-time Data Streaming")
        
        # Start Kafka consumer and check status
        kafka_ok, kafka_status = ensure_kafka_thread()
        buf: Deque[KafkaEvent] = get_kafka_buffer()
        
        # Log buffer status for debugging
        logger.info(f"Real-time tab loaded: buffer size = {len(buf)}, kafka_ok = {kafka_ok}, kafka_status = {kafka_status}")
        
        # Connection status display
        col_status1, col_status2 = st.columns(2)
        with col_status1:
            status_color = "#22c55e" if kafka_ok else "#ef4444"
            st.markdown(
                f"""
                <div style="padding:12px;border-radius:10px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);">
                    <strong style="color:#fff;">Kafka Consumer</strong>
                    <div style="color:{status_color};font-weight:700;margin-top:6px;">{kafka_status}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col_status2:
            buffer_pct = min(100, (len(buf) / 5000) * 100) if buf else 0
            st.markdown(
                f"""
                <div style="padding:12px;border-radius:10px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);">
                    <strong style="color:#fff;">Message Buffer</strong>
                    <div style="color:#0ea5e9;font-weight:700;margin-top:6px;">{len(buf):,} / 5000 ({buffer_pct:.0f}%)</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        
        st.divider()
        
        # Real-time metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            msg_per_min = kafka_messages_per_minute(buf, 1)
            color = "#22c55e" if msg_per_min > 0 else "#8b5cf6"
            st.markdown(
                f"""
                <div style="padding:16px;border-radius:10px;background:rgba(255,255,255,0.05);text-align:center;">
                    <div style="font-size:0.85rem;color:#9ca3af;">Messages/Min</div>
                    <div style="font-size:1.8rem;font-weight:700;color:{color};margin-top:8px;">{msg_per_min:.1f}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col2:
            msg_per_5min = kafka_messages_per_minute(buf, 5)
            st.markdown(
                f"""
                <div style="padding:16px;border-radius:10px;background:rgba(255,255,255,0.05);text-align:center;">
                    <div style="font-size:0.85rem;color:#9ca3af;">Messages/5Min</div>
                    <div style="font-size:1.8rem;font-weight:700;color:#0ea5e9;margin-top:8px;">{msg_per_5min:.1f}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col3:
            last_time = buf[-1].received_at.strftime("%H:%M:%S") if buf else "No messages"
            st.markdown(
                f"""
                <div style="padding:16px;border-radius:10px;background:rgba(255,255,255,0.05);text-align:center;">
                    <div style="font-size:0.85rem;color:#9ca3af;">Last Message</div>
                    <div style="font-size:1.2rem;font-weight:700;color:#f59e0b;margin-top:8px;">{last_time}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col4:
            if buf:
                oldest_time = (datetime.utcnow() - buf[0].received_at).total_seconds()
                age_text = f"{int(oldest_time)}s"
                if oldest_time > 3600:
                    age_text = f"{int(oldest_time / 3600)}h"
                elif oldest_time > 60:
                    age_text = f"{int(oldest_time / 60)}m"
            else:
                age_text = "N/A"
            st.markdown(
                f"""
                <div style="padding:16px;border-radius:10px;background:rgba(255,255,255,0.05);text-align:center;">
                    <div style="font-size:0.85rem;color:#9ca3af;">Oldest Message</div>
                    <div style="font-size:1.2rem;font-weight:700;color:#06b6d4;margin-top:8px;">{age_text}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        
        st.divider()
        
        # Latest messages
        display_subsection_title("Latest Kafka Messages (Last 50)")
        if buf and len(buf) > 0:
            latest = list(buf)[-50:]
            df_latest = pd.DataFrame([e.record for e in latest])
            
            if len(df_latest.columns) > 15:
                cols = st.columns(1)
                with cols[0]:
                    st.info(f"Showing {len(df_latest)} records with {len(df_latest.columns)} columns. Use horizontal scroll to view all columns.")
            
            st.dataframe(df_latest, width="stretch", height=400)
        else:
            st.warning("No Kafka messages in buffer. Waiting for data from Kafka broker...")
            st.info(f"Kafka Consumer Status: {kafka_status}")
            st.info(f"Kafka Broker: {KAFKA_HOST}:{KAFKA_PORT} | Topic: {KAFKA_TOPIC}")
        
        st.divider()
        
        # ClickHouse real-time stats
        display_subsection_title("Database Ingestion Statistics")
        try:
            df_rt = ch_realtime_stats()
            if not df_rt.empty:
                df_rt["avg_delay_rate"] = df_rt["avg_delay_rate"].astype(float)
                
                col1, col2 = st.columns(2)
                with col1:
                    fig = px.area(
                        df_rt,
                        x="ingestion_minute",
                        y="record_count",
                        title="Records Ingested per Minute",
                    )
                    fig.update_layout(height=350)
                    st.plotly_chart(fig, width="stretch")
                
                with col2:
                    fig = px.line(
                        df_rt,
                        x="ingestion_minute",
                        y="avg_delay_rate",
                        title="Average Delay Rate per Minute",
                        markers=True,
                    )
                    fig.update_yaxes(tickformat=".1%")
                    fig.update_layout(height=350)
                    st.plotly_chart(fig, width="stretch")
        except Exception as e:
            st.error(f"Could not fetch real-time stats: {str(e)}")
    
    # ========================================================================
    # TAB 5: REPORTS & EXPORT
    # ========================================================================
    with tab_reports:
        display_section_title("Reports & Data Export")
        
        st.subheader("Airlines Performance Report")
        
        # Top/Bottom carriers
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Carriers with Highest Delay Rate")
            df_carriers = ch_top_carriers(int(selected_year), selected_months, limit=10)
            if not df_carriers.empty:
                display_df = df_carriers[["carrier", "airline_name", "total_flights", "delay_percentage"]].copy()
                display_df.columns = ["Code", "Airline", "Flights", "Delay %"]
                st.dataframe(display_df, width="stretch", hide_index=True)
                
                # Download button
                csv = display_df.to_csv(index=False)
                st.download_button(
                    label="Download Carriers Report (CSV)",
                    data=csv,
                    file_name=f"carriers_report_{selected_year}.csv",
                    mime="text/csv"
                )
        
        with col2:
            st.markdown("#### Carriers with Most Flights")
            if not df_carriers.empty:
                df_volume = df_carriers.nlargest(10, "total_flights")[["carrier", "airline_name", "total_flights"]].copy()
                df_volume.columns = ["Code", "Airline", "Total Flights"]
                st.dataframe(df_volume, width="stretch", hide_index=True)
        
        st.divider()
        
        st.subheader("Airports Performance Report")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Airports with Highest Delay Rate")
            df_airports = ch_top_airports(int(selected_year), selected_months, limit=10)
            if not df_airports.empty:
                display_df = df_airports[["airport", "airport_full_name", "total_flights", "delay_percentage"]].copy()
                display_df.columns = ["Code", "Airport", "Flights", "Delay %"]
                st.dataframe(display_df, width="stretch", hide_index=True)
                
                csv = display_df.to_csv(index=False)
                st.download_button(
                    label="Download Airports Report (CSV)",
                    data=csv,
                    file_name=f"airports_report_{selected_year}.csv",
                    mime="text/csv"
                )
        
        with col2:
            st.markdown("#### Airports by Traffic Volume")
            if not df_airports.empty:
                df_volume = df_airports.nlargest(10, "total_flights")[["airport", "airport_full_name", "total_flights"]].copy()
                df_volume.columns = ["Code", "Airport", "Total Flights"]
                st.dataframe(df_volume, width="stretch", hide_index=True)
        
        st.divider()
        
        # Overall summary report
        st.subheader("Overall Summary Report")
        
        kpis = ch_overview_kpis(int(selected_year), selected_months)
        
        summary_text = f"""
**Report Period:** {selected_year} {'(Selected Months)' if selected_months else '(Full Year)'}

**FLIGHT STATISTICS:**
- Total Flights: {format_number(kpis['flights'])}
- On-Time Flights: {format_number(kpis['on_time'])} ({format_percentage(1 - kpis['delay_rate'])})
- Delayed Flights: {format_number(kpis['delayed'])} ({format_percentage(kpis['delay_rate'])})
- Cancelled Flights: {format_number(kpis['cancelled'])} ({format_percentage(kpis['cancel_rate'])})
- Diverted Flights: {format_number(kpis['diverted'])} ({format_percentage(kpis['divert_rate'])})

**DELAY STATISTICS:**
- Average Delay (All Flights): {kpis['avg_delay_per_flight']:.1f} minutes
- Average Delay (Delayed Only): {kpis['avg_delay_when_delayed']:.1f} minutes
- Total Delay Minutes: {format_number(kpis['delay_minutes'])}
- Maximum Delay: {kpis['max_delay_minutes']:.0f} minutes
- Minimum Delay: {kpis['min_delay_minutes']:.0f} minutes
"""
        
        st.markdown(summary_text)
        
        # Export summary
        st.download_button(
            label="Download Summary Report (TXT)",
            data=summary_text,
            file_name=f"summary_report_{selected_year}.txt",
            mime="text/plain"
        )
    
    # Footer
    st.divider()
    st.markdown(f"Airline Delays Analytics v{APP_VERSION} | Powered by Streamlit, ClickHouse & Kafka")


if __name__ == "__main__":
    main()
