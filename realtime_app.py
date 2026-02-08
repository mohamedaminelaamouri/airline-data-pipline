"""
Airline Data Pipeline - Real-time Dashboard
Professional Kafka + ClickHouse Monitoring
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from typing import Dict

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
CLICKHOUSE_HOST = "localhost"
CLICKHOUSE_PORT = 8123
CLICKHOUSE_DB = "airline_data"

st.set_page_config(page_title="Airline Monitor", page_icon="A", layout="wide", initial_sidebar_state="collapsed")

# =============================================================================
# HELPERS
# =============================================================================
def format_number(n) -> str:
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)

# =============================================================================
# CLICKHOUSE
# =============================================================================
@st.cache_resource
def get_clickhouse_client():
    if not CLICKHOUSE_AVAILABLE:
        return None
    try:
        return clickhouse_connect.get_client(host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT, database=CLICKHOUSE_DB)
    except:
        return None

def get_stats():
    client = get_clickhouse_client()
    if not client:
        return {"records": 0, "flights": 0, "delayed": 0, "rate": 0, "carriers": 0, "airports": 0}
    try:
        r = client.query("SELECT count(), sum(arr_flights), sum(arr_del15), count(DISTINCT carrier), count(DISTINCT airport) FROM flights")
        row = r.result_rows[0]
        records, flights, delayed = int(row[0]), int(row[1] or 0), int(row[2] or 0)
        return {"records": records, "flights": flights, "delayed": delayed, "rate": delayed/flights if flights else 0, "carriers": int(row[3] or 0), "airports": int(row[4] or 0)}
    except:
        return {"records": 0, "flights": 0, "delayed": 0, "rate": 0, "carriers": 0, "airports": 0}

def get_monthly():
    client = get_clickhouse_client()
    if not client:
        return pd.DataFrame()
    try:
        r = client.query("SELECT month, sum(arr_flights), sum(arr_del15) FROM flights GROUP BY month ORDER BY month")
        if r.result_rows:
            df = pd.DataFrame(r.result_rows, columns=['month', 'flights', 'delayed'])
            return df
    except:
        pass
    return pd.DataFrame()

def get_carriers():
    client = get_clickhouse_client()
    if not client:
        return pd.DataFrame()
    try:
        r = client.query("SELECT carrier, sum(arr_flights), sum(arr_del15) FROM flights GROUP BY carrier ORDER BY sum(arr_flights) DESC LIMIT 10")
        if r.result_rows:
            df = pd.DataFrame(r.result_rows, columns=['carrier', 'flights', 'delayed'])
            df['delay_rate'] = df['delayed'] / df['flights'].replace(0, 1)
            return df
    except:
        pass
    return pd.DataFrame()

# =============================================================================
# CSS
# =============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }
    .stApp { background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%); }
    
    .header { background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); padding: 1.5rem; border-radius: 12px; margin-bottom: 1.5rem; }
    .header h1 { font-size: 1.75rem; font-weight: 700; color: white; margin: 0; }
    .header p { color: rgba(255,255,255,0.8); margin: 0.25rem 0 0; font-size: 0.9rem; }
    
    .metric { background: rgba(30, 41, 59, 0.8); border: 1px solid rgba(148, 163, 184, 0.1); border-radius: 10px; padding: 1rem; text-align: center; }
    .metric-val { font-size: 2rem; font-weight: 700; background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .metric-lbl { color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; margin-top: 0.25rem; }
    
    .section { font-size: 1rem; font-weight: 600; color: #f1f5f9; margin: 1rem 0 0.5rem; }
    h1, h2, h3 { color: #f1f5f9 !important; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# CHARTS
# =============================================================================
def gauge(val):
    color = "#10b981" if val < 15 else "#f59e0b" if val < 25 else "#ef4444"
    fig = go.Figure(go.Indicator(mode="gauge+number", value=val, number={'suffix': '%', 'font': {'color': '#f1f5f9', 'size': 28}},
        gauge={'axis': {'range': [0, 50]}, 'bar': {'color': color}, 'bgcolor': '#1e293b',
               'steps': [{'range': [0, 15], 'color': 'rgba(16,185,129,0.1)'}, {'range': [15, 25], 'color': 'rgba(245,158,11,0.1)'}, {'range': [25, 50], 'color': 'rgba(239,68,68,0.1)'}]}))
    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', height=200, margin=dict(l=20, r=20, t=30, b=10))
    return fig

def monthly_chart(df):
    if df.empty:
        return go.Figure()
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    df['m'] = df['month'].apply(lambda x: months[int(x)-1] if 1 <= int(x) <= 12 else str(x))
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df['m'], y=df['flights'] - df['delayed'], name='On Time', marker_color='#10b981'))
    fig.add_trace(go.Bar(x=df['m'], y=df['delayed'], name='Delayed', marker_color='#ef4444'))
    fig.update_layout(barmode='stack', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font={'color': '#94a3b8'},
                      legend=dict(orientation='h', y=1.1, x=0.5, xanchor='center'), height=250, margin=dict(l=20, r=20, t=20, b=30),
                      xaxis=dict(showgrid=False), yaxis=dict(gridcolor='rgba(148,163,184,0.1)'))
    return fig

def carrier_chart(df):
    if df.empty:
        return go.Figure()
    df = df.sort_values('delay_rate', ascending=True)
    colors = ['#ef4444' if r > 0.2 else '#f59e0b' if r > 0.15 else '#10b981' for r in df['delay_rate']]
    fig = go.Figure(go.Bar(x=df['delay_rate'] * 100, y=df['carrier'], orientation='h', marker_color=colors,
                           text=[f"{r*100:.1f}%" for r in df['delay_rate']], textposition='outside', textfont={'color': '#94a3b8'}))
    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font={'color': '#94a3b8'},
                      height=300, margin=dict(l=20, r=50, t=10, b=20), xaxis=dict(gridcolor='rgba(148,163,184,0.1)'), yaxis=dict(showgrid=False))
    return fig

# =============================================================================
# MAIN
# =============================================================================
def main():
    if AUTOREFRESH_AVAILABLE:
        st_autorefresh(interval=5000, key="r")
    
    s = get_stats()
    m = get_monthly()
    c = get_carriers()
    
    st.markdown('<div class="header"><h1>Airline Monitor</h1><p>ClickHouse Analytics Dashboard</p></div>', unsafe_allow_html=True)
    
    # Metrics
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.markdown(f'<div class="metric"><div class="metric-val">{format_number(s["records"])}</div><div class="metric-lbl">Records</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric"><div class="metric-val">{format_number(s["flights"])}</div><div class="metric-lbl">Flights</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric"><div class="metric-val">{format_number(s["delayed"])}</div><div class="metric-lbl">Delayed</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="metric"><div class="metric-val">{s["rate"]*100:.1f}%</div><div class="metric-lbl">Delay Rate</div></div>', unsafe_allow_html=True)
    with c5:
        st.markdown(f'<div class="metric"><div class="metric-val">{s["carriers"]}</div><div class="metric-lbl">Carriers</div></div>', unsafe_allow_html=True)
    with c6:
        st.markdown(f'<div class="metric"><div class="metric-val">{s["airports"]}</div><div class="metric-lbl">Airports</div></div>', unsafe_allow_html=True)
    
    # Charts
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown('<div class="section">Delay Rate</div>', unsafe_allow_html=True)
        st.plotly_chart(gauge(s['rate'] * 100), use_container_width=True, key="g")
    with col2:
        st.markdown('<div class="section">Monthly Volume</div>', unsafe_allow_html=True)
        st.plotly_chart(monthly_chart(m), use_container_width=True, key="m")
    
    st.markdown('<div class="section">Top Carriers by Delay Rate</div>', unsafe_allow_html=True)
    st.plotly_chart(carrier_chart(c), use_container_width=True, key="c")

if __name__ == "__main__":
    import sys
    import subprocess
    if 'streamlit' not in sys.modules:
        subprocess.run([sys.executable, "-m", "streamlit", "run", __file__, "--server.port", "8501"])
    else:
        main()