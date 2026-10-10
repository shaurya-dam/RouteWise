
import mysql.connector

connection = None
cursor = None

try:
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Qmpz65@gfanu",
        database="routewise"
    )

    print("MySQL connection successful!")

    cursor = connection.cursor()
    cursor.execute("SELECT DATABASE()")
    print("Connected database:", cursor.fetchone()[0])

    cursor.execute("SHOW TABLES LIKE 'charging_stations'")
    if cursor.fetchone():
        print("charging_stations table exists.")

        cursor.execute("SELECT COUNT(*) FROM charging_stations")
        print("Number of charging stations:", cursor.fetchone()[0])
    else:
        print("charging_stations table was not found.")

except mysql.connector.Error as error:
    print("MySQL error:", error)

finally:
    if cursor is not None:
        cursor.close()

    if connection is not None and connection.is_connected():
        connection.close()
        print("Database connection closed.")
