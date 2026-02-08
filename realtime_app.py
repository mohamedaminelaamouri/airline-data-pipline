"""
Airline Data Pipeline - Real-time Dashboard
Professional Design with Plotly Charts
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, Any, Deque, List
from dataclasses import dataclass
from collections import deque
import threading
import json
import time

try:
    from confluent_kafka import Consumer, KafkaError
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False

try:
    import clickhouse_connect
    CLICKHOUSE_AVAILABLE = True
except ImportError:
    CLICKHOUSE_AVAILABLE = False

try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH_AVAILABLE = True
except ImportError:
    AUTOREFRESH_AVAILABLE = False

# =============================================================================
# CONFIG
# =============================================================================
KAFKA_HOST = "localhost"
KAFKA_PORT = 9092
KAFKA_TOPIC = "airline-delays"
CLICKHOUSE_HOST = "localhost"
CLICKHOUSE_PORT = 8123
CLICKHOUSE_DB = "airline_data"

st.set_page_config(
    page_title="Airline Real-time Monitor",
    page_icon="A",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =============================================================================
# DATA CLASSES
# =============================================================================
@dataclass(frozen=True)
class KafkaEvent:
    received_at: datetime
    carrier: str
    airport: str
    year: int
    month: int
    flights: int
    delayed: int
    delay_rate: float

# =============================================================================
# KAFKA BUFFER
# =============================================================================
@st.cache_resource
def get_kafka_buffer() -> Deque[KafkaEvent]:
    return deque(maxlen=1000)

@st.cache_resource
def get_kafka_state() -> Dict:
    return {"running": False, "count": 0, "start": None}

def kafka_consumer_loop(buffer: Deque[KafkaEvent], state: Dict):
    if not KAFKA_AVAILABLE:
        return
    
    try:
        consumer = Consumer({
            'bootstrap.servers': f"{KAFKA_HOST}:{KAFKA_PORT}",
            'group.id': 'streamlit-pro-monitor',
            'auto.offset.reset': 'latest',
        })
        consumer.subscribe([KAFKA_TOPIC])
        state["running"] = True
        state["start"] = datetime.now()
        
        while state["running"]:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                continue
            
            try:
                raw = msg.value().decode("utf-8")
                data = json.loads(raw)
                records = [data] if isinstance(data, dict) else data
                
                for rec in records:
                    if isinstance(rec, dict):
                        flights = int(rec.get("arr_flights", 0))
                        delayed = int(rec.get("arr_del15", 0))
                        rate = delayed / flights if flights > 0 else 0
                        
                        buffer.append(KafkaEvent(
                            received_at=datetime.now(),
                            carrier=rec.get("carrier", "N/A"),
                            airport=rec.get("airport", "N/A"),
                            year=int(rec.get("year", 0)),
                            month=int(rec.get("month", 0)),
                            flights=flights,
                            delayed=delayed,
                            delay_rate=rate
                        ))
                        state["count"] += 1
            except:
                pass
                
    except Exception:
        state["running"] = False
    finally:
        try:
            consumer.close()
        except:
            pass

def ensure_kafka_thread():
    state = get_kafka_state()
    buffer = get_kafka_buffer()
    
    if not state["running"]:
        thread = threading.Thread(target=kafka_consumer_loop, args=(buffer, state), daemon=True)
        thread.start()
        time.sleep(1)

# =============================================================================
# CLICKHOUSE
# =============================================================================
@st.cache_resource
def get_clickhouse_client():
    if not CLICKHOUSE_AVAILABLE:
        return None
    try:
        return clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            database=CLICKHOUSE_DB
        )
    except:
        return None

def get_clickhouse_stats():
    client = get_clickhouse_client()
    if not client:
        return {"records": 0, "flights": 0, "delayed": 0, "rate": 0, "carriers": 0, "airports": 0}
    
    try:
        result = client.query("""
            SELECT 
                count(), 
                sum(arr_flights), 
                sum(arr_del15),
                count(DISTINCT carrier),
                count(DISTINCT airport)
            FROM flights
        """)
        row = result.result_rows[0]
        records = int(row[0])
        flights = int(row[1] or 0)
        delayed = int(row[2] or 0)
        carriers = int(row[3] or 0)
        airports = int(row[4] or 0)
        rate = delayed / flights if flights > 0 else 0
        return {"records": records, "flights": flights, "delayed": delayed, "rate": rate, "carriers": carriers, "airports": airports}
    except:
        return {"records": 0, "flights": 0, "delayed": 0, "rate": 0, "carriers": 0, "airports": 0}

def get_monthly_stats():
    client = get_clickhouse_client()
    if not client:
        return pd.DataFrame()
    
    try:
        result = client.query("""
            SELECT 
                month,
                sum(arr_flights) as flights,
                sum(arr_del15) as delayed
            FROM flights
            GROUP BY month
            ORDER BY month
        """)
        if result.result_rows:
            df = pd.DataFrame(result.result_rows, columns=['month', 'flights', 'delayed'])
            df['delay_rate'] = df['delayed'] / df['flights'].replace(0, 1)
            return df
    except:
        pass
    return pd.DataFrame()

def get_carrier_stats():
    client = get_clickhouse_client()
    if not client:
        return pd.DataFrame()
    
    try:
        result = client.query("""
            SELECT 
                carrier,
                sum(arr_flights) as flights,
                sum(arr_del15) as delayed
            FROM flights
            GROUP BY carrier
            ORDER BY flights DESC
            LIMIT 10
        """)
        if result.result_rows:
            df = pd.DataFrame(result.result_rows, columns=['carrier', 'flights', 'delayed'])
            df['delay_rate'] = df['delayed'] / df['flights'].replace(0, 1)
            return df
    except:
        pass
    return pd.DataFrame()

# =============================================================================
# CSS PROFESSIONNEL
# =============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    * { font-family: 'Inter', sans-serif; }
    
    .stApp {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    }
    
    .main-header {
        background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
        padding: 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        box-shadow: 0 10px 40px rgba(59, 130, 246, 0.3);
    }
    
    .main-title {
        font-size: 2.5rem;
        font-weight: 700;
        color: white;
        margin: 0;
        letter-spacing: -0.02em;
    }
    
    .main-subtitle {
        font-size: 1rem;
        color: rgba(255,255,255,0.8);
        margin-top: 0.5rem;
    }
    
    .metric-card {
        background: rgba(30, 41, 59, 0.8);
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        backdrop-filter: blur(10px);
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    .metric-label {
        color: #94a3b8;
        font-size: 0.875rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 0.5rem;
    }
    
    .status-indicator {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        border-radius: 9999px;
        font-size: 0.875rem;
        font-weight: 500;
    }
    
    .status-online {
        background: rgba(16, 185, 129, 0.15);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    
    .status-offline {
        background: rgba(239, 68, 68, 0.15);
        color: #ef4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    
    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        animation: pulse-dot 2s infinite;
    }
    
    .status-online .status-dot { background: #10b981; }
    .status-offline .status-dot { background: #ef4444; }
    
    @keyframes pulse-dot {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.6; transform: scale(0.9); }
    }
    
    .section-title {
        font-size: 1.25rem;
        font-weight: 600;
        color: #f1f5f9;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid rgba(148, 163, 184, 0.2);
    }
    
    .data-table {
        background: rgba(30, 41, 59, 0.6);
        border-radius: 12px;
        overflow: hidden;
    }
    
    .data-table table {
        width: 100%;
        border-collapse: collapse;
    }
    
    .data-table th {
        background: rgba(51, 65, 85, 0.8);
        color: #94a3b8;
        font-weight: 600;
        text-transform: uppercase;
        font-size: 0.75rem;
        letter-spacing: 0.05em;
        padding: 1rem;
        text-align: left;
    }
    
    .data-table td {
        color: #e2e8f0;
        padding: 0.875rem 1rem;
        border-bottom: 1px solid rgba(148, 163, 184, 0.1);
    }
    
    .data-table tr:hover td {
        background: rgba(59, 130, 246, 0.1);
    }
    
    .chart-container {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-radius: 12px;
        padding: 1.5rem;
    }
    
    .live-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        background: rgba(239, 68, 68, 0.15);
        color: #ef4444;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .live-badge::before {
        content: '';
        width: 6px;
        height: 6px;
        background: #ef4444;
        border-radius: 50%;
        animation: pulse-dot 1s infinite;
    }
    
    /* Streamlit overrides */
    [data-testid="stMetric"] {
        background: rgba(30, 41, 59, 0.8);
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-radius: 12px;
        padding: 1rem;
    }
    
    [data-testid="stMetric"] label { color: #94a3b8 !important; }
    [data-testid="stMetric"] [data-testid="stMetricValue"] { color: #f1f5f9 !important; }
    
    h1, h2, h3, h4, h5, h6 { color: #f1f5f9 !important; }
    p, span, label { color: #cbd5e1 !important; }
    
    .stDataFrame { 
        background: rgba(30, 41, 59, 0.6) !important;
        border-radius: 12px !important;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# CHART HELPERS
# =============================================================================
def create_gauge_chart(value: float, title: str, max_val: float = 100):
    """Create a professional gauge chart."""
    color = "#10b981" if value < 15 else "#f59e0b" if value < 25 else "#ef4444"
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={'text': title, 'font': {'color': '#94a3b8', 'size': 14}},
        number={'suffix': '%', 'font': {'color': '#f1f5f9', 'size': 32}},
        gauge={
            'axis': {'range': [0, max_val], 'tickcolor': '#475569', 'tickfont': {'color': '#64748b'}},
            'bar': {'color': color},
            'bgcolor': '#1e293b',
            'bordercolor': '#334155',
            'steps': [
                {'range': [0, 15], 'color': 'rgba(16, 185, 129, 0.2)'},
                {'range': [15, 25], 'color': 'rgba(245, 158, 11, 0.2)'},
                {'range': [25, max_val], 'color': 'rgba(239, 68, 68, 0.2)'}
            ],
            'threshold': {
                'line': {'color': '#f1f5f9', 'width': 2},
                'thickness': 0.8,
                'value': value
            }
        }
    ))
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        font={'color': '#f1f5f9'},
        height=250,
        margin=dict(l=20, r=20, t=50, b=20)
    )
    return fig

def create_monthly_bar_chart(df: pd.DataFrame):
    """Create monthly flights bar chart."""
    if df.empty:
        return go.Figure()
    
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    df['month_name'] = df['month'].apply(lambda x: months[int(x)-1] if 1 <= int(x) <= 12 else str(x))
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df['month_name'],
        y=df['flights'] - df['delayed'],
        name='On Time',
        marker_color='#10b981'
    ))
    
    fig.add_trace(go.Bar(
        x=df['month_name'],
        y=df['delayed'],
        name='Delayed',
        marker_color='#ef4444'
    ))
    
    fig.update_layout(
        barmode='stack',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': '#94a3b8'},
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
        height=300,
        margin=dict(l=20, r=20, t=40, b=40),
        xaxis=dict(gridcolor='rgba(148,163,184,0.1)', showgrid=False),
        yaxis=dict(gridcolor='rgba(148,163,184,0.1)', title='Flights')
    )
    return fig

def create_carrier_chart(df: pd.DataFrame):
    """Create carrier delay rate horizontal bar chart."""
    if df.empty:
        return go.Figure()
    
    df_sorted = df.sort_values('delay_rate', ascending=True)
    
    colors = ['#ef4444' if r > 0.2 else '#f59e0b' if r > 0.15 else '#10b981' for r in df_sorted['delay_rate']]
    
    fig = go.Figure(go.Bar(
        x=df_sorted['delay_rate'] * 100,
        y=df_sorted['carrier'],
        orientation='h',
        marker_color=colors,
        text=[f"{r*100:.1f}%" for r in df_sorted['delay_rate']],
        textposition='outside',
        textfont={'color': '#94a3b8'}
    ))
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': '#94a3b8'},
        height=350,
        margin=dict(l=20, r=60, t=20, b=40),
        xaxis=dict(gridcolor='rgba(148,163,184,0.1)', title='Delay Rate (%)', range=[0, max(df_sorted['delay_rate']*100)*1.2]),
        yaxis=dict(gridcolor='rgba(148,163,184,0.1)')
    )
    return fig

def create_realtime_line_chart(messages: List[KafkaEvent]):
    """Create real-time message rate line chart."""
    if not messages:
        return go.Figure()
    
    # Group by minute
    df_data = []
    for msg in messages:
        minute = msg.received_at.replace(second=0, microsecond=0)
        df_data.append({'minute': minute, 'count': 1, 'delay_rate': msg.delay_rate})
    
    df = pd.DataFrame(df_data)
    if df.empty:
        return go.Figure()
    
    grouped = df.groupby('minute').agg({'count': 'sum', 'delay_rate': 'mean'}).reset_index()
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=grouped['minute'],
        y=grouped['count'],
        mode='lines+markers',
        name='Messages',
        line=dict(color='#3b82f6', width=2),
        marker=dict(size=6),
        fill='tozeroy',
        fillcolor='rgba(59, 130, 246, 0.1)'
    ))
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': '#94a3b8'},
        height=250,
        margin=dict(l=20, r=20, t=20, b=40),
        xaxis=dict(gridcolor='rgba(148,163,184,0.1)', title='Time'),
        yaxis=dict(gridcolor='rgba(148,163,184,0.1)', title='Messages/min'),
        showlegend=False
    )
    return fig

# =============================================================================
# MAIN
# =============================================================================
def main():
    # Auto-refresh
    if AUTOREFRESH_AVAILABLE:
        st_autorefresh(interval=3000, key="refresh")
    
    # Kafka
    ensure_kafka_thread()
    buffer = get_kafka_buffer()
    state = get_kafka_state()
    messages = list(buffer)
    
    # Data
    ch_stats = get_clickhouse_stats()
    monthly_stats = get_monthly_stats()
    carrier_stats = get_carrier_stats()
    
    # Header
    col_header, col_status = st.columns([3, 1])
    
    with col_header:
        st.markdown("""
        <div class="main-header">
            <h1 class="main-title">Airline Real-time Monitor</h1>
            <p class="main-subtitle">Pipeline Analytics Dashboard - Kafka | ClickHouse | NiFi</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col_status:
        kafka_class = "status-online" if state["running"] else "status-offline"
        kafka_text = "Kafka Online" if state["running"] else "Kafka Offline"
        ch_class = "status-online" if ch_stats["records"] > 0 else "status-offline"
        ch_text = "ClickHouse Online" if ch_stats["records"] > 0 else "ClickHouse Offline"
        
        st.markdown(f"""
        <div style="display: flex; flex-direction: column; gap: 0.5rem; padding-top: 1rem;">
            <span class="status-indicator {kafka_class}">
                <span class="status-dot"></span>
                {kafka_text}
            </span>
            <span class="status-indicator {ch_class}">
                <span class="status-dot"></span>
                {ch_text}
            </span>
        </div>
        """, unsafe_allow_html=True)
    
    # Metrics Row
    st.markdown("---")
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{state["count"]:,}</div>
            <div class="metric-label">Kafka Messages</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{ch_stats['records']:,}</div>
            <div class="metric-label">Total Records</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{ch_stats['flights']:,}</div>
            <div class="metric-label">Total Flights</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{ch_stats['delayed']:,}</div>
            <div class="metric-label">Delayed Flights</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{ch_stats['carriers']}</div>
            <div class="metric-label">Carriers</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col6:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{ch_stats['airports']}</div>
            <div class="metric-label">Airports</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Charts Row 1
    col_gauge, col_monthly = st.columns([1, 2])
    
    with col_gauge:
        st.markdown('<div class="section-title">Delay Rate</div>', unsafe_allow_html=True)
        st.plotly_chart(
            create_gauge_chart(ch_stats['rate'] * 100, "Global Delay Rate"),
            use_container_width=True,
            key="gauge"
        )
    
    with col_monthly:
        st.markdown('<div class="section-title">Monthly Flight Volume</div>', unsafe_allow_html=True)
        st.plotly_chart(
            create_monthly_bar_chart(monthly_stats),
            use_container_width=True,
            key="monthly"
        )
    
    # Charts Row 2
    col_carrier, col_realtime = st.columns(2)
    
    with col_carrier:
        st.markdown('<div class="section-title">Top 10 Carriers by Delay Rate</div>', unsafe_allow_html=True)
        st.plotly_chart(
            create_carrier_chart(carrier_stats),
            use_container_width=True,
            key="carrier"
        )
    
    with col_realtime:
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
            <span class="section-title" style="margin: 0; border: none; padding: 0;">Real-time Message Flow</span>
            <span class="live-badge">Live</span>
        </div>
        """, unsafe_allow_html=True)
        st.plotly_chart(
            create_realtime_line_chart(messages),
            use_container_width=True,
            key="realtime"
        )
    
    st.markdown("---")
    
    # Recent Messages Table
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
        <span class="section-title" style="margin: 0; border: none; padding: 0;">Recent Kafka Messages</span>
        <span class="live-badge">Live</span>
        <span style="color: #64748b; font-size: 0.875rem;">{len(messages)} in buffer</span>
    </div>
    """, unsafe_allow_html=True)
    
    if messages:
        recent = messages[-15:][::-1]
        
        table_html = """
        <div class="data-table">
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Carrier</th>
                        <th>Airport</th>
                        <th>Period</th>
                        <th>Flights</th>
                        <th>Delayed</th>
                        <th>Delay Rate</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for msg in recent:
            rate_color = "#ef4444" if msg.delay_rate > 0.2 else "#f59e0b" if msg.delay_rate > 0.15 else "#10b981"
            table_html += f"""
            <tr>
                <td>{msg.received_at.strftime('%H:%M:%S')}</td>
                <td><strong>{msg.carrier}</strong></td>
                <td>{msg.airport}</td>
                <td>{msg.year}/{msg.month:02d}</td>
                <td>{msg.flights:,}</td>
                <td>{msg.delayed:,}</td>
                <td style="color: {rate_color}; font-weight: 600;">{msg.delay_rate*100:.1f}%</td>
            </tr>
            """
        
        table_html += "</tbody></table></div>"
        st.markdown(table_html, unsafe_allow_html=True)
    else:
        st.info("Waiting for Kafka messages... Ensure NiFi flow is running.")
    
    # Footer
    uptime = ""
    if state["start"]:
        elapsed = int((datetime.now() - state["start"]).total_seconds())
        uptime = f"Uptime: {elapsed}s"
    
    st.markdown(f"""
    <div style="text-align: center; color: #475569; font-size: 0.8rem; margin-top: 2rem; padding: 1rem;">
        Airline Real-time Monitor | Auto-refresh: 3s | {uptime}
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()