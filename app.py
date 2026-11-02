import os
import re
import subprocess
from math import radians, sin, cos, sqrt, atan2

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, redirect, url_for

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__)

HARDCODED_API_KEY = "KAPybFJvNpPrXre1o4F2dy7ywR0IYTtB"
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY") or HARDCODED_API_KEY
TOMTOM_MAP_KEY = os.getenv("TOMTOM_MAP_KEY") or HARDCODED_API_KEY

DEFAULT_LATITUDE = 30.3165
DEFAULT_LONGITUDE = 78.0322

class CppEngineBridge:
    def __init__(self, backend_dir):
        self.backend_dir = backend_dir
        self.exe_path = os.path.join(
            backend_dir, 
            "RouteWiseEngine.exe" if os.name == 'nt' else "RouteWiseEngine"
        )

    def calculate_safe_range(self, vehicle_type, form_data):
        if not os.path.isfile(self.exe_path):
            raise FileNotFoundError(f"C++ binary missing at '{self.exe_path}'.")

        vehicle_type = vehicle_type.strip().upper()
        percent = self._safe_float(form_data.get("battery_percent" if vehicle_type in ("EV", "HYBRID") else "fuel_percent")) or 0.0
        capacity = self._safe_float(form_data.get("battery_capacity" if vehicle_type == "EV" else "tank_capacity")) or 0.0
        efficiency = self._safe_float(form_data.get("efficiency" if vehicle_type == "EV" else "mileage")) or 0.0
        connector = form_data.get("connector", "Type-2") if vehicle_type in ("EV", "HYBRID") else "None"

        result = subprocess.run(
            [self.exe_path, vehicle_type, str(percent), str(capacity), str(efficiency), str(connector)],
            cwd=self.backend_dir,
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )

        output = (result.stdout or "").strip()
        match = re.search(r"Calculated\s+Safe\s+Usable\s+Range:\s*([-+]?\d+(?:\.\d+)?)\s*km", output, re.IGNORECASE)
        if not match:
            match = re.search(r"Usable\s+Range:\s*([-+]?\d+(?:\.\d+)?)\s*km", output, re.IGNORECASE)

        if not match:
            raise RuntimeError("Could not parse usable range from C++ binary output.")

        return float(match.group(1)), output

    @staticmethod
    def _safe_float(value):
        try:
            return float(value) if value is not None and str(value).strip() != "" else None
        except (TypeError, ValueError):
            return None


class TomTomService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.session = requests.Session()

    def get_fuel_stations(self, latitude, longitude, radius_km=10):
        url = "https://api.tomtom.com/search/2/poiSearch/fuel.json"
        response = self.session.get(url, params={
            "key": self.api_key, "lat": latitude, "lon": longitude,
            "radius": int(min(max(radius_km, 0.1), 50) * 1000), "limit": 20, "countrySet": "IN"
        }, timeout=8)
        response.raise_for_status()

        return [{
            "name": item.get("poi", {}).get("name", "Unknown fuel station"),
            "address": item.get("address", {}).get("freeformAddress", ""),
            "latitude": item.get("position", {}).get("lat"),
            "longitude": item.get("position", {}).get("lon"),
            "station_type": "Fuel"
        } for item in response.json().get("results", [])]

    def get_ev_stations(self, latitude, longitude, radius_km=10):
        url = "https://api.tomtom.com/search/2/poiSearch/electric%20vehicle%20charging%20station.json"
        response = self.session.get(url, params={
            "key": self.api_key, "lat": latitude, "lon": longitude,
            "radius": int(min(max(radius_km, 0.1), 50) * 1000), "limit": 20, "countrySet": "IN"
        }, timeout=8)
        response.raise_for_status()

        return [{
            "name": item.get("poi", {}).get("name", "Unknown charging station"),
            "address": item.get("address", {}).get("freeformAddress", ""),
            "latitude": item.get("position", {}).get("lat"),
            "longitude": item.get("position", {}).get("lon"),
            "station_type": "EV Charging"
        } for item in response.json().get("results", [])]

    def calculate_traffic_route(self, origin_lat, origin_lon, dest_lat, dest_lon):
        locations = f"{origin_lat},{origin_lon}:{dest_lat},{dest_lon}"
        url = f"https://api.tomtom.com/routing/1/calculateRoute/{locations}/json"
        
        response = self.session.get(url, params={
            "key": self.api_key, 
            "travelMode": "car", 
            "routeType": "fastest",
            "traffic": "true",
            "routeRepresentation": "polyline"
        }, timeout=10)
        response.raise_for_status()
        
        routes = response.json().get("routes", [])
        if not routes:
            return None

        route = routes[0]
        summary = route.get("summary", {})
        points = [{"lat": p["latitude"], "lon": p["longitude"]} for leg in route.get("legs", []) for p in leg.get("points", [])]

        return {
            "distance_km": round(summary.get("lengthInMeters", 0) / 1000, 2),
            "travel_time_minutes": round(summary.get("travelTimeInSeconds", 0) / 60),
            "traffic_delay_minutes": round(summary.get("trafficDelayInSeconds", 0) / 60),
            "points": points
        }


cpp_engine = CppEngineBridge(os.path.join(BASE_DIR, "backend"))
tomtom_service = TomTomService(TOMTOM_API_KEY)

@app.route("/")
def home():
    # Primary landing route
    return render_template("home.html")

@app.route("/app", methods=["GET", "POST"])
def index():
    selected_vehicle, vehicle_model, data, errors = "", "", {}, []
    success, safe_range, active_tab, cpp_route_data = False, None, "vehicle", None

    if request.method == "GET":
        selected_vehicle = request.args.get("vehicle_type", "").strip().upper()

    if request.method == "POST":
        data = request.form.to_dict()
        selected_vehicle = data.get("vehicle_type", "").strip().upper()
        vehicle_model = data.get("vehicle_model", "").strip()

        try:
            safe_range, cpp_output = cpp_engine.calculate_safe_range(selected_vehicle, data)
            success = True
            active_tab = "dashboard"
            cpp_route_data = {"safe_range": safe_range, "cpp_output": cpp_output}
        except Exception as exc:
            errors.append(str(exc))

    return render_template(
        "index.html",
        selected_vehicle=selected_vehicle,
        vehicle_model=vehicle_model,
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
    vehicle_type = request.args.get("vehicle_type", "").strip().upper()
    lat = float(request.args.get("lat") or DEFAULT_LATITUDE)
    lon = float(request.args.get("lon") or DEFAULT_LONGITUDE)
    range_km = float(request.args.get("range_km") or 50)

    try:
        stations = []
        if vehicle_type in ("PETROL", "DIESEL", "HYBRID"):
            stations.extend(tomtom_service.get_fuel_stations(lat, lon, range_km))

        if vehicle_type in ("EV", "HYBRID"):
            stations.extend(tomtom_service.get_ev_stations(lat, lon, range_km))

        evaluated_stations = []
        for st in stations[:10]:
            route_info = tomtom_service.calculate_traffic_route(lat, lon, st["latitude"], st["longitude"])
            if route_info and route_info["distance_km"] <= range_km:
                st["distance_km"] = route_info["distance_km"]
                st["travel_time_minutes"] = route_info["travel_time_minutes"]
                st["traffic_delay_minutes"] = route_info["traffic_delay_minutes"]
                evaluated_stations.append(st)

        evaluated_stations.sort(key=lambda s: (s["travel_time_minutes"], s["distance_km"]))
        top_5 = evaluated_stations[:5]

        return jsonify({
            "success": True,
            "vehicle_type": vehicle_type,
            "range_km": range_km,
            "count": len(top_5),
            "stations": top_5
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

        route_data = tomtom_service.calculate_traffic_route(origin_lat, origin_lon, dest_lat, dest_lon)
        if not route_data:
            return jsonify({"success": False, "message": "No route found."}), 502

        route_data["success"] = True
        return jsonify(route_data)
    except Exception as exc:
        return jsonify({"success": False, "message": str(exc)}), 502

if __name__ == "__main__":
    app.run(debug=True)