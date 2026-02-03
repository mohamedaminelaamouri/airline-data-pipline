#!/usr/bin/env python3
"""
Script pour charger les données GPS des aéroports dans ClickHouse.
Table: airline_data.airports_gps
"""

import csv
import clickhouse_connect
from pathlib import Path


def create_airports_table(client):
    """Créer la table airports_gps si elle n'existe pas."""
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS airline_data.airports_gps (
        airport_code String,
        airport_full_name String,
        city String,
        state String,
        country_code String,
        latitude Float64,
        longitude Float64
    ) ENGINE = MergeTree()
    ORDER BY airport_code
    COMMENT 'Table des aéroports avec coordonnées GPS'
    """
    
    client.command(create_table_sql)
    print("✅ Table airports_gps créée/vérifiée")


def load_airports_data(client, csv_path: str):
    """Charger les données CSV dans la table."""
    
    # Vider la table avant insertion (pour éviter les doublons)
    client.command("TRUNCATE TABLE airline_data.airports_gps")
    print("🗑️  Table vidée")
    
    # Lire le CSV
    airports = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            airports.append([
                row['airport_code'],
                row['airport_full_name'],
                row['city'],
                row['state'],
                row['country_code'],
                float(row['latitude']),
                float(row['longitude'])
            ])
    
    # Insérer les données
    client.insert(
        'airline_data.airports_gps',
        airports,
        column_names=['airport_code', 'airport_full_name', 'city', 'state', 
                      'country_code', 'latitude', 'longitude']
    )
    
    print(f"✅ {len(airports)} aéroports chargés")
    return len(airports)


def verify_data(client):
    """Vérifier les données chargées."""
    
    # Compter les enregistrements
    count = client.command("SELECT count() FROM airline_data.airports_gps")
    print(f"\n📊 Total aéroports: {count}")
    
    # Afficher quelques exemples
    print("\n🔍 Exemples d'aéroports:")
    result = client.query("""
        SELECT airport_code, city, state, latitude, longitude 
        FROM airline_data.airports_gps 
        ORDER BY airport_code 
        LIMIT 10
    """)
    
    for row in result.result_rows:
        print(f"   {row[0]}: {row[1]}, {row[2]} ({row[3]:.4f}, {row[4]:.4f})")
    
    # Stats par état
    print("\n📈 Top 10 états par nombre d'aéroports:")
    result = client.query("""
        SELECT state, count() as cnt 
        FROM airline_data.airports_gps 
        WHERE state != 'Unknown'
        GROUP BY state 
        ORDER BY cnt DESC 
        LIMIT 10
    """)
    
    for row in result.result_rows:
        print(f"   {row[0]}: {row[1]} aéroports")


def main():
    """Fonction principale."""
    
    print("=" * 50)
    print("🛫 Chargement des données GPS des aéroports")
    print("=" * 50)
    
    # Connexion ClickHouse
    client = clickhouse_connect.get_client(
        host='localhost',
        port=8123,
        database='airline_data'
    )
    print("✅ Connecté à ClickHouse")
    
    # Chemin du fichier CSV
    csv_path = Path(__file__).parent.parent / 'data' / 'airports_gps.csv'
    
    if not csv_path.exists():
        print(f"❌ Fichier non trouvé: {csv_path}")
        return
    
    print(f"📁 Fichier CSV: {csv_path}")
    
    # Créer la table
    create_airports_table(client)
    
    # Charger les données
    load_airports_data(client, str(csv_path))
    
    # Vérifier
    verify_data(client)
    
    print("\n" + "=" * 50)
    print("✅ Chargement terminé avec succès!")
    print("=" * 50)


if __name__ == "__main__":
    main()
