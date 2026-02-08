"""
Airline Data Pipeline - Real-time Web Monitor
Version amelioree avec graphiques et configuration Kafka
"""

import json
import threading
import time
from datetime import datetime
from collections import deque, defaultdict
from flask import Flask, render_template_string, jsonify

try:
    from confluent_kafka import Consumer, KafkaError
    from confluent_kafka.admin import AdminClient
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False

# Configuration
KAFKA_HOST = "localhost"
KAFKA_PORT = 9092
KAFKA_TOPIC = "airline-delays"

app = Flask(__name__)

# Buffer de messages (thread-safe)
message_buffer = deque(maxlen=200)
carrier_stats = defaultdict(lambda: {"count": 0, "total_rate": 0})
monthly_stats = defaultdict(lambda: {"count": 0, "total_rate": 0})
stats = {
    "message_count": 0,
    "start_time": None,
    "kafka_connected": False,
    "last_update": None,
    "broker_info": None,
    "topic_info": None
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Airline Data Pipeline - Monitor</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        header {
            text-align: center;
            padding: 25px 0;
            border-bottom: 2px solid rgba(255,255,255,0.1);
            margin-bottom: 25px;
        }
        h1 {
            font-size: 2.2rem;
            background: linear-gradient(90deg, #667eea, #764ba2, #f093fb);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .grid { display: grid; gap: 20px; }
        .grid-2 { grid-template-columns: repeat(2, 1fr); }
        .grid-4 { grid-template-columns: repeat(4, 1fr); }
        @media (max-width: 900px) { .grid-2, .grid-4 { grid-template-columns: 1fr; } }
        
        .card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 20px;
            backdrop-filter: blur(10px);
        }
        .card-title {
            font-size: 0.85rem;
            color: rgba(255,255,255,0.6);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .card-title::before {
            content: '';
            width: 4px;
            height: 16px;
            background: linear-gradient(180deg, #667eea, #764ba2);
            border-radius: 2px;
        }
        
        /* Stats */
        .stats { margin-bottom: 25px; }
        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .stat-label { color: rgba(255,255,255,0.5); font-size: 0.85rem; margin-top: 5px; }
        
        /* Status */
        .status {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.85rem;
            margin-top: 10px;
        }
        .status.online { background: rgba(0,255,136,0.15); color: #00ff88; border: 1px solid rgba(0,255,136,0.3); }
        .status.offline { background: rgba(255,82,82,0.15); color: #ff5252; border: 1px solid rgba(255,82,82,0.3); }
        .dot {
            width: 8px; height: 8px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        .online .dot { background: #00ff88; box-shadow: 0 0 10px #00ff88; }
        .offline .dot { background: #ff5252; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        
        /* Config Panel */
        .config-item {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .config-item:last-child { border: none; }
        .config-key { color: rgba(255,255,255,0.6); }
        .config-value { color: #00d9ff; font-family: monospace; }
        
        /* Charts */
        .chart-container { position: relative; height: 250px; }
        
        /* Table */
        .table-container { max-height: 350px; overflow-y: auto; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px 12px; text-align: left; }
        th {
            background: rgba(102,126,234,0.2);
            color: rgba(255,255,255,0.8);
            font-weight: 500;
            font-size: 0.75rem;
            text-transform: uppercase;
            position: sticky;
            top: 0;
        }
        tr:nth-child(even) { background: rgba(255,255,255,0.02); }
        tr:hover { background: rgba(102,126,234,0.1); }
        .delay-low { color: #00ff88; }
        .delay-medium { color: #ffb347; }
        .delay-high { color: #ff5252; }
        
        .no-data {
            text-align: center;
            padding: 40px;
            color: rgba(255,255,255,0.4);
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: rgba(255,255,255,0.05); }
        ::-webkit-scrollbar-thumb { background: rgba(102,126,234,0.5); border-radius: 3px; }
        
        footer {
            text-align: center;
            padding: 20px;
            color: rgba(255,255,255,0.3);
            font-size: 0.75rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Airline Data Pipeline</h1>
            <p style="color: rgba(255,255,255,0.5); margin-top: 8px;">Real-time Kafka Streaming Monitor</p>
            <div id="status" class="status offline">
                <span class="dot"></span>
                <span id="status-text">Connecting...</span>
            </div>
        </header>
        
        <!-- Stats Row -->
        <div class="grid grid-4 stats">
            <div class="card" style="text-align: center;">
                <div class="stat-value" id="msg-count">0</div>
                <div class="stat-label">Total Messages</div>
            </div>
            <div class="card" style="text-align: center;">
                <div class="stat-value" id="uptime">0s</div>
                <div class="stat-label">Uptime</div>
            </div>
            <div class="card" style="text-align: center;">
                <div class="stat-value" id="avg-delay">0%</div>
                <div class="stat-label">Avg Delay Rate</div>
            </div>
            <div class="card" style="text-align: center;">
                <div class="stat-value" id="msg-rate">0/s</div>
                <div class="stat-label">Message Rate</div>
            </div>
        </div>
        
        <!-- Kafka Config + Charts -->
        <div class="grid grid-2" style="margin-bottom: 25px;">
            <!-- Kafka Configuration -->
            <div class="card">
                <div class="card-title">Kafka Configuration</div>
                <div class="config-item">
                    <span class="config-key">Bootstrap Server</span>
                    <span class="config-value" id="kafka-host">localhost:9092</span>
                </div>
                <div class="config-item">
                    <span class="config-key">Topic</span>
                    <span class="config-value" id="kafka-topic">airline-delays</span>
                </div>
                <div class="config-item">
                    <span class="config-key">Consumer Group</span>
                    <span class="config-value">web-monitor</span>
                </div>
                <div class="config-item">
                    <span class="config-key">Auto Offset Reset</span>
                    <span class="config-value">latest</span>
                </div>
                <div class="config-item">
                    <span class="config-key">Partitions</span>
                    <span class="config-value" id="partitions">-</span>
                </div>
                <div class="config-item">
                    <span class="config-key">Last Update</span>
                    <span class="config-value" id="last-update">-</span>
                </div>
            </div>
            
            <!-- Delay Rate by Carrier Chart -->
            <div class="card">
                <div class="card-title">Delay Rate by Carrier (Top 10)</div>
                <div class="chart-container">
                    <canvas id="carrierChart"></canvas>
                </div>
            </div>
        </div>
        
        <!-- Monthly Chart + Messages Table -->
        <div class="grid grid-2">
            <!-- Monthly Trend Chart -->
            <div class="card">
                <div class="card-title">Monthly Delay Trend</div>
                <div class="chart-container">
                    <canvas id="monthlyChart"></canvas>
                </div>
            </div>
            
            <!-- Recent Messages -->
            <div class="card">
                <div class="card-title">Recent Messages</div>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Carrier</th>
                                <th>Airport</th>
                                <th>Date</th>
                                <th>Flights</th>
                                <th>Rate</th>
                            </tr>
                        </thead>
                        <tbody id="messages-body">
                            <tr class="no-data"><td colspan="5">Waiting for messages...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <footer>
            Airline Data Pipeline - Real-time Kafka Monitor | Auto-refresh: 2s | Chart.js Visualization
        </footer>
    </div>
    
    <script>
        // Initialize Charts
        const carrierCtx = document.getElementById('carrierChart').getContext('2d');
        const carrierChart = new Chart(carrierCtx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Delay Rate %',
                    data: [],
                    backgroundColor: 'rgba(102, 126, 234, 0.7)',
                    borderColor: 'rgba(102, 126, 234, 1)',
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                plugins: { legend: { display: false } },
                scales: {
                    x: { 
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: 'rgba(255,255,255,0.6)' }
                    },
                    y: { 
                        grid: { display: false },
                        ticks: { color: 'rgba(255,255,255,0.8)' }
                    }
                }
            }
        });
        
        const monthlyCtx = document.getElementById('monthlyChart').getContext('2d');
        const monthlyChart = new Chart(monthlyCtx, {
            type: 'line',
            data: {
                labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
                datasets: [{
                    label: 'Avg Delay Rate %',
                    data: [0,0,0,0,0,0,0,0,0,0,0,0],
                    borderColor: '#f093fb',
                    backgroundColor: 'rgba(240, 147, 251, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#f093fb',
                    pointRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { 
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: 'rgba(255,255,255,0.6)' }
                    },
                    y: { 
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: 'rgba(255,255,255,0.6)' },
                        beginAtZero: true
                    }
                }
            }
        });
        
        let lastMsgCount = 0;
        let lastTime = Date.now();
        
        function updateData() {
            fetch('/api/data')
                .then(r => r.json())
                .then(data => {
                    // Status
                    const status = document.getElementById('status');
                    const statusText = document.getElementById('status-text');
                    status.className = data.kafka_connected ? 'status online' : 'status offline';
                    statusText.textContent = data.kafka_connected ? 'Kafka Connected' : 'Kafka Offline';
                    
                    // Stats
                    document.getElementById('msg-count').textContent = data.message_count.toLocaleString();
                    document.getElementById('uptime').textContent = data.uptime;
                    document.getElementById('avg-delay').textContent = data.avg_delay.toFixed(1) + '%';
                    document.getElementById('last-update').textContent = data.last_update || '-';
                    document.getElementById('partitions').textContent = data.partitions || '-';
                    
                    // Message rate
                    const now = Date.now();
                    const elapsed = (now - lastTime) / 1000;
                    const rate = elapsed > 0 ? ((data.message_count - lastMsgCount) / elapsed).toFixed(1) : 0;
                    document.getElementById('msg-rate').textContent = rate + '/s';
                    lastMsgCount = data.message_count;
                    lastTime = now;
                    
                    // Carrier Chart
                    if (data.carrier_stats && data.carrier_stats.length > 0) {
                        carrierChart.data.labels = data.carrier_stats.map(c => c.carrier);
                        carrierChart.data.datasets[0].data = data.carrier_stats.map(c => c.rate);
                        carrierChart.update('none');
                    }
                    
                    // Monthly Chart
                    if (data.monthly_stats) {
                        monthlyChart.data.datasets[0].data = data.monthly_stats;
                        monthlyChart.update('none');
                    }
                    
                    // Messages Table
                    const tbody = document.getElementById('messages-body');
                    if (data.messages.length === 0) {
                        tbody.innerHTML = '<tr class="no-data"><td colspan="5">Waiting for messages...</td></tr>';
                    } else {
                        tbody.innerHTML = data.messages.slice(0, 15).map(m => {
                            const rateClass = m.rate < 15 ? 'delay-low' : m.rate < 25 ? 'delay-medium' : 'delay-high';
                            return `<tr>
                                <td><strong>${m.carrier}</strong></td>
                                <td>${m.airport}</td>
                                <td>${m.year}/${String(m.month).padStart(2,'0')}</td>
                                <td>${m.flights.toLocaleString()}</td>
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
    messages = list(message_buffer)[-30:]
    
    # Calculate averages
    total_rate = sum(m.get('rate', 0) for m in messages)
    avg_delay = total_rate / len(messages) if messages else 0
    
    # Carrier stats (top 10)
    carrier_data = []
    for carrier, data in carrier_stats.items():
        if data["count"] > 0:
            carrier_data.append({
                "carrier": carrier,
                "rate": round(data["total_rate"] / data["count"], 1)
            })
    carrier_data = sorted(carrier_data, key=lambda x: x["rate"], reverse=True)[:10]
    
    # Monthly stats
    monthly_data = [0] * 12
    for month, data in monthly_stats.items():
        if data["count"] > 0 and 1 <= month <= 12:
            monthly_data[month - 1] = round(data["total_rate"] / data["count"], 1)
    
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
        "messages": messages[::-1],
        "message_count": stats["message_count"],
        "kafka_connected": stats["kafka_connected"],
        "uptime": uptime,
        "avg_delay": avg_delay,
        "last_update": stats["last_update"],
        "partitions": stats.get("partitions", 3),
        "carrier_stats": carrier_data,
        "monthly_stats": monthly_data
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
        stats["partitions"] = 3
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
                        carrier = record.get("carrier", "N/A")
                        month = record.get("month", 0)
                        
                        msg_data = {
                            "carrier": carrier,
                            "airport": record.get("airport", "N/A"),
                            "year": record.get("year", 0),
                            "month": month,
                            "flights": flights,
                            "delayed": delayed,
                            "rate": rate
                        }
                        message_buffer.append(msg_data)
                        
                        # Update stats
                        carrier_stats[carrier]["count"] += 1
                        carrier_stats[carrier]["total_rate"] += rate
                        monthly_stats[month]["count"] += 1
                        monthly_stats[month]["total_rate"] += rate
                        
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
    print(f"  Kafka:  {KAFKA_HOST}:{KAFKA_PORT}")
    print(f"  Topic:  {KAFKA_TOPIC}")
    print("=" * 60)
    
    # Demarrer le thread Kafka
    kafka_thread = threading.Thread(target=kafka_consumer_thread, daemon=True)
    kafka_thread.start()
    
    # Demarrer Flask
    app.run(host='0.0.0.0', port=5000, debug=False)
