"""
Airline Data Pipeline - Real-time Kafka Monitor
Version simplifiee pour execution locale
"""

import json
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional

try:
    from confluent_kafka import Consumer, KafkaError
except ImportError:
    print("ERREUR: confluent-kafka non installe")
    print("Installation: pip install confluent-kafka")
    sys.exit(1)

# Configuration
KAFKA_HOST = "localhost"
KAFKA_PORT = 9092
KAFKA_TOPIC = "airline-delays"
KAFKA_GROUP_ID = "realtime-monitor"

# Compteurs
message_count = 0
start_time = None


def clear_screen():
    """Efface l'ecran."""
    print("\033[2J\033[H", end="")


def format_record(record: Dict[str, Any]) -> str:
    """Formate un record Kafka pour l'affichage."""
    carrier = record.get("carrier", "N/A")
    airport = record.get("airport", "N/A")
    year = record.get("year", "N/A")
    month = record.get("month", "N/A")
    flights = record.get("arr_flights", 0)
    delayed = record.get("arr_del15", 0)
    
    delay_rate = (delayed / flights * 100) if flights > 0 else 0
    
    return f"{carrier:>4} | {airport:>4} | {year}/{month:02d} | {flights:>5} vols | {delayed:>4} retards | {delay_rate:>5.1f}%"


def display_header():
    """Affiche l'en-tete."""
    global message_count, start_time
    
    uptime = ""
    if start_time:
        elapsed = int((datetime.now() - start_time).total_seconds())
        uptime = f" | Uptime: {elapsed}s"
    
    print("=" * 70)
    print(f"  AIRLINE DATA PIPELINE - Kafka Monitor")
    print(f"  Topic: {KAFKA_TOPIC} | Messages: {message_count}{uptime}")
    print("=" * 70)
    print(f"{'CARRIER':>6} | {'AIRPORT':>4} | {'DATE':>7} | {'VOLS':>6} | {'RETARDS':>7} | {'TAUX':>6}")
    print("-" * 70)


def run_monitor():
    """Boucle principale du monitor."""
    global message_count, start_time
    
    conf = {
        'bootstrap.servers': f"{KAFKA_HOST}:{KAFKA_PORT}",
        'group.id': KAFKA_GROUP_ID,
        'auto.offset.reset': 'latest',
        'enable.auto.commit': True,
    }
    
    print(f"Connexion a Kafka ({KAFKA_HOST}:{KAFKA_PORT})...")
    
    try:
        consumer = Consumer(conf)
        consumer.subscribe([KAFKA_TOPIC])
        print(f"Abonne au topic: {KAFKA_TOPIC}")
        print("En attente de messages... (Ctrl+C pour quitter)\n")
        
        start_time = datetime.now()
        last_display = time.time()
        recent_messages = []
        
        while True:
            msg = consumer.poll(timeout=1.0)
            
            if msg is None:
                # Rafraichir l'affichage toutes les 2 secondes
                if time.time() - last_display > 2:
                    clear_screen()
                    display_header()
                    for line in recent_messages[-15:]:
                        print(line)
                    last_display = time.time()
                continue
            
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                print(f"Erreur Kafka: {msg.error()}")
                continue
            
            try:
                raw = msg.value().decode("utf-8")
                data = json.loads(raw)
                
                records = [data] if isinstance(data, dict) else data
                
                for record in records:
                    if isinstance(record, dict):
                        message_count += 1
                        line = format_record(record)
                        recent_messages.append(line)
                        
                        # Garder seulement les 50 derniers
                        if len(recent_messages) > 50:
                            recent_messages = recent_messages[-50:]
                
                # Rafraichir l'affichage
                clear_screen()
                display_header()
                for line in recent_messages[-15:]:
                    print(line)
                last_display = time.time()
                
            except json.JSONDecodeError:
                pass
            except Exception as e:
                print(f"Erreur: {e}")
                
    except KeyboardInterrupt:
        print(f"\n\nArret du monitor. Total messages: {message_count}")
    except Exception as e:
        print(f"Erreur de connexion: {e}")
    finally:
        try:
            consumer.close()
        except:
            pass


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  AIRLINE DATA PIPELINE - Real-time Kafka Monitor")
    print("=" * 70 + "\n")
    
    run_monitor()
