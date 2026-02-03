"""Test minimal Streamlit"""
import streamlit as st
import clickhouse_connect

st.set_page_config(page_title="Test", layout="wide")

st.title("Airline Data Pipeline - Test")

# ClickHouse
try:
    client = clickhouse_connect.get_client(
        host='localhost',
        port=8123,
        database='airline_data'
    )
    total = client.query("SELECT count() FROM flights").result_rows[0][0]
    st.success(f"ClickHouse OK: {total:,} records")
    
    # Stats
    stats = client.query("""
        SELECT 
            count() as total,
            count(DISTINCT carrier) as carriers,
            count(DISTINCT airport) as airports,
            sum(arr_del15) as delayed,
            sum(arr_flights) as flights
        FROM flights
    """).result_rows[0]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Records", f"{stats[0]:,}")
    col2.metric("Compagnies", f"{stats[1]}")
    col3.metric("Aeroports", f"{stats[2]}")
    
    col4, col5, col6 = st.columns(3)
    col4.metric("Vols", f"{stats[4]:,}")
    delayed_pct = (stats[3] / stats[4] * 100) if stats[4] > 0 else 0
    col5.metric("Retardes", f"{stats[3]:,}", delta=f"{delayed_pct:.1f}%", delta_color="inverse")
    col6.metric("Taux Retard", f"{delayed_pct:.1f}%")
    
except Exception as e:
    st.error(f"Erreur ClickHouse: {e}")

st.info("Dashboard minimal - test de stabilite")
