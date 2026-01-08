
import sqlite3
import os

db_path = 'database.db'


# Always try to connect and create tables if they don't exist
try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("--- 1. ENSURING TABLES EXIST ---")
    # Create tables if they don't exist (Simplified schema from app.py)
    cursor.execute('''CREATE TABLE IF NOT EXISTS truck (
        id INTEGER PRIMARY KEY,
        plate VARCHAR(20) UNIQUE NOT NULL,
        location VARCHAR(100) DEFAULT '',
        location_last_updated VARCHAR(20) DEFAULT '2000-01-01',
        creation_date VARCHAR(20) NOT NULL,
        deletion_date VARCHAR(20),
        is_location_manual BOOLEAN DEFAULT 0,
        is_zone_manual BOOLEAN DEFAULT 0,
        zones_str VARCHAR(200) DEFAULT '',
        manual_location VARCHAR(100) DEFAULT '',
        zones_last_updated VARCHAR(20) DEFAULT '2000-01-01',
        trailer VARCHAR(50) DEFAULT '',
        driver_name VARCHAR(100) DEFAULT '',
        driver_phone VARCHAR(20) DEFAULT '',
        driver_dni VARCHAR(20) DEFAULT '',
        driver_alias VARCHAR(50) DEFAULT '',
        manual_zones_str VARCHAR(200) DEFAULT '',
        history_str TEXT DEFAULT '[]'
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS trip (
        id INTEGER PRIMARY KEY,
        type VARCHAR(20) NOT NULL,
        client VARCHAR(100) NOT NULL,
        driver VARCHAR(100) DEFAULT '',
        origin VARCHAR(100) NOT NULL,
        destination VARCHAR(100) NOT NULL,
        destination_zone VARCHAR(50),
        load_date VARCHAR(20) NOT NULL,
        unload_date VARCHAR(20) NOT NULL,
        assigned_truck_plate VARCHAR(20),
        assigned_slot INTEGER,
        is_urgent BOOLEAN DEFAULT 0,
        is_groupage BOOLEAN DEFAULT 0,
        zone VARCHAR(50),
        pg INTEGER DEFAULT 0,
        ep INTEGER DEFAULT 0,
        pp INTEGER DEFAULT 0,
        notify_time VARCHAR(20) DEFAULT "",
        is_notified BOOLEAN DEFAULT 0,
        FOREIGN KEY(assigned_truck_plate) REFERENCES truck(plate)
    )''')
    
    # Also ensure other tables exist
    cursor.execute('''CREATE TABLE IF NOT EXISTS daily_note (
        id INTEGER PRIMARY KEY,
        date VARCHAR(20) NOT NULL,
        type VARCHAR(20) NOT NULL,
        content TEXT DEFAULT '',
        CONSTRAINT unique_date_type UNIQUE (date, type)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS truck_fds (
        id INTEGER PRIMARY KEY,
        truck_plate VARCHAR(20) NOT NULL,
        date VARCHAR(20) NOT NULL,
        is_out_of_service BOOLEAN DEFAULT 1,
        FOREIGN KEY(truck_plate) REFERENCES truck(plate),
        CONSTRAINT unique_plate_date UNIQUE (truck_plate, date)
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS driver (
        id INTEGER PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        dni VARCHAR(20) DEFAULT '',
        phone VARCHAR(20) DEFAULT '',
        alias VARCHAR(50) DEFAULT ''
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS trailer (
        id INTEGER PRIMARY KEY,
        plate VARCHAR(20) UNIQUE NOT NULL,
        type VARCHAR(50) DEFAULT ''
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS user (
        id INTEGER PRIMARY KEY,
        username VARCHAR(80) UNIQUE NOT NULL,
        password_hash VARCHAR(128),
        is_admin BOOLEAN DEFAULT 0
    )''')
    
    conn.commit()
    print("Tables check/creation complete.")

    # --- 2. UPDATING COLUMNS ---

    print("Checking Truck table...")
    truck_cols_to_add = [
        ("manual_location", "VARCHAR(100) DEFAULT ''"),
        ("is_zone_manual", "BOOLEAN DEFAULT 0"),
        ("manual_zones_str", "VARCHAR(200) DEFAULT ''"),
        ("zones_last_updated", "VARCHAR(20) DEFAULT '2000-01-01'"),
        ("trailer", "VARCHAR(50) DEFAULT ''"),
        ("driver_name", "VARCHAR(100) DEFAULT ''"),
        ("driver_phone", "VARCHAR(20) DEFAULT ''"),
        ("driver_dni", "VARCHAR(20) DEFAULT ''"),
        ("driver_alias", "VARCHAR(50) DEFAULT ''"),
        ("history_str", "TEXT DEFAULT '[]'")
    ]
    
    cursor.execute("PRAGMA table_info(truck)")
    existing_truck_cols = [row[1] for row in cursor.fetchall()]
    
    for col_name, col_def in truck_cols_to_add:
        if col_name not in existing_truck_cols:
            print(f"Adding column {col_name} to truck...")
            try:
                cursor.execute(f"ALTER TABLE truck ADD COLUMN {col_name} {col_def}")
                print(f"  > Added {col_name}")
            except Exception as e:
                print(f"  ! Error adding {col_name}: {e}")
        else:
            print(f"  - {col_name} exists.")

    # --- TRIP UPDATES ---
    print("\nChecking Trip table...")
    trip_cols_to_add = [
        ("destination_zone", "VARCHAR(50)")
    ]
    
    cursor.execute("PRAGMA table_info(trip)")
    existing_trip_cols = [row[1] for row in cursor.fetchall()]
    
    for col_name, col_def in trip_cols_to_add:
        if col_name not in existing_trip_cols:
            print(f"Adding column {col_name} to trip...")
            try:
                cursor.execute(f"ALTER TABLE trip ADD COLUMN {col_name} {col_def}")
                print(f"  > Added {col_name}")
            except Exception as e:
                print(f"  ! Error adding {col_name}: {e}")
        else:
            print(f"  - {col_name} exists.")
            
    conn.commit()
    conn.close()
    print("\nSchema update complete.")
    
except Exception as e:
    print(f"CRITICAL ERROR: {e}")
