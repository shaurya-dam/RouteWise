
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST","localhost"),
        user=os.getenv("DB_USER", "root"),
        database=os.getenv("DB_NAME", "routewise"),
        password=os.environ["DB_PASSWORD"],
    )


def get_available_charging_stations(city="Dehradun"):
    connection = get_db_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT station_id, station_name, address, city,
                   latitude, longitude, total_chargers,
                   available_chargers, charging_speed, price_per_kwh
            FROM charging_stations
            WHERE available_chargers > 0
              AND city = %s
            """,
            (city,)
        )

        return cursor.fetchall()

    finally:
        connection.close()


def save_vehicle_data(vehicle_type, form_data):
    connection = get_db_connection()

    try:
        cursor = connection.cursor()

        fuel_capacity = None
        current_fuel = None
        fuel_percentage = None

        battery_capacity = None
        current_battery = None
        battery_percentage = None

        if vehicle_type in ("PETROL", "HYBRID"):
            fuel_capacity = float(form_data["tank_capacity"])
            fuel_percentage = float(form_data["fuel_percent"])
            current_fuel = fuel_capacity * fuel_percentage / 100

        if vehicle_type in ("EV", "HYBRID"):
            battery_percentage = float(form_data["battery_percent"])

            # EV battery capacity comes from the form.
            if vehicle_type == "EV":
                battery_capacity = float(form_data["battery_capacity"])
                current_battery = (
                    battery_capacity * battery_percentage / 100
                )

        cursor.execute(
            """
            INSERT INTO vehicle_fuel_data (
                vehicle_type, fuel_type,
                fuel_capacity, current_fuel, fuel_percentage,
                battery_capacity, current_battery, battery_percentage
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                vehicle_type,
                "PETROL" if vehicle_type in ("PETROL", "HYBRID") else None,
                fuel_capacity,
                current_fuel,
                fuel_percentage,
                battery_capacity,
                current_battery,
                battery_percentage,
            )
        )

        connection.commit()

    finally:
        connection.close()

