
import os
import mysql.connector
from dotenv import load_dotenv

# Load database settings from .env
load_dotenv()

connection = None
cursor = None

try:
    # Connect to the RouteWise database
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

    if connection.is_connected():
        print("MySQL connection successful!")
        print("Connected database:", connection.database)

        # Check database tables
        cursor = connection.cursor()
        cursor.execute("SHOW TABLES")

        print("\nTables in RouteWise:")
        for table in cursor.fetchall():
            print("-", table[0])

        # Check sample station records
        cursor.execute("SELECT COUNT(*) FROM charging_stations")
        print("\nCharging stations:", cursor.fetchone()[0])

        cursor.execute("SELECT COUNT(*) FROM fuel_stations")
        print("Fuel stations:", cursor.fetchone()[0])

except mysql.connector.Error as error:
    print("MySQL connection failed:", error)

finally:
    if cursor is not None:
        cursor.close()

    if connection is not None and connection.is_connected():
        connection.close()
        print("\nDatabase connection closed.")
