from db import get_available_charging_stations

stations = get_available_charging_stations()

print("Stations found:", len(stations))

for station in stations:
    print(station)