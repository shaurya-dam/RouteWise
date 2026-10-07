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

INSERT INTO charging_stations(
    station_name,
    address,
    city,
    latitude,
    longitude,
    total_chargers,
    charging_speed,
    price_per_kwh
)
VALUES(
    'Trial EV Station 1',
    'Rajpur Road',
    'Dehradun',
    30.3165,
    78.0322,
    6,
    4,
    60.00,
    15.00
),
(
    'Trial EV Station 2',
    'Haridwar Road',
    'Dehradun',
    30.2900,
    78.0500,
    4,
    2,
    50.00,
    14.00
);

SELECT * FROM charging_stations;