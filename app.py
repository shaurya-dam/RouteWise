from flask import Flask, render_template, request
from dotenv import load_dotenv
import os
import requests
from db import get_available_charging_stations
import mysql.connector

app = Flask(__name__)

load_dotenv()

TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY")
# ============================================================
# SAFE RANGE
# ============================================================

def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def calculate_safe_range(vehicle_type, form_data):

    if vehicle_type in ["PETROL"]:

        fuel_percent = safe_float(
            form_data.get("fuel_percent")
        )

        tank_capacity = safe_float(
            form_data.get("tank_capacity")
        )

        mileage = safe_float(
            form_data.get("mileage")
        )

        if None in [
            fuel_percent,
            tank_capacity,
            mileage
        ]:
            return None

        return (
            fuel_percent / 100
            * tank_capacity
            * mileage
            * 0.85
        )


    if vehicle_type == "EV":

        battery_percent = safe_float(
            form_data.get("battery_percent")
        )

        battery_capacity = safe_float(
            form_data.get("battery_capacity")
        )

        efficiency = safe_float(
            form_data.get("efficiency")
        )

        if None in [
            battery_percent,
            battery_capacity,
            efficiency
        ]:
            return None

        return (
            battery_percent / 100
            * battery_capacity
            * efficiency
            * 0.80
        )


    if vehicle_type == "HYBRID":

        fuel_percent = safe_float(
            form_data.get("fuel_percent")
        )

        tank_capacity = safe_float(
            form_data.get("tank_capacity")
        )

        mileage = safe_float(
            form_data.get("mileage")
        )

        battery_percent = safe_float(
            form_data.get("battery_percent")
        )

        if None in [
            fuel_percent,
            tank_capacity,
            mileage,
            battery_percent
        ]:
            return None

        fuel_range = (
            fuel_percent / 100
            * tank_capacity
            * mileage
            * 0.85
        )

        # Demo hybrid electric contribution
        electric_range = (
            battery_percent / 100
            * 25
            * 6
            * 0.80
        )

        return fuel_range + electric_range

    return None


# ============================================================
# VALIDATION
# ============================================================

def validate_data(vehicle_type, form_data):

    errors = []

   

    # Vehicle model validation
    vehicle_model = form_data.get("vehicle_model", "").strip()

    if not vehicle_model:
        errors.append("Vehicle model is required.")

    allowed_types = ["PETROL", "EV", "HYBRID"]

    if vehicle_type not in allowed_types:
        errors.append("Please select a valid vehicle type.")
        return errors
    # --------------------------------------------------------
    # VEHICLE TYPE
    # --------------------------------------------------------

    allowed_types = [
        "PETROL",
        "DIESEL",
        "EV",
        "HYBRID"
    ]

    if vehicle_type not in allowed_types:

        errors.append(
            "Please select a valid vehicle type."
        )

        return errors


    # --------------------------------------------------------
    # PETROL / DIESEL
    # --------------------------------------------------------

    if vehicle_type in ["PETROL", "DIESEL"]:

        fields = [
            "fuel_percent",
            "tank_capacity",
            "mileage"
        ]

        for field in fields:

            if not form_data.get(field, "").strip():

                errors.append(
                    f"{field.replace('_', ' ').title()} is required."
                )


        if errors:
            return errors


        fuel = safe_float(
            form_data.get("fuel_percent")
        )

        tank = safe_float(
            form_data.get("tank_capacity")
        )

        mileage = safe_float(
            form_data.get("mileage")
        )


        if fuel is None:
            errors.append(
                "Fuel level must be numeric."
            )

        elif fuel < 0 or fuel > 100:
            errors.append(
                "Fuel level must be between 0 and 100%."
            )


        if tank is None:
            errors.append(
                "Tank capacity must be numeric."
            )

        elif tank <= 0:
            errors.append(
                "Tank capacity must be greater than 0."
            )


        if mileage is None:
            errors.append(
                "Mileage must be numeric."
            )

        elif mileage <= 0:
            errors.append(
                "Mileage must be greater than 0."
            )


    # --------------------------------------------------------
    # EV
    # --------------------------------------------------------

    elif vehicle_type == "EV":

        fields = [
            "battery_percent",
            "battery_capacity",
            "efficiency",
            "connector"
        ]

        for field in fields:

            if not form_data.get(field, "").strip():

                errors.append(
                    f"{field.replace('_', ' ').title()} is required."
                )


        if errors:
            return errors


        battery = safe_float(
            form_data.get("battery_percent")
        )

        capacity = safe_float(
            form_data.get("battery_capacity")
        )

        efficiency = safe_float(
            form_data.get("efficiency")
        )


        if battery is None:
            errors.append(
                "Battery level must be numeric."
            )

        elif battery < 0 or battery > 100:
            errors.append(
                "Battery level must be between 0 and 100%."
            )


        if capacity is None:
            errors.append(
                "Battery capacity must be numeric."
            )

        elif capacity <= 0:
            errors.append(
                "Battery capacity must be greater than 0."
            )


        if efficiency is None:
            errors.append(
                "Efficiency must be numeric."
            )

        elif efficiency <= 0:
            errors.append(
                "Efficiency must be greater than 0."
            )


    # --------------------------------------------------------
    # HYBRID
    # --------------------------------------------------------

    elif vehicle_type == "HYBRID":

        fields = [
            "fuel_percent",
            "tank_capacity",
            "mileage",
            "battery_percent"
        ]

        for field in fields:

            if not form_data.get(field, "").strip():

                errors.append(
                    f"{field.replace('_', ' ').title()} is required."
                )


        if errors:
            return errors


        fuel = safe_float(
            form_data.get("fuel_percent")
        )

        tank = safe_float(
            form_data.get("tank_capacity")
        )

        mileage = safe_float(
            form_data.get("mileage")
        )

        battery = safe_float(
            form_data.get("battery_percent")
        )


        if fuel is None:
            errors.append(
                "Fuel level must be numeric."
            )

        elif fuel < 0 or fuel > 100:
            errors.append(
                "Fuel level must be between 0 and 100%."
            )


        if tank is None or tank <= 0:
            errors.append(
                "Tank capacity must be greater than 0."
            )


        if mileage is None or mileage <= 0:
            errors.append(
                "Mileage must be greater than 0."
            )


        if battery is None:
            errors.append(
                "Battery level must be numeric."
            )

        elif battery < 0 or battery > 100:
            errors.append(
                "Battery level must be between 0 and 100%."
            )


    # --------------------------------------------------------
    # LOCATION
    # --------------------------------------------------------

    # latitude = form_data.get(
    #     "latitude",
    #     ""
    # ).strip()

    # longitude = form_data.get(
    #     "longitude",
    #     ""
    # ).strip()


    # if not latitude:

    #     errors.append(
    #         "Latitude is required."
    #     )

    # else:

    #     lat = safe_float(latitude)

    #     if lat is None:

    #         errors.append(
    #             "Latitude must be numeric."
    #         )

    #     elif lat < -90 or lat > 90:

    #         errors.append(
    #             "Latitude must be between -90 and 90."
    #         )


    # if not longitude:

    #     errors.append(
    #         "Longitude is required."
    #     )

    # else:

    #     lng = safe_float(longitude)

    #     if lng is None:

    #         errors.append(
    #             "Longitude must be numeric."
    #         )

    #     elif lng < -180 or lng > 180:

    #         errors.append(
    #             "Longitude must be between -180 and 180."
    #         )


    # return errors



     


# ============================================================
# HOME
# ============================================================

@app.route("/test-tomtom")
def test_tomtom():

    url = "https://api.tomtom.com/search/2/search/EV%20charging.json"

    params = {
        "key": TOMTOM_API_KEY,
        "lat": 30.3165,
        "lon": 78.0322,
        "radius": 5000
    }

    response = requests.get(url, params=params)

    print("TomTom Status:", response.status_code)
    print("TomTom Response:", response.text)

    return response.text

@app.route("/", methods=["GET", "POST"])
def index():

    selected_vehicle = ""

    data = {}

    errors = []

    stations = []

    success = False

    safe_range = None

    range_status = None


    # ========================================================
    # GET
    # ========================================================

    if request.method == "GET":

        selected_vehicle = (
            request.args.get(
                "vehicle_type",
                ""
            ).upper()
        )

        # data = {
        #     "latitude":
        #         DEFAULT_LATITUDE,

        #     "longitude":
        #         DEFAULT_LONGITUDE
        # }


    # ========================================================
    # POST
    # ========================================================

    if request.method == "POST":

        data = request.form.to_dict()

        selected_vehicle = (
            data.get(
                "vehicle_type",
                ""
            ).upper()
        )
        if selected_vehicle == "EV":
               try:
                   stations = get_available_charging_stations()
               except Exception:
                   app.logger.exception("Unable to retrieve charging stations")
                   errors.append("Unable to load charging stations.")
                   success = False


        # ----------------------------------------------------
        # VALIDATE
        # ----------------------------------------------------

        errors = validate_data(
            selected_vehicle,
            data
        )


        # ----------------------------------------------------
        # CALCULATE
        # ----------------------------------------------------

        if not errors:

            safe_range = calculate_safe_range(
                selected_vehicle,
                data
            )


            if safe_range is None:

                errors.append(
                    "Unable to calculate safe range."
                )

            else:

                success = True


                if safe_range >= 80:

                    range_status = "Normal"

                elif safe_range >= 30:

                    range_status = "Low"

                else:

                    range_status = "Critical"


    return render_template(
        "index.html",

        selected_vehicle=selected_vehicle,

        data=data,

        errors=errors,

        success=success,

        safe_range=safe_range,

        range_status=range_status,

        # default_latitude=DEFAULT_LATITUDE,

        # default_longitude=DEFAULT_LONGITUDE
        stations=stations
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )