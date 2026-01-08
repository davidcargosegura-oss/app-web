
import sqlite3
import os

db_path = 'database.db'

if not os.path.exists(db_path):
    print(f"ERROR: {db_path} not found.")
    exit(1)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("--- TRUCK TABLE ---")
    cursor.execute("PRAGMA table_info(truck)")
    truck_cols = [row[1] for row in cursor.fetchall()]
    print("Columns:", truck_cols)
    
    expected_truck = ['manual_location', 'is_zone_manual', 'manual_zones_str']
    missing_truck = [c for c in expected_truck if c not in truck_cols]
    
    if missing_truck:
        print(f"MISSING TRUCK COLUMNS: {missing_truck}")
    else:
        print("ALL TRUCK COLUMNS PRESENT")

    print("\n--- TRIP TABLE ---")
    cursor.execute("PRAGMA table_info(trip)")
    trip_cols = [row[1] for row in cursor.fetchall()]
    print("Columns:", trip_cols)
    
    if 'destination_zone' not in trip_cols:
        print("MISSING TRIP COLUMN: destination_zone")
    else:
        print("ALL TRIP COLUMNS PRESENT")
        
    conn.close()
    
except Exception as e:
    print(f"Error inspecting DB: {e}")
