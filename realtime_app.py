"""
Airline Data Pipeline - Dashboard Professionnel v7.0
Temps Reel avec Kafka Consumer Thread
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import clickhouse_connect
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Deque, Tuple
from dataclasses import dataclass
from enum import Enum
from collections import deque
import threading
import logging
import json
import time
import sys

try:
    from confluent_kafka import Consumer, KafkaError
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False

try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH_AVAILABLE = True
except ImportError:
    AUTOREFRESH_AVAILABLE = False

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================
APP_VERSION = "7.0.0"
CLICKHOUSE_HOST = "localhost"
CLICKHOUSE_PORT = 8123
CLICKHOUSE_DB = "airline_data"

# Kafka config - localhost pour dev local
KAFKA_HOST = "localhost"
KAFKA_PORT = 9092
KAFKA_TOPIC = "airline-delays"
KAFKA_GROUP_ID = "streamlit-realtime-dashboard"
KAFKA_MAX_RETRIES = 3
KAFKA_RETRY_DELAY = 5

MONTHS_FR = ["Jan", "Fev", "Mar", "Avr", "Mai", "Juin", "Juil", "Aout", "Sep", "Oct", "Nov", "Dec"]

# =============================================================================
# PAGE CONFIG
# =============================================================================
st.set_page_config(
    page_title="Airline Data Pipeline",
    page_icon="A",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# DATA CLASSES
# =============================================================================
@dataclass(frozen=True)
class KafkaEvent:
    received_at: datetime
    record: Dict[str, Any]
    raw: str

class Status(Enum):
    ONLINE = "online"
    WARNING = "warning"
    OFFLINE = "offline"

@dataclass
class PipelineStatus:
    clickhouse: Status = Status.OFFLINE
    kafka: Status = Status.OFFLINE
    nifi: Status = Status.OFFLINE
    ml: Status = Status.OFFLINE

@dataclass
class Metrics:
    total_records: int = 0
    flights: int = 0
    delayed: int = 0
    carriers: int = 0
    airports: int = 0
    delay_rate: float = 0.0
    year_min: int = 0
    year_max: int = 0

# =============================================================================
# KAFKA SHARED STATE (cache_resource pour persistance)
# =============================================================================
@st.cache_resource
def get_kafka_buffer() -> Deque[KafkaEvent]:
    """Buffer Kafka partage qui survit aux reruns Streamlit."""
    buf = deque(maxlen=5000)
    logger.info(f"Buffer Kafka cree (id={id(buf)})")
    return buf

@st.cache_resource
def get_kafka_stop_event() -> threading.Event:
    """Event stop pour le thread Kafka."""
    stop = threading.Event()
    logger.info(f"Stop event cree (id={id(stop)})")
    return stop

class _KafkaThreadHolder:
    thread: Optional[threading.Thread] = None
    start_time: Optional[datetime] = None

@st.cache_resource
def get_kafka_thread_holder() -> _KafkaThreadHolder:
    return _KafkaThreadHolder()

def get_kafka_thread() -> Optional[threading.Thread]:
    return get_kafka_thread_holder().thread

def set_kafka_thread(thread: Optional[threading.Thread]) -> None:
    get_kafka_thread_holder().thread = thread

def set_kafka_start_time(start_time: datetime) -> None:
    get_kafka_thread_holder().start_time = start_time

def get_kafka_start_time() -> Optional[datetime]:
    return get_kafka_thread_holder().start_time

# =============================================================================
# KAFKA FUNCTIONS
# =============================================================================
def parse_kafka_payload(raw: str) -> List[Dict[str, Any]]:
    """Parse Kafka message - JSON standard ou array."""
    try:
        parsed = json.loads(raw)
    except Exception as e:
        logger.debug(f"JSON parse error: {str(e)[:50]}")
        return []

    if isinstance(parsed, dict):
        return [parsed]
    
    if isinstance(parsed, list):
        if len(parsed) == 0:
            return []
        if all(isinstance(x, dict) for x in parsed):
            return [d for d in parsed if isinstance(d, dict)]
    
    return []

def kafka_consumer_loop(buffer: Deque[KafkaEvent], stop_event: threading.Event) -> None:
    """Thread background pour consommer les messages Kafka."""
    consumer = None
    retry_count = 0
    message_count = 0
    
    try:
        while not stop_event.is_set() and retry_count < KAFKA_MAX_RETRIES:
            try:
                conf = {
                    'bootstrap.servers': f"{KAFKA_HOST}:{KAFKA_PORT}",
                    'group.id': KAFKA_GROUP_ID,
                    'auto.offset.reset': 'latest',
                    'enable.auto.commit': False,
                    'session.timeout.ms': 60000,
                    'socket.timeout.ms': 10000,
                    'fetch.wait.max.ms': 100,
                }
                
                logger.info(f"Kafka consumer connexion a {KAFKA_HOST}:{KAFKA_PORT}")
                consumer = Consumer(conf)
                consumer.subscribe([KAFKA_TOPIC])
                retry_count = 0
                logger.info(f"Kafka consumer abonne au topic: {KAFKA_TOPIC}")
                message_count = 0
                
                poll_count = 0
                while not stop_event.is_set():
                    try:
                        msg = consumer.poll(timeout=2.0)
                        poll_count += 1
                        
                        if msg is None:
                            if poll_count % 30 == 0:
                                logger.debug(f"Kafka poll timeout - {poll_count} polls, buffer: {len(buffer)}")
                            continue
                            
                        if msg.error():
                            if msg.error().code() == KafkaError._PARTITION_EOF:
                                continue
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
                                        if message_count % 50 == 0:
                                            logger.info(f"Kafka: {message_count} messages, buffer: {len(buffer)}")
                                        if message_count == 1:
                                            logger.info(f"Premier message! Keys: {list(record.keys())[:10]}")
                                    
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
        logger.error(f"Fatal error in Kafka consumer: {str(e)}")
    finally:
        if consumer is not None:
            try:
                consumer.close()
                logger.info(f"Kafka consumer ferme. Total messages: {message_count}")
            except Exception as e:
                logger.warning(f"Error closing Kafka consumer: {str(e)}")

def ensure_kafka_thread() -> Tuple[bool, str]:
    """Assure que le thread Kafka tourne."""
    if not KAFKA_AVAILABLE:
        return False, "Kafka non disponible"
    
    buf = get_kafka_buffer()
    stop = get_kafka_stop_event()
    thread = get_kafka_thread()
    
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
            logger.info(f"Kafka thread demarre (buffer id={id(buf)})")
            return True, "Connecte"
        except Exception as e:
            logger.error(f"Failed to start Kafka thread: {str(e)}")
            return False, f"Erreur: {str(e)[:50]}"
    
    start_time = get_kafka_start_time() or datetime.utcnow()
    uptime = datetime.utcnow() - start_time
    return True, f"En ligne ({int(uptime.total_seconds())}s)"

def kafka_messages_per_minute(buffer: Deque[KafkaEvent], window_minutes: int = 1) -> float:
    """Calcule le taux de messages Kafka (thread-safe)."""
    if not buffer:
        return 0.0
    try:
        # Copie thread-safe du buffer
        snapshot = list(buffer)
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        count = sum(1 for e in snapshot if e.received_at >= cutoff)
        return float(count) / float(window_minutes)
    except RuntimeError:
        # Si mutation pendant copie, retourner estimation
        return float(len(buffer)) / float(window_minutes)

# =============================================================================
# CSS PROFESSIONNEL
# =============================================================================
st.markdown("""
<style>
    :root {
        --primary: #7c3aed;
        --primary-light: #a78bfa;
        --primary-dark: #5b21b6;
        --success: #10b981;
        --warning: #f59e0b;
        --danger: #ef4444;
        --info: #3b82f6;
        --bg-main: #f5f7fa;
        --bg-card: #ffffff;
        --bg-sidebar: #fafbfc;
        --text-dark: #1f2937;
        --text-gray: #6b7280;
        --text-light: #9ca3af;
        --border: #e5e7eb;
        --shadow: rgba(0, 0, 0, 0.08);
    }
    
    .stApp {
        background: var(--bg-main) !important;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: var(--bg-sidebar) !important;
        border-right: 1px solid var(--border);
    }
    
    [data-testid="stSidebar"] * {
        color: var(--text-dark) !important;
    }
    
    .main-header {
        background: linear-gradient(135deg, var(--primary) 0%, #9333ea 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 20px rgba(124, 58, 237, 0.25);
    }
    
    .main-title {
        font-size: 2rem;
        font-weight: 700;
        color: white;
        margin: 0;
    }
    
    .main-subtitle {
        font-size: 1rem;
        color: rgba(255,255,255,0.9);
        margin-top: 0.25rem;
    }
    
    .version-badge {
        display: inline-block;
        background: rgba(255,255,255,0.2);
        padding: 0.3rem 0.8rem;
        border-radius: 16px;
        font-size: 0.8rem;
        color: white;
        margin-top: 0.75rem;
    }
    
    .metric-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1.25rem;
        text-align: center;
        box-shadow: 0 2px 8px var(--shadow);
    }
    
    .status-container {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }
    
    .status-row {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.6rem 0.8rem;
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 8px;
    }
    
    .status-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
    }
    
    .status-dot.online {
        background: var(--success);
        box-shadow: 0 0 6px var(--success);
    }
    
    .status-dot.warning {
        background: var(--warning);
        box-shadow: 0 0 6px var(--warning);
    }
    
    .status-dot.offline {
        background: var(--danger);
        box-shadow: 0 0 6px var(--danger);
    }
    
    .status-name {
        font-size: 0.85rem;
        color: var(--text-dark);
    }
    
    .section-title {
        font-size: 1.2rem;
        font-weight: 600;
        color: var(--text-dark);
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid var(--primary);
    }
    
    /* Metric cards override for Streamlit */
    [data-testid="stMetric"] {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 2px 8px var(--shadow);
    }
    
    [data-testid="stMetric"] label {
        color: var(--text-gray) !important;
    }
    
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: var(--text-dark) !important;
    }
    
    /* Realtime specific */
    .rt-metric-box {
        padding: 1rem;
        border-radius: 12px;
        background: var(--bg-card);
        border: 1px solid var(--border);
        text-align: center;
        box-shadow: 0 2px 8px var(--shadow);
    }
    
    .rt-metric-label {
        font-size: 0.85rem;
        color: var(--text-gray);
    }
    
    .rt-metric-value {
        font-size: 1.6rem;
        font-weight: 700;
        margin-top: 6px;
        color: var(--text-dark);
    }
    
    .rt-status-box {
        padding: 10px;
        border-radius: 10px;
        background: var(--bg-card);
        border: 1px solid var(--border);
    }
    
    .kafka-message-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 0.5rem;
        box-shadow: 0 1px 4px var(--shadow);
    }
    
    .kafka-msg-header {
        display: flex;
        justify-content: space-between;
        margin-bottom: 0.5rem;
    }
    
    .kafka-msg-carrier {
        font-weight: 700;
        color: var(--primary);
    }
    
    .kafka-msg-time {
        font-size: 0.8rem;
        color: var(--text-light);
    }
    
    .kafka-msg-stats {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 0.5rem;
        font-size: 0.85rem;
    }
    
    .kafka-msg-stat {
        text-align: center;
        padding: 4px;
        border-radius: 6px;
        background: var(--bg-main);
    }
    
    .kafka-msg-stat-value {
        font-weight: 600;
        color: var(--text-dark);
    }
    
    .kafka-msg-stat-label {
        font-size: 0.7rem;
        color: var(--text-gray);
    }
    
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }
    
    .live-indicator {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        background: rgba(239, 68, 68, 0.1);
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        color: var(--danger);
    }
    
    .live-dot {
        width: 8px;
        height: 8px;
        background: var(--danger);
        border-radius: 50%;
        animation: pulse 1.5s infinite;
    }
    
    .scroll-container {
        max-height: 500px;
        overflow-y: auto;
        padding-right: 0.5rem;
    }
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        background: var(--bg-card);
        border-radius: 10px;
        padding: 4px;
        gap: 4px;
        border: 1px solid var(--border);
    }
    
    .stTabs [data-baseweb="tab"] {
        color: var(--text-dark) !important;
        border-radius: 8px;
        background: transparent !important;
    }
    
    .stTabs [aria-selected="true"] {
        background: var(--primary) !important;
        color: white !important;
    }
    
    /* DataFrames - Force light theme */
    .stDataFrame, [data-testid="stDataFrame"] {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
    }
    
    .stDataFrame table, [data-testid="stDataFrame"] table {
        background: var(--bg-card) !important;
    }
    
    .stDataFrame th, [data-testid="stDataFrame"] th {
        background: var(--bg-main) !important;
        color: var(--text-dark) !important;
        border-bottom: 2px solid var(--border) !important;
    }
    
    .stDataFrame td, [data-testid="stDataFrame"] td {
        background: var(--bg-card) !important;
        color: var(--text-dark) !important;
        border-bottom: 1px solid var(--border) !important;
    }
    
    .stDataFrame tr:hover td, [data-testid="stDataFrame"] tr:hover td {
        background: var(--bg-main) !important;
    }
    
    /* Glide Data Grid override for tables */
    [data-testid="stDataFrame"] > div {
        background: var(--bg-card) !important;
    }
    
    .dvn-scroller {
        background: var(--bg-card) !important;
    }
    
    /* SelectBox / Dropdowns */
    [data-testid="stSelectbox"], .stSelectbox {
        background: var(--bg-card) !important;
    }
    
    [data-testid="stSelectbox"] > div > div,
    .stSelectbox > div > div {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        color: var(--text-dark) !important;
    }
    
    [data-baseweb="select"] {
        background: var(--bg-card) !important;
    }
    
    [data-baseweb="select"] > div {
        background: var(--bg-card) !important;
        border-color: var(--border) !important;
        color: var(--text-dark) !important;
    }
    
    [data-baseweb="popover"] {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
    }
    
    [data-baseweb="menu"] {
        background: var(--bg-card) !important;
    }
    
    [data-baseweb="menu"] li {
        background: var(--bg-card) !important;
        color: var(--text-dark) !important;
    }
    
    [data-baseweb="menu"] li:hover {
        background: var(--bg-main) !important;
    }
    
    /* Input labels */
    .stSelectbox label, .stTextInput label, .stNumberInput label,
    [data-testid="stWidgetLabel"] {
        color: var(--text-dark) !important;
    }
    
    /* Text inputs */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        color: var(--text-dark) !important;
    }
    
    /* Checkbox */
    .stCheckbox label {
        color: var(--text-dark) !important;
    }
    
    /* Slider */
    .stSlider label {
        color: var(--text-dark) !important;
    }
    
    /* Charts container */
    [data-testid="stPlotlyChart"] {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 2px 8px var(--shadow);
    }
    
    /* Main content text */
    .stMarkdown, .stMarkdown p, .stMarkdown span {
        color: var(--text-dark) !important;
    }
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        color: var(--text-dark) !important;
    }
    
    /* Info, Warning, Error boxes */
    .stAlert {
        border-radius: 8px !important;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background: var(--bg-card) !important;
        color: var(--text-dark) !important;
    }
    
    /* Main container */
    [data-testid="stMainBlockContainer"] {
        background: var(--bg-main) !important;
    }
    
    /* Section titles fix */
    .section-title {
        color: var(--text-dark) !important;
    }
    
    /* Force all text dark */
    p, span, div {
        color: inherit;
    }
    
    /* Override any dark mode remnants */
    [data-testid="stAppViewContainer"] {
        background: var(--bg-main) !important;
    }
    
    /* Scrollbar styling */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: var(--bg-main);
    }
    
    ::-webkit-scrollbar-thumb {
        background: var(--text-light);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: var(--text-gray);
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# DATABASE CONNECTION
# =============================================================================
_clickhouse_client_cache = None

def get_clickhouse_client(force_new=False):
    """Get ClickHouse client with connection retry logic."""
    global _clickhouse_client_cache
    
    # Use cached client if available and not forcing new connection
    if _clickhouse_client_cache is not None and not force_new:
        try:
            # Test if connection is still alive
            _clickhouse_client_cache.query("SELECT 1")
            return _clickhouse_client_cache
        except:
            _clickhouse_client_cache = None
    
    # Try to create new connection with retry
    for attempt in range(3):
        try:
            client = clickhouse_connect.get_client(
                host=CLICKHOUSE_HOST,
                port=CLICKHOUSE_PORT,
                database=CLICKHOUSE_DB,
                connect_timeout=5,
            )
            # Test connection
            client.query("SELECT 1")
            _clickhouse_client_cache = client
            logger.info(f"ClickHouse connected successfully on attempt {attempt + 1}")
            return client
        except Exception as e:
            logger.warning(f"ClickHouse connection attempt {attempt + 1} failed: {e}")
            time.sleep(1)  # Wait 1 second before retry
    
    logger.error("ClickHouse connection failed after 3 attempts")
    return None

# =============================================================================
# DATA LOADING
# =============================================================================
# Note: Pas de cache ici pour toujours avoir des donnees fraiches
def load_metrics() -> Metrics:
    client = get_clickhouse_client()
    if not client:
        return Metrics()
    
    try:
        result = client.query("""
            SELECT 
                count() as total,
                sum(arr_flights) as flights,
                sum(arr_del15) as delayed,
                count(DISTINCT carrier) as carriers,
                count(DISTINCT airport) as airports,
                min(year) as year_min,
                max(year) as year_max
            FROM flights
        """)
        row = result.result_rows[0]
        
        flights = int(row[1]) if row[1] else 0
        delayed = int(row[2]) if row[2] else 0
        
        return Metrics(
            total_records=int(row[0]) if row[0] else 0,
            flights=flights,
            delayed=delayed,
            carriers=int(row[3]) if row[3] else 0,
            airports=int(row[4]) if row[4] else 0,
            delay_rate=delayed / flights if flights > 0 else 0,
            year_min=int(row[5]) if row[5] else 0,
            year_max=int(row[6]) if row[6] else 0,
        )
    except Exception as e:
        logger.error(f"Error loading metrics: {e}")
        return Metrics()

@st.cache_data(ttl=60)
def load_years() -> List[int]:
    client = get_clickhouse_client()
    if not client:
        return []
    
    try:
        result = client.query("SELECT DISTINCT year FROM flights ORDER BY year DESC")
        return [int(row[0]) for row in result.result_rows]
    except Exception as e:
        logger.error(f"Error loading years: {e}")
        return []

@st.cache_data(ttl=60)
def load_monthly_data(year: Optional[int] = None) -> pd.DataFrame:
    client = get_clickhouse_client()
    if not client:
        return pd.DataFrame()
    
    try:
        where = f"WHERE year = {year}" if year else ""
        result = client.query(f"""
            SELECT 
                year, month,
                sum(arr_flights) as flights,
                sum(arr_del15) as delayed
            FROM flights
            {where}
            GROUP BY year, month
            ORDER BY year, month
        """)
        
        if not result.result_rows:
            return pd.DataFrame()
            
        df = pd.DataFrame(result.result_rows, columns=['year', 'month', 'flights', 'delayed'])
        df['delay_rate'] = df['delayed'] / df['flights'].replace(0, 1)
        return df
    except Exception as e:
        logger.error(f"Error loading monthly data: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_carrier_data(year: Optional[int] = None) -> pd.DataFrame:
    client = get_clickhouse_client()
    if not client:
        return pd.DataFrame()
    
    try:
        where = f"WHERE year = {year}" if year else ""
        result = client.query(f"""
            SELECT 
                carrier,
                any(carrier_name) as carrier_name,
                sum(arr_flights) as flights,
                sum(arr_del15) as delayed
            FROM flights
            {where}
            GROUP BY carrier
            ORDER BY flights DESC
            LIMIT 15
        """)
        
        if not result.result_rows:
            return pd.DataFrame()
            
        df = pd.DataFrame(result.result_rows, columns=['carrier', 'carrier_name', 'flights', 'delayed'])
        df['delay_rate'] = df['delayed'] / df['flights'].replace(0, 1)
        return df
    except Exception as e:
        logger.error(f"Error loading carrier data: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_airport_data(year: Optional[int] = None) -> pd.DataFrame:
    client = get_clickhouse_client()
    if not client:
        return pd.DataFrame()
    
    try:
        where = f"WHERE year = {year}" if year else ""
        result = client.query(f"""
            SELECT 
                airport,
                any(airport_name) as airport_name,
                sum(arr_flights) as flights,
                sum(arr_del15) as delayed
            FROM flights
            {where}
            GROUP BY airport
            ORDER BY flights DESC
            LIMIT 15
        """)
        
        if not result.result_rows:
            return pd.DataFrame()
            
        df = pd.DataFrame(result.result_rows, columns=['airport', 'airport_name', 'flights', 'delayed'])
        df['delay_rate'] = df['delayed'] / df['flights'].replace(0, 1)
        return df
    except Exception as e:
        logger.error(f"Error loading airport data: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_delay_causes(year: Optional[int] = None) -> pd.DataFrame:
    client = get_clickhouse_client()
    if not client:
        return pd.DataFrame()
    
    try:
        where = f"WHERE year = {year}" if year else ""
        result = client.query(f"""
            SELECT 
                sum(carrier_delay) as carrier,
                sum(weather_delay) as weather,
                sum(nas_delay) as nas,
                sum(security_delay) as security,
                sum(late_aircraft_delay) as late_aircraft
            FROM flights
            {where}
        """)
        
        if not result.result_rows:
            return pd.DataFrame()
            
        row = result.result_rows[0]
        data = {
            'cause': ['Compagnie', 'Meteo', 'NAS', 'Securite', 'Avion en retard'],
            'minutes': [float(v) if v else 0 for v in row]
        }
        return pd.DataFrame(data)
    except Exception as e:
        logger.error(f"Error loading delay causes: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_detailed_data(year: Optional[int] = None) -> pd.DataFrame:
    client = get_clickhouse_client()
    if not client:
        return pd.DataFrame()
    
    try:
        where = f"WHERE year = {year}" if year else ""
        result = client.query(f"""
            SELECT 
                year, month, carrier, carrier_name, airport, airport_name,
                arr_flights, arr_del15, arr_delay
            FROM flights
            {where}
            ORDER BY year DESC, month DESC
            LIMIT 1000
        """)
        
        if not result.result_rows:
            return pd.DataFrame()
            
        return pd.DataFrame(
            result.result_rows,
            columns=['year', 'month', 'carrier', 'carrier_name', 'airport', 'airport_name', 'arr_flights', 'arr_del15', 'arr_delay']
        )
    except Exception as e:
        logger.error(f"Error loading detailed data: {e}")
        return pd.DataFrame()

def load_realtime_stats() -> pd.DataFrame:
    """Stats temps reel depuis ClickHouse."""
    client = get_clickhouse_client()
    if not client:
        return pd.DataFrame()
    
    try:
        # Essayer la vue materialisee
        result = client.query("""
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
        """)
        
        if result.result_rows:
            return pd.DataFrame(
                result.result_rows,
                columns=['ingestion_minute', 'record_count', 'total_flights', 'total_delayed', 'avg_delay_rate']
            )
    except:
        pass
    
    # Fallback: compter les records recents
    try:
        result = client.query("""
            SELECT 
                count() as total,
                max(year) as latest_year,
                max(month) as latest_month
            FROM flights
        """)
        if result.result_rows:
            row = result.result_rows[0]
            return pd.DataFrame({
                'total': [row[0]],
                'latest_year': [row[1]],
                'latest_month': [row[2]]
            })
    except:
        pass
    
    return pd.DataFrame()

# =============================================================================
# PIPELINE STATUS
# =============================================================================
def check_pipeline_status() -> PipelineStatus:
    status = PipelineStatus()
    
    # ClickHouse
    client = get_clickhouse_client()
    if client:
        try:
            client.query("SELECT 1")
            status.clickhouse = Status.ONLINE
        except:
            status.clickhouse = Status.WARNING
    
    # Kafka
    if KAFKA_AVAILABLE:
        kafka_ok, _ = ensure_kafka_thread()
        status.kafka = Status.ONLINE if kafka_ok else Status.WARNING
    else:
        status.kafka = Status.OFFLINE
    
    # NiFi
    status.nifi = Status.ONLINE if status.clickhouse == Status.ONLINE else Status.WARNING
    
    # ML
    try:
        import os
        if os.path.exists("yno-ml/models") or os.path.exists("models"):
            status.ml = Status.ONLINE
        else:
            status.ml = Status.WARNING
    except:
        status.ml = Status.OFFLINE
    
    return status

# =============================================================================
# CHARTS
# =============================================================================
def create_monthly_chart(data: pd.DataFrame) -> go.Figure:
    if data.empty:
        fig = go.Figure()
        fig.add_annotation(text="Pas de donnees", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(template="plotly_white", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=450)
        return fig
    
    monthly_agg = data.groupby('month').agg({
        'flights': 'sum',
        'delayed': 'sum'
    }).reset_index()
    monthly_agg['delay_rate'] = monthly_agg['delayed'] / monthly_agg['flights'].replace(0, 1)
    monthly_agg['on_time'] = monthly_agg['flights'] - monthly_agg['delayed']
    
    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.7, 0.3],
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
        vertical_spacing=0.12,
        subplot_titles=("Volume et Retards par Mois", "Taux de Retard (%)")
    )
    
    fig.add_trace(
        go.Bar(x=monthly_agg['month'], y=monthly_agg['on_time'], name='A l\'heure',
               marker_color='#10b981', hovertemplate='Mois: %{x}<br>A l\'heure: %{y:,.0f}<extra></extra>'),
        row=1, col=1, secondary_y=False,
    )
    
    fig.add_trace(
        go.Bar(x=monthly_agg['month'], y=monthly_agg['delayed'], name='Retardes',
               marker_color='#ef4444', hovertemplate='Mois: %{x}<br>Retardes: %{y:,.0f}<extra></extra>'),
        row=1, col=1, secondary_y=False,
    )
    
    fig.add_trace(
        go.Scatter(x=monthly_agg['month'], y=monthly_agg['flights'], name='Total Vols',
                   line=dict(color='#6366f1', width=3, dash='dot'), mode='lines+markers',
                   marker=dict(size=8, symbol='diamond')),
        row=1, col=1, secondary_y=True,
    )
    
    colors = ['#ef4444' if r > 0.2 else '#f59e0b' if r > 0.15 else '#10b981' for r in monthly_agg['delay_rate']]
    
    fig.add_trace(
        go.Bar(x=monthly_agg['month'], y=monthly_agg['delay_rate'] * 100, name='Taux Retard',
               marker_color=colors, text=[f"{r*100:.1f}%" for r in monthly_agg['delay_rate']],
               textposition='outside', textfont=dict(size=10, color='white'), showlegend=False),
        row=2, col=1,
    )
    
    fig.add_hline(y=15, line_dash="dash", line_color="#f59e0b", line_width=1, 
                  annotation_text="Seuil 15%", annotation_position="right", row=2, col=1)
    
    fig.update_layout(
        template="plotly_white", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        height=550, barmode='stack',
        legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="center", x=0.5,
                    bgcolor='rgba(0,0,0,0.3)', bordercolor='#334155', borderwidth=1),
        margin=dict(t=80, b=40),
    )
    
    fig.update_xaxes(tickmode='array', tickvals=list(range(1, 13)), ticktext=MONTHS_FR, gridcolor='rgba(255,255,255,0.1)', row=1, col=1)
    fig.update_xaxes(tickmode='array', tickvals=list(range(1, 13)), ticktext=MONTHS_FR, gridcolor='rgba(255,255,255,0.1)', row=2, col=1)
    fig.update_yaxes(title_text="Vols", gridcolor='rgba(255,255,255,0.1)', row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Total", gridcolor='rgba(255,255,255,0.1)', row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="Taux (%)", gridcolor='rgba(255,255,255,0.1)', range=[0, max(monthly_agg['delay_rate'] * 100) * 1.3], row=2, col=1)
    fig.update_annotations(font=dict(size=12, color='#94a3b8'))
    
    return fig

def create_carrier_chart(data: pd.DataFrame) -> go.Figure:
    if data.empty:
        fig = go.Figure()
        fig.add_annotation(text="Pas de donnees", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    
    colors = ['#ef4444' if rate > 0.2 else '#f59e0b' if rate > 0.15 else '#10b981' for rate in data['delay_rate']]
    
    fig = go.Figure(go.Bar(
        x=data['delay_rate'] * 100, y=data['carrier'], orientation='h',
        marker_color=colors, text=[f"{r*100:.1f}%" for r in data['delay_rate']], textposition='outside',
    ))
    
    fig.update_layout(
        template="plotly_white", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        height=400, yaxis=dict(categoryorder='total ascending'), xaxis_title="Taux de retard (%)",
    )
    return fig

def create_airport_chart(data: pd.DataFrame) -> go.Figure:
    if data.empty:
        fig = go.Figure()
        fig.add_annotation(text="Pas de donnees", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    
    colors = ['#ef4444' if rate > 0.2 else '#f59e0b' if rate > 0.15 else '#10b981' for rate in data['delay_rate']]
    
    fig = go.Figure(go.Bar(
        x=data['delay_rate'] * 100, y=data['airport'], orientation='h',
        marker_color=colors, text=[f"{r*100:.1f}%" for r in data['delay_rate']], textposition='outside',
    ))
    
    fig.update_layout(
        template="plotly_white", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        height=400, yaxis=dict(categoryorder='total ascending'), xaxis_title="Taux de retard (%)",
    )
    return fig

def create_delay_causes_chart(data: pd.DataFrame) -> go.Figure:
    if data.empty:
        fig = go.Figure()
        fig.add_annotation(text="Pas de donnees", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    
    colors = ['#6366f1', '#f59e0b', '#10b981', '#3b82f6', '#ef4444']
    
    fig = go.Figure(go.Pie(
        labels=data['cause'], values=data['minutes'], hole=0.5,
        marker_colors=colors, textinfo='label+percent', textposition='outside',
    ))
    
    fig.update_layout(
        template="plotly_white", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        height=400, showlegend=False,
    )
    return fig

# =============================================================================
# RENDER FUNCTIONS
# =============================================================================
def render_pipeline_status(status: PipelineStatus):
    def get_class(s: Status) -> str:
        return s.value
    
    def get_label(s: Status) -> str:
        labels = {Status.ONLINE: "En ligne", Status.WARNING: "Attention", Status.OFFLINE: "Hors ligne"}
        return labels.get(s, "Inconnu")
    
    st.markdown(f"""
    <div class="status-container">
        <div class="status-row">
            <span class="status-dot {get_class(status.clickhouse)}"></span>
            <span class="status-name">ClickHouse: {get_label(status.clickhouse)}</span>
        </div>
        <div class="status-row">
            <span class="status-dot {get_class(status.kafka)}"></span>
            <span class="status-name">Kafka: {get_label(status.kafka)}</span>
        </div>
        <div class="status-row">
            <span class="status-dot {get_class(status.nifi)}"></span>
            <span class="status-name">NiFi: {get_label(status.nifi)}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_kafka_message(event: KafkaEvent):
    """Affiche un message Kafka."""
    record = event.record
    carrier = record.get('carrier', 'N/A')
    airport = record.get('airport', 'N/A')
    flights = int(record.get('arr_flights', 0))
    delayed = int(record.get('arr_del15', 0))
    year = record.get('year', '')
    month = record.get('month', '')
    delay_minutes = int(record.get('arr_delay', 0))
    
    time_str = event.received_at.strftime("%H:%M:%S")
    
    st.markdown(f"""
    <div class="kafka-message-card">
        <div class="kafka-msg-header">
            <span class="kafka-msg-carrier">{carrier} - {airport}</span>
            <span class="kafka-msg-time">{time_str}</span>
        </div>
        <div class="kafka-msg-stats">
            <div class="kafka-msg-stat">
                <div class="kafka-msg-stat-value">{flights:,}</div>
                <div class="kafka-msg-stat-label">Vols</div>
            </div>
            <div class="kafka-msg-stat">
                <div class="kafka-msg-stat-value" style="color:#ef4444;">{delayed:,}</div>
                <div class="kafka-msg-stat-label">Retardes</div>
            </div>
            <div class="kafka-msg-stat">
                <div class="kafka-msg-stat-value">{delay_minutes:,}</div>
                <div class="kafka-msg-stat-label">Min retard</div>
            </div>
            <div class="kafka-msg-stat">
                <div class="kafka-msg-stat-value">{year}/{month}</div>
                <div class="kafka-msg-stat-label">Periode</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# =============================================================================
# MAIN
# =============================================================================
def main():
    # Load data
    metrics = load_metrics()
    pipeline_status = check_pipeline_status()
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1 class="main-title">Airline Data Pipeline</h1>
        <p class="main-subtitle">Dashboard Analytics Temps Reel - NiFi / Kafka / ClickHouse</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Metrics row
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Records", f"{metrics.total_records:,}")
    with col2:
        st.metric("Vols Analyses", f"{metrics.flights:,}")
    with col3:
        st.metric("Vols Retardes", f"{metrics.delayed:,}", delta=f"{metrics.delay_rate*100:.1f}%", delta_color="inverse")
    with col4:
        st.metric("Compagnies", f"{metrics.carriers}")
    with col5:
        st.metric("Aeroports", f"{metrics.airports}")
    
    # Sidebar
    selected_year = None  # Pas de filtre annee
    with st.sidebar:
        st.markdown("## Statut Pipeline")
        render_pipeline_status(pipeline_status)
        
        st.markdown("---")
        st.markdown("## Kafka Config")
        st.text(f"Broker: {KAFKA_HOST}:{KAFKA_PORT}")
        st.text(f"Topic: {KAFKA_TOPIC}")
        st.text(f"Group: {KAFKA_GROUP_ID}")
        
        st.markdown("---")
        st.markdown("## Auto-Refresh")
        auto_refresh = st.toggle("Activer", value=True)
        refresh_seconds = st.slider("Intervalle (sec)", 5, 60, 5, disabled=not auto_refresh)
        
        if auto_refresh and AUTOREFRESH_AVAILABLE:
            st_autorefresh(interval=refresh_seconds * 1000, key="auto_refresh")
    
    # Onglets
    tab1, tab2, tab3, tab4 = st.tabs(["Temps Reel", "Analyses", "Comparaisons", "Donnees"])
    
    # TAB 1: Temps Reel - SECTION PRINCIPALE
    with tab1:
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem;">
            <p class="section-title" style="margin: 0; border: none; padding: 0;">Streaming Temps Reel - NiFi/Kafka/ClickHouse</p>
            <span class="live-indicator">
                <span class="live-dot"></span>
                LIVE
            </span>
        </div>
        """, unsafe_allow_html=True)
        
        # Demarrer le consumer Kafka
        kafka_ok, kafka_status = ensure_kafka_thread()
        buf: Deque[KafkaEvent] = get_kafka_buffer()
        
        logger.info(f"Tab Temps Reel: buffer={len(buf)}, kafka_ok={kafka_ok}, status={kafka_status}")
        
        # Status boxes
        st.markdown("### Statut des Connexions")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            ch_status = "En ligne" if pipeline_status.clickhouse == Status.ONLINE else "Hors ligne"
            ch_color = "#22c55e" if pipeline_status.clickhouse == Status.ONLINE else "#ef4444"
            st.markdown(f"""
            <div class="rt-status-box">
                <strong style="color:#fff;">ClickHouse</strong>
                <div style="color:{ch_color};font-weight:700;margin-top:6px;">{ch_status}</div>
                <div style="font-size:0.8rem;color:#9ca3af;margin-top:4px;">{CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            k_color = "#22c55e" if kafka_ok else "#ef4444"
            st.markdown(f"""
            <div class="rt-status-box">
                <strong style="color:#fff;">Kafka Consumer</strong>
                <div style="color:{k_color};font-weight:700;margin-top:6px;">{kafka_status}</div>
                <div style="font-size:0.8rem;color:#9ca3af;margin-top:4px;">{KAFKA_HOST}:{KAFKA_PORT}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            buffer_pct = min(100, (len(buf) / 5000) * 100) if buf else 0
            st.markdown(f"""
            <div class="rt-status-box">
                <strong style="color:#fff;">Message Buffer</strong>
                <div style="color:#0ea5e9;font-weight:700;margin-top:6px;">{len(buf):,} / 5000</div>
                <div style="font-size:0.8rem;color:#9ca3af;margin-top:4px;">{buffer_pct:.0f}% utilise</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Metriques temps reel
        st.markdown("### Metriques Kafka en Direct")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            msg_per_min = kafka_messages_per_minute(buf, 1)
            color = "#22c55e" if msg_per_min > 0 else "#8b5cf6"
            st.markdown(f"""
            <div class="rt-metric-box">
                <div class="rt-metric-label">Messages/Min</div>
                <div class="rt-metric-value" style="color:{color};">{msg_per_min:.1f}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            msg_per_5min = kafka_messages_per_minute(buf, 5)
            st.markdown(f"""
            <div class="rt-metric-box">
                <div class="rt-metric-label">Messages/5Min</div>
                <div class="rt-metric-value" style="color:#0ea5e9;">{msg_per_5min:.1f}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            try:
                last_time = list(buf)[-1].received_at.strftime("%H:%M:%S") if buf else "Aucun"
            except (IndexError, RuntimeError):
                last_time = "..."
            st.markdown(f"""
            <div class="rt-metric-box">
                <div class="rt-metric-label">Dernier Message</div>
                <div class="rt-metric-value" style="color:#f59e0b;font-size:1.2rem;">{last_time}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            try:
                if buf:
                    snapshot = list(buf)
                    if snapshot:
                        oldest = (datetime.utcnow() - snapshot[0].received_at).total_seconds()
                        if oldest > 3600:
                            age_text = f"{int(oldest / 3600)}h"
                        elif oldest > 60:
                            age_text = f"{int(oldest / 60)}m"
                        else:
                            age_text = f"{int(oldest)}s"
                    else:
                        age_text = "N/A"
                else:
                    age_text = "N/A"
            except (IndexError, RuntimeError):
                age_text = "..."
            st.markdown(f"""
            <div class="rt-metric-box">
                <div class="rt-metric-label">Plus Ancien</div>
                <div class="rt-metric-value" style="color:#06b6d4;font-size:1.2rem;">{age_text}</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Derniers messages Kafka
        st.markdown("### Derniers Messages Kafka (50 derniers)")
        
        try:
            # Copie thread-safe du buffer
            buffer_snapshot = list(buf) if buf else []
            buffer_len = len(buffer_snapshot)
        except RuntimeError:
            buffer_snapshot = []
            buffer_len = 0
        
        if buffer_len > 0:
            latest = buffer_snapshot[-50:][::-1]  # Derniers 50, plus recent en premier
            
            # Afficher en cards dans un container scrollable de hauteur fixe (5 messages visibles)
            st.markdown('<div style="max-height: 280px; overflow-y: auto; padding-right: 0.5rem;">', unsafe_allow_html=True)
            for event in latest:
                render_kafka_message(event)
            st.markdown('</div>', unsafe_allow_html=True)
            
        else:
            st.warning("Aucun message Kafka dans le buffer.")
            st.info(f"""
            **En attente de donnees...**
            
            Verifiez que:
            1. NiFi est en cours d'execution et le flow est demarre
            2. Kafka est accessible sur {KAFKA_HOST}:{KAFKA_PORT}
            3. Le topic '{KAFKA_TOPIC}' existe et recoit des messages
            
            **Status actuel:** {kafka_status}
            """)
        
        st.markdown("---")
        
        # Stats ClickHouse temps reel
        st.markdown("### Statistiques d'Ingestion ClickHouse")
        
        rt_stats = load_realtime_stats()
        if not rt_stats.empty and 'ingestion_minute' in rt_stats.columns:
            col1, col2 = st.columns(2)
            
            with col1:
                fig = px.area(
                    rt_stats, x="ingestion_minute", y="record_count",
                    title="Records Injectes par Minute",
                )
                fig.update_layout(template="plotly_white", paper_bgcolor='rgba(0,0,0,0)', 
                                  plot_bgcolor='rgba(0,0,0,0)', height=350)
                st.plotly_chart(fig, use_container_width=True, key="rt_records_chart")
            
            with col2:
                if 'avg_delay_rate' in rt_stats.columns:
                    fig = px.line(
                        rt_stats, x="ingestion_minute", y="avg_delay_rate",
                        title="Taux de Retard Moyen par Minute", markers=True,
                    )
                    fig.update_yaxes(tickformat=".1%")
                    fig.update_layout(template="plotly_white", paper_bgcolor='rgba(0,0,0,0)', 
                                      plot_bgcolor='rgba(0,0,0,0)', height=350)
                    st.plotly_chart(fig, use_container_width=True, key="rt_delay_chart")
        else:
            # Stats de base
            st.info("Vue materialisee 'realtime_stats' non disponible. Affichage des stats de base.")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Records ClickHouse", f"{metrics.total_records:,}")
            with col2:
                st.metric("Periode", f"{metrics.year_min} - {metrics.year_max}")
            with col3:
                st.metric("Taux Retard Global", f"{metrics.delay_rate*100:.1f}%")
    
    # TAB 2: Analyses
    with tab2:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<p class="section-title">Top Compagnies</p>', unsafe_allow_html=True)
            carrier_data = load_carrier_data(selected_year)
            st.plotly_chart(create_carrier_chart(carrier_data), use_container_width=True, key="carrier_chart")
            
            if not carrier_data.empty:
                worst = carrier_data.nlargest(3, 'delay_rate')
                st.error(f"Plus de retards: {', '.join(worst['carrier'].tolist())}")
        
        with col2:
            st.markdown('<p class="section-title">Top Aeroports</p>', unsafe_allow_html=True)
            airport_data = load_airport_data(selected_year)
            st.plotly_chart(create_airport_chart(airport_data), use_container_width=True, key="airport_chart")
            
            if not airport_data.empty:
                worst = airport_data.nlargest(3, 'delay_rate')
                st.error(f"Plus de retards: {', '.join(worst['airport'].tolist())}")
    
    # TAB 3: Comparaisons
    with tab3:
        st.markdown('<p class="section-title">Comparaison des Performances</p>', unsafe_allow_html=True)
        
        carrier_data = load_carrier_data(selected_year)
        if not carrier_data.empty:
            fig = px.scatter(
                carrier_data, x='flights', y='delay_rate', size='delayed', color='delay_rate',
                color_continuous_scale='RdYlGn_r', hover_name='carrier',
                labels={'flights': 'Nombre de vols', 'delay_rate': 'Taux de retard'},
            )
            fig.update_layout(template="plotly_white", paper_bgcolor='rgba(0,0,0,0)', 
                              plot_bgcolor='rgba(0,0,0,0)', height=500)
            st.plotly_chart(fig, use_container_width=True, key="scatter_chart")
        
        monthly_data = load_monthly_data(selected_year)
        if not monthly_data.empty and 'year' in monthly_data.columns:
            st.markdown('<p class="section-title">Heatmap des Retards</p>', unsafe_allow_html=True)
            
            pivot = monthly_data.pivot_table(index='year', columns='month', values='delay_rate', aggfunc='mean') * 100
            
            fig = go.Figure(go.Heatmap(
                z=pivot.values, x=[MONTHS_FR[i] for i in range(len(pivot.columns))],
                y=pivot.index.astype(str), colorscale='RdYlGn_r',
                text=[[f"{v:.1f}%" if not np.isnan(v) else "" for v in row] for row in pivot.values],
                texttemplate="%{text}",
            ))
            fig.update_layout(template="plotly_white", paper_bgcolor='rgba(0,0,0,0)', 
                              plot_bgcolor='rgba(0,0,0,0)', height=400)
            st.plotly_chart(fig, use_container_width=True, key="heatmap_chart")
    
    # TAB 4: Donnees
    with tab4:
        st.markdown('<p class="section-title">Donnees Detaillees</p>', unsafe_allow_html=True)
        
        detailed_data = load_detailed_data(selected_year)
        
        if not detailed_data.empty:
            col1, col2 = st.columns(2)
            with col1:
                carriers = ["Toutes"] + detailed_data['carrier'].unique().tolist()
                filter_carrier = st.selectbox("Compagnie", carriers)
            with col2:
                airports = ["Tous"] + detailed_data['airport'].unique().tolist()
                filter_airport = st.selectbox("Aeroport", airports)
            
            filtered = detailed_data.copy()
            if filter_carrier != "Toutes":
                filtered = filtered[filtered['carrier'] == filter_carrier]
            if filter_airport != "Tous":
                filtered = filtered[filtered['airport'] == filter_airport]
            
            st.markdown(f"**{len(filtered):,} enregistrements**")
            
            st.dataframe(filtered, use_container_width=True, height=400)
            
            csv = filtered.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Telecharger CSV", data=csv,
                file_name=f"airline_data_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv",
            )
        else:
            st.info("Aucune donnee disponible.")

# =============================================================================
# RUN
# =============================================================================
if __name__ == "__main__":
    main()
