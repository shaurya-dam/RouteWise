
import os
import mysql.connector


def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user=os.environ.get("DB_USER", "root"),
        password=os.environ["DB_PASSWORD"],
        database="routewise"
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
