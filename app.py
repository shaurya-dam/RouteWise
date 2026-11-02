import os
import re
import subprocess
from math import radians, sin, cos, sqrt, atan2

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from db import get_available_charging_stations, save_vehicle_data

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Attempt to load .env file
load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__)

# Fallback API key mechanism if .env fails to load
HARDCODED_API_KEY = "KAPybFJvNpPrXre1o4F2dy7ywR0IYTtB"
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY") or HARDCODED_API_KEY
TOMTOM_MAP_KEY = os.getenv("TOMTOM_MAP_KEY") or HARDCODED_API_KEY

BACKEND_DIR = os.path.join(BASE_DIR, "backend")
CPP_EXE = os.path.join(BACKEND_DIR, "RouteWiseEngine.exe") if os.name == 'nt' else os.path.join(BACKEND_DIR, "RouteWiseEngine")

DEFAULT_LATITUDE = 30.3165
DEFAULT_LONGITUDE = 78.0322
DEFAULT_CITY = "Dehradun"

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def safe_float(value):
    """Convert a value to float, or return None if invalid."""
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None

def calculate_distance_km(lat1, lon1, lat2, lon2):
    earth_radius = 6371.0
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    a = max(0.0, min(1.0, a))
    return 2 * earth_radius * atan2(sqrt(a), sqrt(1 - a))

def rank_stations_by_distance(stations, latitude, longitude):
    valid_stations = []
    for station in stations:
        lat = safe_float(station.get("latitude"))
        lon = safe_float(station.get("longitude"))

        if lat is None or lon is None:
            continue

        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue

        station["distance_km"] = round(
            calculate_distance_km(latitude, longitude, lat, lon),
            2
        )
        valid_stations.append(station)

    valid_stations.sort(key=lambda station: station["distance_km"])
    return valid_stations

def validate_data(vehicle_type, form_data):
    """Validate submitted form values."""
    errors = []
    vehicle_model = form_data.get("vehicle_model", "").strip()

    if not vehicle_model:
        errors.append("Please enter the vehicle model.")

    required_fields = {
        "PETROL": ["fuel_percent", "tank_capacity", "mileage"],
        "DIESEL": ["fuel_percent", "tank_capacity", "mileage"],
        "EV": ["battery_percent", "battery_capacity", "efficiency"],
        "HYBRID": ["fuel_percent", "tank_capacity", "mileage", "battery_percent"],
    }

    if vehicle_type not in required_fields:
        errors.append("Please select a valid vehicle type.")
        return errors

    values = {}
    for field in required_fields[vehicle_type]:
        value = safe_float(form_data.get(field))
        if value is None:
            errors.append(f"Please enter a valid value for {field.replace('_', ' ')}.")
        else:
            values[field] = value

    if errors:
        return errors

    for field in ("fuel_percent", "battery_percent"):
        if field in values and not 0 <= values[field] <= 100:
            errors.append(f"{field.replace('_', ' ').title()} must be between 0 and 100.")

    for field in ("tank_capacity", "battery_capacity", "mileage", "efficiency"):
        if field in values and values[field] <= 0:
            errors.append(f"{field.replace('_', ' ').title()} must be greater than 0.")

    return errors

# ============================================================
# TOMTOM API INTEGRATION
# ============================================================

def get_tomtom_fuel_stations(latitude, longitude, radius_km=10):
    if not TOMTOM_API_KEY:
        raise RuntimeError("TOMTOM_API_KEY is missing.")

    url = "https://api.tomtom.com/search/2/poiSearch/fuel.json"
    response = requests.get(
        url,
        params={
            "key": TOMTOM_API_KEY,
            "lat": latitude,
            "lon": longitude,
            "radius": int(min(max(radius_km, 0.1), 50) * 1000),
            "limit": 100,
            "countrySet": "IN",
        },
        timeout=20,
    )
    response.raise_for_status()

    stations = []
    for item in response.json().get("results", []):
        poi = item.get("poi", {})
        address = item.get("address", {})
        position = item.get("position", {})

        stations.append({
            "name": poi.get("name", "Unknown fuel station"),
            "address": address.get("freeformAddress", ""),
            "latitude": position.get("lat"),
            "longitude": position.get("lon"),
        })

    return stations

def get_tomtom_ev_stations(latitude, longitude, radius_km=10):
    if not TOMTOM_API_KEY:
        raise RuntimeError("TOMTOM_API_KEY is missing.")

    url = "https://api.tomtom.com/search/2/poiSearch/electric%20vehicle%20charging%20station.json"
    response = requests.get(
        url,
        params={
            "key": TOMTOM_API_KEY,
            "lat": latitude,
            "lon": longitude,
            "radius": int(min(max(radius_km, 0.1), 50) * 1000),
            "limit": 100,
            "countrySet": "IN",
        },
        timeout=20,
    )
    response.raise_for_status()

    stations = []
    for item in response.json().get("results", []):
        poi = item.get("poi", {})
        address = item.get("address", {})
        position = item.get("position", {})
        charging_park = item.get("chargingPark") or {}

        stations.append({
            "name": poi.get("name", "Unknown charging station"),
            "address": address.get("freeformAddress", ""),
            "latitude": position.get("lat"),
            "longitude": position.get("lon"),
            "connectors": charging_park.get("connectors", []),
        })

    return stations

# ============================================================
# C++ OOP ENGINE INTEGRATION
# ============================================================

def calculate_cpp_safe_range(vehicle_type, form_data):
    """Pass raw vehicle inputs directly to compiled C++ OOP Engine binary."""
    if not os.path.isfile(CPP_EXE):
        raise FileNotFoundError(
            f"C++ executable not found at '{CPP_EXE}'. Compile backend/logic.cpp first."
        )

    vehicle_type = vehicle_type.strip().upper()

    percent = 0.0
    capacity = 0.0
    efficiency = 0.0
    connector = "Type-2"

    if vehicle_type == "EV":
        percent = safe_float(form_data.get("battery_percent"))
        capacity = safe_float(form_data.get("battery_capacity"))
        efficiency = safe_float(form_data.get("efficiency"))
        connector = form_data.get("connector", "Type-2")
    elif vehicle_type in ("PETROL", "DIESEL"):
        percent = safe_float(form_data.get("fuel_percent"))
        capacity = safe_float(form_data.get("tank_capacity"))
        efficiency = safe_float(form_data.get("mileage"))
        connector = "None"
    elif vehicle_type == "HYBRID":
        percent = safe_float(form_data.get("fuel_percent"))
        capacity = safe_float(form_data.get("tank_capacity"))
        efficiency = safe_float(form_data.get("mileage"))
        connector = "Type-2"
    else:
        raise ValueError("Invalid vehicle type.")

    # Execute C++ binary
    result = subprocess.run(
        [
            CPP_EXE,
            vehicle_type,
            str(percent),
            str(capacity),
            str(efficiency),
            str(connector)
        ],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    output = (result.stdout or "").strip()
    error_output = (result.stderr or "").strip()

    if result.returncode != 0:
        raise RuntimeError(error_output or output or "C++ engine execution failed.")

    match = re.search(r"Calculated\s+Safe\s+Usable\s+Range:\s*([-+]?\d+(?:\.\d+)?)\s*km", output, re.IGNORECASE)
    if not match:
        match = re.search(r"Usable\s+Range:\s*([-+]?\d+(?:\.\d+)?)\s*km", output, re.IGNORECASE)

    if not match:
        raise RuntimeError("Could not parse calculated usable range from C++ output:\n" + output)

    return float(match.group(1)), output

# ============================================================
# API ROUTES
# ============================================================

@app.route("/test-tomtom")
def test_tomtom():
    if not TOMTOM_API_KEY:
        return jsonify({"success": False, "message": "TOMTOM_API_KEY missing."}), 500
    try:
        stations = get_tomtom_fuel_stations(DEFAULT_LATITUDE, DEFAULT_LONGITUDE)
        return jsonify({
            "success": True, 
            "message": "TomTom API connection successful.", 
            "station_count": len(stations), 
            "stations": stations
        })
    except Exception as exc:
        app.logger.exception("TomTom test failed")
        return jsonify({"success": False, "message": str(exc)}), 500

@app.route("/fuel-stations")
def fuel_stations():
    latitude = safe_float(request.args.get("lat")) or DEFAULT_LATITUDE
    longitude = safe_float(request.args.get("lon")) or DEFAULT_LONGITUDE
    try:
        stations = get_tomtom_fuel_stations(latitude, longitude)
        return jsonify({"success": True, "stations": stations})
    except Exception as exc:
        app.logger.exception("Fuel station lookup failed")
        return jsonify({"success": False, "message": str(exc), "stations": []}), 500

@app.route("/station-recommendations")
def station_recommendations():
    vehicle_type = request.args.get("vehicle_type", "").strip().upper()
    latitude = safe_float(request.args.get("lat"))
    longitude = safe_float(request.args.get("lon"))
    range_km = safe_float(request.args.get("range_km"))

    if vehicle_type not in ("PETROL", "DIESEL", "EV", "HYBRID"):
        return jsonify({"success": False, "message": "Invalid vehicle type.", "stations": []}), 400

    if latitude is None or longitude is None:
        return jsonify({"success": False, "message": "Select current location first.", "stations": []}), 400

    if range_km is None or range_km <= 0:
        return jsonify({"success": False, "message": "Calculate valid range first.", "stations": []}), 400

    try:
        stations = []
        if vehicle_type in ("PETROL", "DIESEL", "HYBRID"):
            fuel_stations = get_tomtom_fuel_stations(latitude, longitude, range_km)
            for st in fuel_stations:
                st["station_type"] = "Fuel"
                stations.append(st)

        if vehicle_type in ("EV", "HYBRID"):
            ev_stations = get_tomtom_ev_stations(latitude, longitude, range_km)
            for st in ev_stations:
                st["station_type"] = "EV Charging"
                stations.append(st)

        stations = rank_stations_by_distance(stations, latitude, longitude)
        stations = [st for st in stations if st["distance_km"] <= range_km]

        return jsonify({
            "success": True,
            "vehicle_type": vehicle_type,
            "range_km": range_km,
            "count": len(stations),
            "stations": stations
        })
    except Exception:
        app.logger.exception("Station recommendation lookup failed")
        return jsonify({"success": False, "message": "Unable to load nearby stations.", "stations": []}), 502

@app.route("/charging-stations")
def charging_stations():
    city = request.args.get("city", DEFAULT_CITY).strip() or DEFAULT_CITY
    try:
        stations = get_available_charging_stations()
        return jsonify({"success": True, "count": len(stations), "stations": stations})
    except Exception as exc:
        app.logger.exception("MySQL charging station lookup failed")
        return jsonify({"success": False, "message": str(exc), "stations": []}), 500

@app.route("/calculate-route", methods=["GET"])
def calculate_route():
    origin_lat = safe_float(request.args.get("origin_lat"))
    origin_lon = safe_float(request.args.get("origin_lon"))
    dest_lat = safe_float(request.args.get("dest_lat"))
    dest_lon = safe_float(request.args.get("dest_lon"))

    if any(val is None for val in [origin_lat, origin_lon, dest_lat, dest_lon]):
        return jsonify({"success": False, "message": "Coordinates are required."}), 400

    if not TOMTOM_API_KEY:
        return jsonify({"success": False, "message": "TomTom API key missing."}), 500

    locations = f"{origin_lat},{origin_lon}:{dest_lat},{dest_lon}"
    url = f"https://api.tomtom.com/routing/1/calculateRoute/{locations}/json"

    try:
        response = requests.get(
            url,
            params={
                "key": TOMTOM_API_KEY,
                "travelMode": "car",
                "routeType": "fastest",
                "traffic": "true",
                "routeRepresentation": "polyline"
            },
            timeout=20
        )
        response.raise_for_status()
        routes = response.json().get("routes", [])

        if not routes:
            return jsonify({"success": False, "message": "No route found."}), 502

        route = routes[0]
        summary = route.get("summary", {})
        points = [{"lat": p["latitude"], "lon": p["longitude"]} for leg in route.get("legs", []) for p in leg.get("points", [])]

        return jsonify({
            "success": True,
            "distance_km": round(summary.get("lengthInMeters", 0) / 1000, 2),
            "travel_time_minutes": round(summary.get("travelTimeInSeconds", 0) / 60),
            "points": points
        })
    except Exception as exc:
        app.logger.exception("TomTom routing failed")
        return jsonify({"success": False, "message": str(exc)}), 502

# ============================================================
# PAGE ROUTING (HOME LANDING PAGE & MAIN APP)
# ============================================================

@app.route("/")
def home():
    """Default Purple/Black Gradient Landing Page."""
    return render_template("home.html")

@app.route("/app", methods=["GET", "POST"])
def index():
    """Main RouteWise Interactive Application."""
    selected_vehicle = ""
    vehicle_model = ""
    data = {}
    errors = []
    stations = []
    success = False
    safe_range = None
    range_status = None
    active_tab = "vehicle"
    cpp_route_data = None

    if request.method == "GET":
        selected_vehicle = request.args.get("vehicle_type", "").strip().upper()

    if request.method == "POST":
        data = request.form.to_dict()
        selected_vehicle = data.get("vehicle_type", "").strip().upper()
        vehicle_model = data.get("vehicle_model", "").strip()

        errors = validate_data(selected_vehicle, data)

        if not errors:
            try:
                safe_range, cpp_output = calculate_cpp_safe_range(selected_vehicle, data)

                success = True
                active_tab = "dashboard"

                if safe_range >= 80:
                    range_status = "Normal"
                elif safe_range >= 30:
                    range_status = "Low"
                else:
                    range_status = "Critical"

                if selected_vehicle in ("EV", "HYBRID"):
                    try:
                        stations = get_available_charging_stations()
                    except Exception:
                        app.logger.exception("Unable to load database stations")

                cpp_route_data = {
                    "safe_range": safe_range,
                    "cpp_output": cpp_output
                }

            except Exception as exc:
                app.logger.exception("Safe range calculation failed")
                errors.append(str(exc))

    return render_template(
        "index.html",
        selected_vehicle=selected_vehicle,
        vehicle_model=vehicle_model,
        data=data,
        errors=errors,
        success=success,
        safe_range=safe_range,
        range_status=range_status,
        stations=stations,
        show_energy=success,
        active_tab=active_tab,
        tomtom_map_key=TOMTOM_MAP_KEY,
        cpp_route_data=cpp_route_data
    )

# ============================================================
# START FLASK SERVER
# ============================================================

if __name__ == "__main__":
    app.run(debug=True)