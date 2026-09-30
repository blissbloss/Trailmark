"""
db.py
-----
Database access layer for the AI-Based Smart Trip Planner for Community Tourism System.

NOTE ON DATABASE ENGINE
========================
The project synopsis specifies MySQL as the production database. This build uses
Python's built-in `sqlite3` module so the project runs immediately with zero setup.
The schema below is MySQL-compatible; the exact MySQL DDL is in `schema_mysql.sql`.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "trip_planner.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'traveler',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS destinations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    state TEXT,
    description TEXT,
    category TEXT,
    community_tourism INTEGER DEFAULT 0,
    avg_daily_cost REAL DEFAULT 1500,
    rating REAL DEFAULT 4.0,
    image_seed TEXT,
    image_url TEXT,
    latitude REAL,
    longitude REAL
);

CREATE TABLE IF NOT EXISTS hotels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    destination_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    price_per_night REAL NOT NULL,
    rating REAL DEFAULT 4.0,
    is_homestay INTEGER DEFAULT 0,
    latitude REAL,
    longitude REAL,
    FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS restaurants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    destination_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    cuisine TEXT,
    price_per_meal REAL NOT NULL,
    rating REAL DEFAULT 4.0,
    local_owned INTEGER DEFAULT 0,
    latitude REAL,
    longitude REAL,
    FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    destination_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    category TEXT,
    description TEXT,
    cost REAL DEFAULT 0,
    duration_hours REAL DEFAULT 2,
    community_run INTEGER DEFAULT 0,
    latitude REAL,
    longitude REAL,
    FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS transport_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    destination_id INTEGER NOT NULL,
    mode TEXT NOT NULL,
    cost REAL NOT NULL,
    duration_hours REAL NOT NULL,
    FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS trip_rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    creator_user_id INTEGER NOT NULL,
    status TEXT DEFAULT 'collecting',
    created_at TEXT NOT NULL,
    FOREIGN KEY (creator_user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS room_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    joined_at TEXT NOT NULL,
    UNIQUE(room_id, user_id),
    FOREIGN KEY (room_id) REFERENCES trip_rooms(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS room_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    budget REAL NOT NULL,
    interests TEXT,
    submitted_at TEXT NOT NULL,
    UNIQUE(room_id, user_id),
    FOREIGN KEY (room_id) REFERENCES trip_rooms(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS trips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    destination_id INTEGER NOT NULL,
    duration_days INTEGER NOT NULL,
    travelers_count INTEGER NOT NULL DEFAULT 1,
    budget REAL NOT NULL,
    interests TEXT,
    pace TEXT DEFAULT 'balanced',
    status TEXT DEFAULT 'planned',
    room_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE,
    FOREIGN KEY (room_id) REFERENCES trip_rooms(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS itinerary_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL,
    day_number INTEGER NOT NULL,
    item_type TEXT NOT NULL,
    ref_id INTEGER,
    title TEXT NOT NULL,
    start_time TEXT,
    cost REAL DEFAULT 0,
    notes TEXT,
    latitude REAL,
    longitude REAL,
    FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    ntype TEXT DEFAULT 'info',
    created_at TEXT NOT NULL,
    FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    destination_id INTEGER NOT NULL,
    rating INTEGER NOT NULL,
    comment TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE
);
"""


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def now():
    return datetime.utcnow().isoformat(timespec="seconds")
