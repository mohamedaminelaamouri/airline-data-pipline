"""
Airline Data Pipeline - Real-time Web Monitor
Version web avec Flask pour affichage dans le navigateur
"""

import json
import threading
import time
from datetime import datetime
from collections import deque
from flask import Flask, render_template_string, jsonify

try:
    from confluent_kafka import Consumer, KafkaError
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False

# Configuration
KAFKA_HOST = "localhost"
KAFKA_PORT = 9092
KAFKA_TOPIC = "airline-delays"

app = Flask(__name__)

# Buffer de messages (thread-safe)
message_buffer = deque(maxlen=100)
stats = {
    "message_count": 0,
    "start_time": None,
    "kafka_connected": False,
    "last_update": None
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Airline Data Pipeline - Monitor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        header {
            text-align: center;
            padding: 30px 0;
            border-bottom: 2px solid rgba(255,255,255,0.1);
            margin-bottom: 30px;
        }
        h1 {
            font-size: 2.5rem;
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            backdrop-filter: blur(10px);
        }
        .stat-value {
            font-size: 2rem;
            font-weight: bold;
            color: #00d9ff;
        }
        .stat-label { color: rgba(255,255,255,0.7); margin-top: 5px; }
        .status {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.9rem;
            margin-top: 15px;
        }
        .status.online { background: rgba(0,255,136,0.2); color: #00ff88; }
        .status.offline { background: rgba(255,82,82,0.2); color: #ff5252; }
        .dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        .online .dot { background: #00ff88; }
        .offline .dot { background: #ff5252; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .messages-container {
            background: rgba(0,0,0,0.3);
            border-radius: 12px;
            overflow: hidden;
        }
        .messages-header {
            background: rgba(0,217,255,0.1);
            padding: 15px 20px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            font-weight: 600;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px 15px;
            text-align: left;
        }
        th {
            background: rgba(255,255,255,0.05);
            color: rgba(255,255,255,0.8);
            font-weight: 500;
            font-size: 0.85rem;
            text-transform: uppercase;
        }
        tr:nth-child(even) { background: rgba(255,255,255,0.02); }
        tr:hover { background: rgba(0,217,255,0.1); }
        .delay-low { color: #00ff88; }
        .delay-medium { color: #ffb347; }
        .delay-high { color: #ff5252; }
        .no-data {
            text-align: center;
            padding: 50px;
            color: rgba(255,255,255,0.5);
        }
        footer {
            text-align: center;
            padding: 20px;
            color: rgba(255,255,255,0.3);
            font-size: 0.8rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Airline Data Pipeline</h1>
            <p style="color: rgba(255,255,255,0.6); margin-top: 10px;">Real-time Kafka Monitor</p>
            <div id="status" class="status offline">
                <span class="dot"></span>
                <span id="status-text">Connecting...</span>
            </div>
        </header>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value" id="msg-count">0</div>
                <div class="stat-label">Messages</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="uptime">0s</div>
                <div class="stat-label">Uptime</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="avg-delay">0%</div>
                <div class="stat-label">Avg Delay Rate</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="last-update">-</div>
                <div class="stat-label">Last Update</div>
            </div>
        </div>
        
        <div class="messages-container">
            <div class="messages-header">Recent Messages</div>
            <table>
                <thead>
                    <tr>
                        <th>Carrier</th>
                        <th>Airport</th>
                        <th>Date</th>
                        <th>Flights</th>
                        <th>Delays</th>
                        <th>Rate</th>
                    </tr>
                </thead>
                <tbody id="messages-body">
                    <tr class="no-data"><td colspan="6">Waiting for messages...</td></tr>
                </tbody>
            </table>
        </div>
        
        <footer>
            Airline Data Pipeline - Real-time Monitor | Auto-refresh: 2s
        </footer>
    </div>
    
    <script>
        function updateData() {
            fetch('/api/data')
                .then(r => r.json())
                .then(data => {
                    // Update status
                    const status = document.getElementById('status');
                    const statusText = document.getElementById('status-text');
                    if (data.kafka_connected) {
                        status.className = 'status online';
                        statusText.textContent = 'Kafka Online';
                    } else {
                        status.className = 'status offline';
                        statusText.textContent = 'Kafka Offline';
                    }
                    
                    // Update stats
                    document.getElementById('msg-count').textContent = data.message_count.toLocaleString();
                    document.getElementById('uptime').textContent = data.uptime;
                    document.getElementById('avg-delay').textContent = data.avg_delay.toFixed(1) + '%';
                    document.getElementById('last-update').textContent = data.last_update || '-';
                    
                    // Update messages
                    const tbody = document.getElementById('messages-body');
                    if (data.messages.length === 0) {
                        tbody.innerHTML = '<tr class="no-data"><td colspan="6">Waiting for messages...</td></tr>';
                    } else {
                        tbody.innerHTML = data.messages.map(m => {
                            const rateClass = m.rate < 15 ? 'delay-low' : m.rate < 25 ? 'delay-medium' : 'delay-high';
                            return `<tr>
                                <td><strong>${m.carrier}</strong></td>
                                <td>${m.airport}</td>
                                <td>${m.year}/${String(m.month).padStart(2,'0')}</td>
                                <td>${m.flights.toLocaleString()}</td>
                                <td>${m.delayed.toLocaleString()}</td>
                                <td class="${rateClass}">${m.rate.toFixed(1)}%</td>
                            </tr>`;
                        }).join('');
                    }
                })
                .catch(console.error);
        }
        
        updateData();
        setInterval(updateData, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/data')
def get_data():
    messages = []
    total_rate = 0
    
    for msg in list(message_buffer)[-20:]:
        messages.append(msg)
        total_rate += msg.get('rate', 0)
    
    avg_delay = total_rate / len(messages) if messages else 0
    
    uptime = "0s"
    if stats["start_time"]:
        elapsed = int((datetime.now() - stats["start_time"]).total_seconds())
        if elapsed < 60:
            uptime = f"{elapsed}s"
        elif elapsed < 3600:
            uptime = f"{elapsed // 60}m {elapsed % 60}s"
        else:
            uptime = f"{elapsed // 3600}h {(elapsed % 3600) // 60}m"
    
    return jsonify({
        "messages": messages[::-1],  # Most recent first
        "message_count": stats["message_count"],
        "kafka_connected": stats["kafka_connected"],
        "uptime": uptime,
        "avg_delay": avg_delay,
        "last_update": stats["last_update"]
    })

def kafka_consumer_thread():
    """Thread de consommation Kafka en arriere-plan."""
    if not KAFKA_AVAILABLE:
        print("Kafka non disponible - mode demo")
        return
    
    conf = {
        'bootstrap.servers': f"{KAFKA_HOST}:{KAFKA_PORT}",
        'group.id': 'web-monitor',
        'auto.offset.reset': 'latest',
        'enable.auto.commit': True,
    }
    
    try:
        consumer = Consumer(conf)
        consumer.subscribe([KAFKA_TOPIC])
        stats["kafka_connected"] = True
        stats["start_time"] = datetime.now()
        print(f"Connecte a Kafka: {KAFKA_TOPIC}")
        
        while True:
            msg = consumer.poll(timeout=1.0)
            
            if msg is None:
                continue
            
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                print(f"Erreur: {msg.error()}")
                continue
            
            try:
                raw = msg.value().decode("utf-8")
                data = json.loads(raw)
                records = [data] if isinstance(data, dict) else data
                
                for record in records:
                    if isinstance(record, dict):
                        flights = record.get("arr_flights", 0)
                        delayed = record.get("arr_del15", 0)
                        rate = (delayed / flights * 100) if flights > 0 else 0
                        
                        message_buffer.append({
                            "carrier": record.get("carrier", "N/A"),
                            "airport": record.get("airport", "N/A"),
                            "year": record.get("year", 0),
                            "month": record.get("month", 0),
                            "flights": flights,
                            "delayed": delayed,
                            "rate": rate
                        })
                        stats["message_count"] += 1
                        stats["last_update"] = datetime.now().strftime("%H:%M:%S")
                        
            except Exception as e:
                print(f"Erreur parsing: {e}")
                
    except Exception as e:
        print(f"Erreur Kafka: {e}")
        stats["kafka_connected"] = False

if __name__ == "__main__":
    print("=" * 60)
    print("  AIRLINE DATA PIPELINE - Web Monitor")
    print("=" * 60)
    print(f"  Server: http://localhost:5000")
    print("=" * 60)
    
    # Demarrer le thread Kafka
    kafka_thread = threading.Thread(target=kafka_consumer_thread, daemon=True)
    kafka_thread.start()
    
    # Demarrer Flask
    app.run(host='0.0.0.0', port=5000, debug=False)
