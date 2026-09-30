-- ============================================================
-- AI-Based Smart Trip Planner for Community Tourism System
-- Production schema (MySQL 8+)
-- ============================================================

CREATE DATABASE IF NOT EXISTS smart_trip_planner CHARACTER SET utf8mb4;
USE smart_trip_planner;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('traveler','admin') NOT NULL DEFAULT 'traveler',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE destinations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    state VARCHAR(100),
    description TEXT,
    category VARCHAR(60),
    community_tourism TINYINT(1) DEFAULT 0,
    avg_daily_cost DECIMAL(10,2) DEFAULT 1500.00,
    rating DECIMAL(2,1) DEFAULT 4.0,
    image_seed VARCHAR(120),
    image_url VARCHAR(500),
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6)
) ENGINE=InnoDB;

CREATE TABLE hotels (
    id INT AUTO_INCREMENT PRIMARY KEY,
    destination_id INT NOT NULL,
    name VARCHAR(150) NOT NULL,
    price_per_night DECIMAL(10,2) NOT NULL,
    rating DECIMAL(2,1) DEFAULT 4.0,
    is_homestay TINYINT(1) DEFAULT 0,
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE restaurants (
    id INT AUTO_INCREMENT PRIMARY KEY,
    destination_id INT NOT NULL,
    name VARCHAR(150) NOT NULL,
    cuisine VARCHAR(100),
    price_per_meal DECIMAL(10,2) NOT NULL,
    rating DECIMAL(2,1) DEFAULT 4.0,
    local_owned TINYINT(1) DEFAULT 0,
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE activities (
    id INT AUTO_INCREMENT PRIMARY KEY,
    destination_id INT NOT NULL,
    name VARCHAR(150) NOT NULL,
    category VARCHAR(60),
    description TEXT,
    cost DECIMAL(10,2) DEFAULT 0,
    duration_hours DECIMAL(4,1) DEFAULT 2.0,
    community_run TINYINT(1) DEFAULT 0,
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE transport_options (
    id INT AUTO_INCREMENT PRIMARY KEY,
    destination_id INT NOT NULL,
    mode VARCHAR(40) NOT NULL,
    cost DECIMAL(10,2) NOT NULL,
    duration_hours DECIMAL(4,1) NOT NULL,
    FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE trip_rooms (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(12) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    creator_user_id INT NOT NULL,
    status VARCHAR(30) DEFAULT 'collecting',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (creator_user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE room_members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    room_id INT NOT NULL,
    user_id INT NOT NULL,
    joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_room_user (room_id, user_id),
    FOREIGN KEY (room_id) REFERENCES trip_rooms(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE room_preferences (
    id INT AUTO_INCREMENT PRIMARY KEY,
    room_id INT NOT NULL,
    user_id INT NOT NULL,
    budget DECIMAL(10,2) NOT NULL,
    interests VARCHAR(255),
    submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_room_user_pref (room_id, user_id),
    FOREIGN KEY (room_id) REFERENCES trip_rooms(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE trips (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    destination_id INT NOT NULL,
    duration_days INT NOT NULL,
    travelers_count INT NOT NULL DEFAULT 1,
    budget DECIMAL(10,2) NOT NULL,
    interests VARCHAR(255),
    pace ENUM('relaxed','balanced','packed') DEFAULT 'balanced',
    status VARCHAR(30) DEFAULT 'planned',
    room_id INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE,
    FOREIGN KEY (room_id) REFERENCES trip_rooms(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE itinerary_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trip_id INT NOT NULL,
    day_number INT NOT NULL,
    item_type VARCHAR(30) NOT NULL,
    ref_id INT,
    title VARCHAR(200) NOT NULL,
    start_time VARCHAR(20),
    cost DECIMAL(10,2) DEFAULT 0,
    notes TEXT,
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trip_id INT NOT NULL,
    message VARCHAR(500) NOT NULL,
    ntype VARCHAR(30) DEFAULT 'info',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE feedback (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    destination_id INT NOT NULL,
    rating INT NOT NULL,
    comment TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (destination_id) REFERENCES destinations(id) ON DELETE CASCADE
) ENGINE=InnoDB;
