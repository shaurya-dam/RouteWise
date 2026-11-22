import os
import re
import random
import subprocess
from math import radians, sin, cos, sqrt, atan2

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

import routing  # apna A* routing (routing.py)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, "my.env"))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

app = Flask(__name__)


def _clean(val):
    return (val or "").strip().strip('"').strip("'")


def _load_api_key():
    # Sirf known variable names use karo (random 16+ char value ko key nahi maanna)
    for var_name in ("TOMTOM_API_KEY", "TOMTOM_MAP_KEY", "API_KEY", "TOMTOM_KEY", "KEY"):
        val = _clean(os.getenv(var_name))
        if val:
            return val
    return ""


TOMTOM_API_KEY = _load_api_key()
TOMTOM_MAP_KEY = _clean(os.getenv("TOMTOM_MAP_KEY")) or TOMTOM_API_KEY

DEFAULT_LATITUDE = 30.3165
DEFAULT_LONGITUDE = 78.0322

BUFFER_FACTORS = {"EV": 0.80, "HYBRID": 0.85}  # baaki (PETROL/DIESEL) = 0.90, C++ ke same


def _haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return r * 2 * atan2(sqrt(a), sqrt(1 - a))


class CppEngineBridge:
    def __init__(self, backend_dir):
        self.backend_dir = backend_dir
        self.exe_path = os.path.join(
            backend_dir,
            "RouteWiseEngine.exe" if os.name == "nt" else "RouteWiseEngine"
        )

    def calculate_safe_range(self, vehicle_type, form_data):
        vehicle_type = vehicle_type.strip().upper()
        percent = self._safe_float(
            form_data.get("battery_percent" if vehicle_type in ("EV", "HYBRID") else "fuel_percent")
        ) or 85.0
        capacity = self._safe_float(
            form_data.get("battery_capacity" if vehicle_type == "EV" else "tank_capacity")
        ) or 40.0
        efficiency = self._safe_float(
            form_data.get("efficiency" if vehicle_type == "EV" else "mileage")
        ) or 6.0
        connector = form_data.get("connector", "Type-2") if vehicle_type in ("EV", "HYBRID") else "None"

        try:
            if not os.path.isfile(self.exe_path):
                raise FileNotFoundError("C++ binary not found.")

            if os.name != "nt" and not os.access(self.exe_path, os.X_OK):
                os.chmod(self.exe_path, 0o755)

            result = subprocess.run(
                [self.exe_path, vehicle_type, str(percent), str(capacity), str(efficiency), str(connector)],
                cwd=self.backend_dir,
                capture_output=True,
                text=True,
                timeout=3,
                check=False
            )

            output = (result.stdout or "").strip()
            match = re.search(r"Calculated\s+Safe\s+Usable\s+Range:\s*([-+]?\d+(?:\.\d+)?)\s*km", output, re.IGNORECASE)
            if not match:
                match = re.search(r"Usable\s+Range:\s*([-+]?\d+(?:\.\d+)?)\s*km", output, re.IGNORECASE)

            if match:
                return float(match.group(1)), output
        except (OSError, subprocess.SubprocessError):
            pass

        # Python fallback (C++ binary na mile to) - buffer C++ jaisa hi
        buffer_factor = BUFFER_FACTORS.get(vehicle_type, 0.90)
        safe_range = round(((percent / 100.0) * capacity * efficiency) * buffer_factor, 2)
        fallback_output = f"Calculated Safe Usable Range: {safe_range} km"
        return safe_range, fallback_output

    @staticmethod
    def _safe_float(value):
        try:
            return float(value) if value is not None and str(value).strip() != "" else None
        except (TypeError, ValueError):
            return None


class RoutingAndStationService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "RouteWiseApp/1.0"})

    def get_stations(self, vehicle_type, latitude, longitude, radius_km=15):
        stations = []
        if self.api_key:
            try:
                if vehicle_type in ("PETROL", "DIESEL", "HYBRID"):
                    stations.extend(self._tomtom_poi("fuel", "Fuel", latitude, longitude, radius_km))
                if vehicle_type in ("EV", "HYBRID"):
                    stations.extend(self._tomtom_poi("electric vehicle charging station", "EV Charging", latitude, longitude, radius_km))
            except Exception:
                stations = []

        if not stations:
            try:
                stations = self._osm_overpass_stations(vehicle_type, latitude, longitude, radius_km)
            except Exception:
                stations = []

        stations.sort(key=lambda s: _haversine_km(latitude, longitude, s["latitude"], s["longitude"]))
        return stations

    def _tomtom_poi(self, query, station_type, latitude, longitude, radius_km):
        url = f"https://api.tomtom.com/search/2/poiSearch/{requests.utils.quote(query)}.json"
        response = self.session.get(
            url,
            params={
                "key": self.api_key,
                "lat": latitude,
                "lon": longitude,
                "radius": int(min(max(radius_km, 0.1), 50) * 1000),
                "limit": 15,
                "countrySet": "IN"
            },
            timeout=8
        )
        if response.status_code in (401, 403):
            self.api_key = ""   # key galat/expired: aage se TomTom skip, free OSM/OSRM use hoga
            raise RuntimeError("TomTom API key invalid")
        response.raise_for_status()

        results = []
        for item in response.json().get("results", []):
            pos = item.get("position", {})
            if pos.get("lat") is not None and pos.get("lon") is not None:
                results.append({
                    "name": item.get("poi", {}).get("name", f"{station_type} Station"),
                    "address": item.get("address", {}).get("freeformAddress", ""),
                    "latitude": pos["lat"],
                    "longitude": pos["lon"],
                    "station_type": station_type
                })
        return results

    def _osm_overpass_stations(self, vehicle_type, latitude, longitude, radius_km):
        radius_m = int(min(max(radius_km, 1), 25) * 1000)
        filters = []
        if vehicle_type in ("PETROL", "DIESEL", "HYBRID"):
            filters.append(f'node["amenity"="fuel"](around:{radius_m},{latitude},{longitude});')
            filters.append(f'way["amenity"="fuel"](around:{radius_m},{latitude},{longitude});')
        if vehicle_type in ("EV", "HYBRID"):
            filters.append(f'node["amenity"="charging_station"](around:{radius_m},{latitude},{longitude});')
            filters.append(f'way["amenity"="charging_station"](around:{radius_m},{latitude},{longitude});')

        if not filters:
            return []

        query = f"[out:json][timeout:10];({''.join(filters)});out center 15;"
        response = self.session.post("https://overpass-api.de/api/interpreter", data={"data": query}, timeout=12)
        response.raise_for_status()

        results = []
        for el in response.json().get("elements", []):
            tags = el.get("tags", {})
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
            if lat is None or lon is None:
                continue

            amenity = tags.get("amenity", "")
            default_name = "EV Charging Station" if amenity == "charging_station" else "Fuel Station"
            name = tags.get("name") or tags.get("brand") or tags.get("operator") or default_name
            addr_parts = [tags.get("addr:street"), tags.get("addr:suburb"), tags.get("addr:city")]
            address = ", ".join([p for p in addr_parts if p]) or "Nearby Road Station"

            results.append({
                "name": name,
                "address": address,
                "latitude": float(lat),
                "longitude": float(lon),
                "station_type": "EV Charging" if amenity == "charging_station" else "Fuel"
            })
        return results


cpp_engine = CppEngineBridge(os.path.join(BASE_DIR, "backend"))
station_service = RoutingAndStationService(TOMTOM_API_KEY)   # sirf station (POI) dhundne ke liye


def _evaluate_station(graph, lat, lon, st):
    """Apne A* se route nikalo; na mile to straight-line estimate."""
    info = None
    if graph is not None:
        try:
            info = routing.find_route(graph, lat, lon, st["latitude"], st["longitude"])
        except Exception:
            info = None

    if info:
        st["distance_km"] = info["distance_km"]
        st["travel_time_minutes"] = info["travel_time_minutes"]
        st["traffic_delay_minutes"] = info["traffic_delay_minutes"]
        st["route_source"] = "A*"
    else:
        d = round(_haversine_km(lat, lon, st["latitude"], st["longitude"]) * 1.3, 2)
        st["distance_km"] = d
        st["travel_time_minutes"] = max(1, round(d / 30 * 60))
        st["traffic_delay_minutes"] = 0
        st["route_source"] = "estimate"
    return st


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/app", methods=["GET", "POST"])
def index():
    selected_vehicle, data, errors = "EV", {}, []
    success, safe_range, active_tab, cpp_route_data = False, None, "vehicle", None

    if request.method == "GET":
        selected_vehicle = request.args.get("vehicle_type", "EV").strip().upper() or "EV"

    if request.method == "POST":
        data = request.form.to_dict()
        selected_vehicle = data.get("vehicle_type", "EV").strip().upper() or "EV"

        random_percent = random.randint(72, 92)

        if selected_vehicle in ("EV", "HYBRID"):
            data["battery_percent"] = str(random_percent)
            data["battery_capacity"] = "42"
            data["efficiency"] = "6.2"
        if selected_vehicle in ("PETROL", "DIESEL", "HYBRID"):
            data["fuel_percent"] = str(random_percent)
            data["tank_capacity"] = "45"
            data["mileage"] = "16.5"

        try:
            safe_range, cpp_output = cpp_engine.calculate_safe_range(selected_vehicle, data)
            success = True
            active_tab = "dashboard"
            cpp_route_data = {
                "safe_range": safe_range,
                "cpp_output": cpp_output,
                "battery_percent": random_percent
            }
        except Exception as exc:
            errors.append(str(exc))

    return render_template(
        "index.html",
        selected_vehicle=selected_vehicle,
        data=data,
        errors=errors,
        success=success,
        safe_range=safe_range,
        show_energy=success,
        active_tab=active_tab,
        tomtom_map_key=TOMTOM_MAP_KEY,
        cpp_route_data=cpp_route_data
    )


@app.route("/station-recommendations")
def station_recommendations():
    vehicle_type = request.args.get("vehicle_type", "EV").strip().upper() or "EV"

    try:
        lat = float(request.args.get("lat") or DEFAULT_LATITUDE)
        lon = float(request.args.get("lon") or DEFAULT_LONGITUDE)
        stations = station_service.get_stations(vehicle_type, lat, lon, radius_km=15)[:5]

        # Ek hi road graph origin + saare stations ke liye, phir har station par A*
        graph = None
        if stations:
            points = [(lat, lon)] + [(s["latitude"], s["longitude"]) for s in stations]
            try:
                graph = routing.get_graph(points)
            except Exception:
                graph = None

        evaluated = [_evaluate_station(graph, lat, lon, s) for s in stations]
        evaluated.sort(key=lambda s: (s["distance_km"], s["travel_time_minutes"]))

        return jsonify({
            "success": True,
            "vehicle_type": vehicle_type,
            "count": len(evaluated),
            "stations": evaluated
        })
    except Exception as exc:
        return jsonify({"success": False, "message": str(exc), "stations": []}), 502


@app.route("/calculate-route", methods=["GET"])
def calculate_route():
    try:
        origin_lat = float(request.args.get("origin_lat"))
        origin_lon = float(request.args.get("origin_lon"))
        dest_lat = float(request.args.get("dest_lat"))
        dest_lon = float(request.args.get("dest_lon"))

        graph = routing.get_graph([(origin_lat, origin_lon), (dest_lat, dest_lon)])
        route_data = routing.find_route(graph, origin_lat, origin_lon, dest_lat, dest_lon)
        if not route_data:
            return jsonify({"success": False, "message": "No route found."}), 502

        route_data["success"] = True
        return jsonify(route_data)
    except Exception as exc:
        return jsonify({"success": False, "message": str(exc)}), 502


if __name__ == "__main__":
    app.run(debug=True)