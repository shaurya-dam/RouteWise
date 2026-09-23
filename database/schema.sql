CREATE DATABASE routewise;

USE routewise;

CREATE TABLE charging_stations (
    station_id INT PRIMARY KEY AUTO_INCREMENT,
    station_name VARCHAR(100) NOT NULL,
    address VARCHAR(255),
    city VARCHAR(100),
    latitude DECIMAL(10,7),
    longitude DECIMAL(10,7),
    total_chargers INT DEFAULT 0,
    available_chargers INT DEFAULT 0,
    charging_speed DECIMAL(6,2),
    price_per_kwh DECIMAL(8,2)
);