
import os
import re
import subprocess

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from db import get_available_charging_stations


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Your environment file is named 1.env
load_dotenv(os.path.join(BASE_DIR, "1.env"))

app = Flask(__name__)

TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY")

BACKEND_DIR = os.path.join(BASE_DIR, "backend")
CPP_EXE = os.path.join(BACKEND_DIR, "RouteWiseEngine.exe")

DEFAULT_LATITUDE = 30.3165
DEFAULT_LONGITUDE = 78.0322
DEFAULT_CITY = "Dehradun"



# ============================================================
# MYSQL EV CHARGING STATION HELPER
# ============================================================

def get_stations_safely(city=DEFAULT_CITY):
    try:
        stations = get_available_charging_stations(city)
        return stations, None

    except Exception as exc:
        app.logger.exception(
            "Unable to retrieve charging stations from MySQL"
        )
        return [], str(exc)



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


def validate_data(vehicle_type, form_data):
    """Validate submitted form values without calculating range."""

    errors = []

    vehicle_model = form_data.get("vehicle_model", "").strip()

    if not vehicle_model:
        errors.append("Please enter the vehicle model.")

    required_fields = {
        "PETROL": ["fuel_percent", "tank_capacity", "mileage"],
        "DIESEL": ["fuel_percent", "tank_capacity", "mileage"],
        "EV": ["battery_percent", "battery_capacity", "efficiency"],
        "HYBRID": [
            "fuel_percent",
            "tank_capacity",
            "mileage",
            "battery_percent",
        ],
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

    # Stop numeric checks if required values are missing.
    if errors:
        return errors

    # Percentage validation
    for field in ("fuel_percent", "battery_percent"):
        if field in values and not 0 <= values[field] <= 100:
            errors.append(f"{field.replace('_', ' ').title()} must be between 0 and 100.")

    # Positive-value validation
    for field in ("tank_capacity", "battery_capacity", "mileage", "efficiency"):
        if field in values and values[field] <= 0:
            errors.append(f"{field.replace('_', ' ').title()} must be greater than 0.")

    return errors

def get_tomtom_fuel_stations(latitude, longitude):
    """Find nearby fuel stations using TomTom."""

    if not TOMTOM_API_KEY:
        raise RuntimeError("TOMTOM_API_KEY is missing from 1.env.")

    url = "https://api.tomtom.com/search/2/poiSearch/fuel.json"

    response = requests.get(
        url,
        params={
            "key": TOMTOM_API_KEY,
            "lat": latitude,
            "lon": longitude,
            "radius": 10000,
            "limit": 10,
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


def get_tomtom_ev_stations(latitude, longitude):
    """Find nearby EV charging stations using TomTom."""

    if not TOMTOM_API_KEY:
        raise RuntimeError("TOMTOM_API_KEY is missing from 1.env.")

    url = (
        "https://api.tomtom.com/search/2/"
        "poiSearch/electric%20vehicle%20charging%20station.json"
    )

    response = requests.get(
        url,
        params={
            "key": TOMTOM_API_KEY,
            "lat": latitude,
            "lon": longitude,
            "radius": 10000,
            "limit": 10,
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
# C++ ENGINE INTEGRATION
# IMPORTANT:
# C++ must accept the raw fields passed below and calculate
# the usable range. Python must not calculate the range.
# ============================================================


def calculate_cpp_safe_range(vehicle_type, form_data):
    """Pass maximum range and current energy percentage to C++."""

    if not os.path.isfile(CPP_EXE):
        raise FileNotFoundError(
            "C++ executable not found. Compile backend/logic.cpp first."
        )

    vehicle_type = vehicle_type.strip().upper()

    # C++ expects title-case names for Petrol, Diesel and Hybrid.
    cpp_types = {
        "PETROL": "Petrol",
        "DIESEL": "Diesel",
        "EV": "EV",
        "HYBRID": "Hybrid",
    }

    if vehicle_type not in cpp_types:
        raise ValueError("Invalid vehicle type.")

    if vehicle_type in ("PETROL", "DIESEL"):
        tank_capacity = safe_float(form_data.get("tank_capacity"))
        mileage = safe_float(form_data.get("mileage"))
        current_percent = safe_float(form_data.get("fuel_percent"))

        if (
            tank_capacity is None or tank_capacity <= 0
            or mileage is None or mileage <= 0
            or current_percent is None
            or not 0 <= current_percent <= 100
        ):
            raise ValueError("Invalid fuel inputs.")

        max_range = tank_capacity * mileage

    elif vehicle_type == "EV":
        battery_capacity = safe_float(form_data.get("battery_capacity"))
        efficiency = safe_float(form_data.get("efficiency"))
        current_percent = safe_float(form_data.get("battery_percent"))

        if (
            battery_capacity is None or battery_capacity <= 0
            or efficiency is None or efficiency <= 0
            or current_percent is None
            or not 0 <= current_percent <= 100
        ):
            raise ValueError("Invalid EV inputs.")

        max_range = battery_capacity * efficiency

    else:
        tank_capacity = safe_float(form_data.get("tank_capacity"))
        mileage = safe_float(form_data.get("mileage"))
        fuel_percent = safe_float(form_data.get("fuel_percent"))
        battery_percent = safe_float(form_data.get("battery_percent"))

        if (
            tank_capacity is None or tank_capacity <= 0
            or mileage is None or mileage <= 0
            or fuel_percent is None
            or not 0 <= fuel_percent <= 100
            or battery_percent is None
            or not 0 <= battery_percent <= 100
        ):
            raise ValueError("Invalid Hybrid inputs.")

        # Assumption: hybrid battery provides 150 km at 100%.
        full_fuel_range = tank_capacity * mileage
        full_battery_range = 150.0
        max_range = full_fuel_range + full_battery_range

        # Convert the two energy percentages into one equivalent
        # percentage because the current C++ interface accepts one.
        current_percent = (
            full_fuel_range * fuel_percent
            + full_battery_range * battery_percent
        ) / max_range

    result = subprocess.run(
        [
            CPP_EXE,
            cpp_types[vehicle_type],
            str(max_range),
            str(current_percent),
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
        raise RuntimeError(
            error_output or output or "C++ engine failed."
        )

    match = re.search(
        r"Usable\s+Range:\s*([-+]?\d+(?:\.\d+)?)\s*km",
        output,
        re.IGNORECASE,
    )

    if not match:
        raise RuntimeError(
            "Could not read usable range from C++ output: "
            + (output or error_output or "No output received.")
        )

    return float(match.group(1)), output



# ============================================================
# TOMTOM TEST ROUTE
# ============================================================

@app.route("/test-tomtom")
def test_tomtom():
    if not TOMTOM_API_KEY:
        return jsonify({
            "success": False,
            "message": "TOMTOM_API_KEY is missing from 1.env.",
        }), 500

    try:
        stations = get_tomtom_fuel_stations(
            DEFAULT_LATITUDE,
            DEFAULT_LONGITUDE,
        )

        return jsonify({
            "success": True,
            "message": "TomTom API connection successful.",
            "station_count": len(stations),
            "stations": stations,
        })

    except requests.RequestException as exc:
        app.logger.exception("TomTom request failed")
        return jsonify({
            "success": False,
            "message": f"TomTom request failed: {exc}",
        }), 502

    except Exception as exc:
        app.logger.exception("TomTom test failed")
        return jsonify({
            "success": False,
            "message": str(exc),
        }), 500


# ============================================================
# FUEL STATION ROUTES
# ============================================================

@app.route("/test-fuel")
def test_fuel():
    try:
        stations = get_tomtom_fuel_stations(
            DEFAULT_LATITUDE,
            DEFAULT_LONGITUDE,
        )

        return jsonify({
            "success": True,
            "count": len(stations),
            "stations": stations,
        })

    except Exception as exc:
        app.logger.exception("Fuel station test failed")
        return jsonify({
            "success": False,
            "message": str(exc),
        }), 500


@app.route("/fuel-stations")
def fuel_stations():
    latitude = safe_float(request.args.get("lat")) or DEFAULT_LATITUDE
    longitude = safe_float(request.args.get("lon")) or DEFAULT_LONGITUDE

    try:
        stations = get_tomtom_fuel_stations(latitude, longitude)

        return jsonify({
            "success": True,
            "stations": stations,
        })

    except Exception as exc:
        app.logger.exception("Fuel station lookup failed")
        return jsonify({
            "success": False,
            "message": str(exc),
            "stations": [],
        }), 500


# ============================================================
# CHARGING STATION ROUTE
# ============================================================

@app.route("/charging-stations")
def charging_stations():
    city = request.args.get("city", DEFAULT_CITY).strip() or DEFAULT_CITY

    stations, db_error = get_stations_safely(city)

    if db_error:
        return jsonify({
            "success": False,
            "message": "Could not retrieve charging stations from MySQL.",
            "stations": [],
        }), 500

    return jsonify({
        "success": True,
        "count": len(stations),
        "stations": stations,
    })


# ============================================================
# HOME PAGE
# ============================================================



@app.route("/", methods=["GET", "POST"])
def index():
    selected_vehicle = ""
    vehicle_model = ""
    safe_range = None
    range_status = None
    errors = []
    stations = []
    engine_output = ""
    station_error = None
    form_data = {}
    show_energy = False

   
    if request.method == "GET":
        selected_vehicle = (
            request.args.get("vehicle_type", "").strip().upper()
        )

        allowed_vehicles = {"PETROL", "DIESEL", "EV", "HYBRID"}

        if selected_vehicle not in allowed_vehicles:
            selected_vehicle = ""

        # Load EV stations only when the TomTom API key exists.
        if selected_vehicle == "EV" and TOMTOM_API_KEY:
            try:
                stations = get_tomtom_ev_stations(
                    DEFAULT_LATITUDE,
                    DEFAULT_LONGITUDE,
                )
            except Exception:
                app.logger.exception("EV station lookup failed")
                station_error = (
                    "Unable to retrieve EV charging stations."
                )

        elif selected_vehicle == "EV":
            station_error = (
                "EV stations unavailable: TomTom API key "
                "is not configured. Energy Status can still "
                "be calculated."
            )

    
     

    else:
        form_data = request.form.to_dict()

        selected_vehicle = (
            form_data.get("vehicle_type", "").strip().upper()
        )
        vehicle_model = form_data.get("vehicle_model", "").strip()

        errors = validate_data(selected_vehicle, form_data)

        # Read coordinates supplied by your location JavaScript.
        latitude = safe_float(form_data.get("latitude"))
        longitude = safe_float(form_data.get("longitude"))

        # Fall back to Dehradun if no coordinates were supplied.
        if latitude is None or longitude is None:
            latitude = DEFAULT_LATITUDE
            longitude = DEFAULT_LONGITUDE

        if not errors:
            try:
                # C++ calculates the usable vehicle range.
                safe_range, engine_output = calculate_cpp_safe_range(
                    selected_vehicle,
                    form_data,
                )
                show_energy = True 

                if safe_range >= 80:
                    range_status = "Normal"
                elif safe_range >= 30:
                    range_status = "Low"
                else:
                    range_status = "Critical"

                # Petrol and Diesel: retrieve nearby fuel stations from TomTom.
                if selected_vehicle in ("PETROL", "DIESEL"):
                    stations = get_tomtom_fuel_stations(
                        latitude,
                        longitude,
                    )

                
                
# EV: retrieve charging stations from TomTom.
                elif selected_vehicle == "EV":
                   stations = get_tomtom_ev_stations(
                        latitude,
                        longitude,
                    )

# Hybrid: retrieve both types from TomTom.
                elif selected_vehicle == "HYBRID":
                   fuel_stations = get_tomtom_fuel_stations(
                        latitude,
                        longitude,
                    )

                   ev_stations = get_tomtom_ev_stations(
                          latitude,
                        longitude,
                            )

                   stations = fuel_stations + ev_stations


            except (ValueError, FileNotFoundError, RuntimeError) as exc:
                app.logger.exception("Vehicle processing failed")
                errors.append(str(exc))

            except Exception as exc:
                app.logger.exception("Unexpected application error")
                errors.append(
                    "Unable to retrieve vehicle or station information. "
                    "Check the Flask terminal."
                )

    return render_template(
        "index.html",
        selected_vehicle=selected_vehicle,
        vehicle_model=vehicle_model,
        safe_range=safe_range,
        range_status=range_status,
        show_energy=show_energy,
        errors=errors,
        stations=stations,
        station_error=station_error,
        engine_output=engine_output,
        form_data=form_data,
        data=form_data,
    )




# ============================================================
# START FLASK
# ============================================================

if __name__ == "__main__":
    app.run(debug=True)
