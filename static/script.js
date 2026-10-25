const locationBtn = document.getElementById("locationBtn");
const addressBtn = document.getElementById("addressBtn");

const locationName = document.getElementById("locationName");
const locationStatus = document.getElementById("locationStatus");

const latitudeInput = document.getElementById("latitude");
const longitudeInput = document.getElementById("longitude");

if (
    locationBtn && addressBtn &&
    locationName && locationStatus &&
    latitudeInput && longitudeInput
) {

    function showLocationMessage(name, status) {
        if (locationName) locationName.textContent = name;
        if (locationStatus) locationStatus.textContent = status;
    }

    // USE CURRENT LOCATION
    if (locationBtn) {
        locationBtn.addEventListener("click", function () {
            if (!navigator.geolocation) {
                showLocationMessage(
                    "Location not supported",
                    "Your browser does not support location detection."
                );
                return;
            }

            showLocationMessage(
                "Detecting location...",
                "Please allow location access in your browser."
            );

            navigator.geolocation.getCurrentPosition(
                async function (position) {
                    const latitude = position.coords.latitude;
                    const longitude = position.coords.longitude;

                    if (latitudeInput) latitudeInput.value = latitude;
                    if (longitudeInput) longitudeInput.value = longitude;

                    try {
                        const response = await fetch(
                            `https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}&zoom=18&addressdetails=1`,
                            {
                                headers: {
                                    "User-Agent": "MyWebGISApp/1.0" // Nominatim requires a valid user-agent header
                                }
                            }
                        );

                        if (!response.ok) {
                            throw new Error("Address lookup failed");
                        }

                        const result = await response.json();

                        showLocationMessage(
                            result.display_name
                                ? "📍 " + result.display_name
                                : "📍 Current Location",
                            "Current location detected successfully."
                        );
                    } catch (error) {
                        showLocationMessage(
                            "📍 Current Location",
                            "Location detected, but address could not be loaded."
                        );
                    }

                    locationBtn.textContent = "✓ Current Location Selected";
                },
                function (error) {
                    console.error(error);
                    showLocationMessage(
                        "Location not detected",
                        "Please allow location access and try again."
                    );
                },
                {
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 0
                }
            );
        });
    }

    // SEARCH MANUAL ADDRESS
    if (addressBtn) {
        addressBtn.addEventListener("click", async function () {
            const addressInput = document.getElementById("address");
            const address = addressInput ? addressInput.value.trim() : "";

            if (!address) {
                showLocationMessage(
                    "No address entered",
                    "Please enter an address."
                );
                return;
            }

            showLocationMessage(
                "Searching address...",
                "Finding your location."
            );

            try {
                const response = await fetch(
                    `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(address)}&limit=1`,
                    {
                        headers: {
                            "User-Agent": "MyWebGISApp/1.0"
                        }
                    }
                );

                if (!response.ok) {
                    throw new Error("Address lookup failed");
                }

                const results = await response.json();

                if (!results.length) {
                    showLocationMessage(
                        "Address not found",
                        "Try entering a more specific address."
                    );
                    return;
                }

                const result = results[0];

                if (latitudeInput) latitudeInput.value = result.lat;
                if (longitudeInput) longitudeInput.value = result.lon;

                showLocationMessage(
                    "📍 " + result.display_name,
                    "Address selected successfully."
                );

                addressBtn.textContent = "✓ Address Selected";

            } catch (error) {
                if (locationName) locationName.textContent = "Unable to find address";
                if (locationStatus) locationStatus.textContent = "Please check your internet connection.";
            }
        });
    }
}
// ... aapka existing location code (unchanged) ...


// ============================================================
// TAB SWITCHING
// ============================================================

let routeMap = null;
let routeLine = null;
let originMarker = null;
let destinationMarker = null;

function initializeRouteMap(originLat, originLon) {
    const mapElement = document.getElementById("resultMap");

    if (!mapElement || typeof L === "undefined") {
        throw new Error("Map library or map container is missing.");
    }

    const mapKey = mapElement.dataset.mapKey;

    if (!mapKey) {
        throw new Error("TomTom map display key is missing.");
    }

    if (!routeMap) {
        routeMap = L.map(mapElement).setView(
            [originLat, originLon],
            12
        );

        L.tileLayer(
            `https://{s}.api.tomtom.com/map/1/tile/basic/main/{z}/{x}/{y}.png?key=${encodeURIComponent(mapKey)}`,
            {
                subdomains: ["a", "b", "c", "d"],
                maxZoom: 22,
                attribution: "&copy; TomTom"
            }
        ).addTo(routeMap);
    }

    routeMap.invalidateSize();

    return routeMap;
}

async function calculateAndDisplayRoute(station) {
    const status = document.getElementById("routeStatus");
    const distanceElement = document.getElementById("routeDistance");
    const durationElement = document.getElementById("routeDuration");

    const originLat = Number(
        document.getElementById("latitude")?.value
    );
    const originLon = Number(
        document.getElementById("longitude")?.value
    );

    const destinationLat = Number(station.latitude);
    const destinationLon = Number(station.longitude);

    const validCoordinates =
        Number.isFinite(originLat) &&
        Number.isFinite(originLon) &&
        Number.isFinite(destinationLat) &&
        Number.isFinite(destinationLon) &&
        Math.abs(originLat) <= 90 &&
        Math.abs(destinationLat) <= 90 &&
        Math.abs(originLon) <= 180 &&
        Math.abs(destinationLon) <= 180;

    if (
        !validCoordinates ||
        station.latitude == null ||
        station.longitude == null
    ) {
        if (status) {
            status.textContent =
                "Valid coordinates for your location and station are required.";
        }
        return;
    }

    try {
        const map = initializeRouteMap(originLat, originLon);

        if (status) status.textContent = "Calculating road route…";
        if (distanceElement) distanceElement.textContent = "Calculating…";
        if (durationElement) durationElement.textContent = "Calculating…";

        const params = new URLSearchParams({
            origin_lat: String(originLat),
            origin_lon: String(originLon),
            dest_lat: String(destinationLat),
            dest_lon: String(destinationLon)
        });

        const response = await fetch(
            `/calculate-route?${params.toString()}`
        );

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(
                data.message || "Unable to calculate the route."
            );
        }

        if (!Array.isArray(data.points) || data.points.length < 2) {
            throw new Error("TomTom returned no usable route geometry.");
        }

        // Remove the previous route and markers.
        if (routeLine) map.removeLayer(routeLine);
        if (originMarker) map.removeLayer(originMarker);
        if (destinationMarker) map.removeLayer(destinationMarker);

        originMarker = L.marker([originLat, originLon])
            .addTo(map)
            .bindPopup("Your starting location");

        destinationMarker = L.marker([
            destinationLat,
            destinationLon
        ])
            .addTo(map)
            .bindPopup(
                station.station_name ||
                station.name ||
                "Selected station"
            );

        const routeCoordinates = data.points.map(point => [
            point.lat,
            point.lon
        ]);

        routeLine = L.polyline(routeCoordinates, {
            color: "#325b33",
            weight: 6,
            opacity: 0.85
        }).addTo(map);

        map.fitBounds(routeLine.getBounds(), {
            padding: [35, 35]
        });

        if (distanceElement) {
            distanceElement.textContent =
                `${Number(data.distance_km).toFixed(2)} km`;
        }

        if (durationElement) {
            durationElement.textContent =
                `${data.travel_time_minutes} min`;
        }

        if (status) status.textContent = "Road route calculated successfully.";

        setTimeout(() => map.invalidateSize(), 100);

    } catch (error) {
        console.error("Route calculation error:", error);

        if (status) {
            status.textContent = error.message;
        }

        if (distanceElement) distanceElement.textContent = "Unavailable";
        if (durationElement) durationElement.textContent = "Unavailable";
    }
}


let selectedRouteWiseStation = null;

function selectRouteWiseStation(station, selectedCard) {
    selectedRouteWiseStation = station;

    // Highlight the selected station card
    document.querySelectorAll(".station-card").forEach(card => {
        card.classList.remove("selected-station");
    });

    if (selectedCard) {
        selectedCard.classList.add("selected-station");
    }

    const stationName =
        station.station_name ||
        station.name ||
        station.poi?.name ||
        "Selected Station";

    const stationAddress =
        typeof station.address === "string"
            ? station.address
            : station.address?.freeformAddress ||
              station.poi?.address?.freeformAddress ||
              station.address?.municipality ||
              "Address not available";

    const distance = Number(station.distance_km);
    const stationType = station.station_type || "Station";

    // Update the Result section
    const nameElement = document.getElementById("resultStationName");
    const addressElement = document.getElementById("resultStationAddress");
    const distanceElement = document.getElementById("resultStationDistance");
    const typeElement = document.getElementById("resultStationType");

    if (nameElement) nameElement.textContent = stationName;
    if (addressElement) addressElement.textContent = stationAddress;

    if (distanceElement) {
        distanceElement.textContent = Number.isFinite(distance)
            ? `${distance.toFixed(1)} km`
            : "Distance unavailable";
    }

    if (typeElement) typeElement.textContent = stationType;

    // Open the Result tab and display the road route
   switchTab("result");

setTimeout(() => {
    if (routeMap) {
        routeMap.invalidateSize();
    }

    calculateAndDisplayRoute(station);
}, 250);}


function switchTab(tabName) {
    document.querySelectorAll(".tab-content").forEach(tab => {
        tab.classList.add("hidden");
    });

    const targetTab = document.getElementById("tab-" + tabName);

    if (!targetTab) {
        console.error("Tab not found:", tabName);
        return;
    }

    targetTab.classList.remove("hidden");

    document.querySelectorAll(".step").forEach(step => {
        step.classList.remove("active");
    });

    const tabMap = {
        vehicle: 0,
        energy: 1,
        location: 2,
        result: 3
    };

    const steps = document.querySelectorAll(".step");
    const stepIndex = tabMap[tabName];

    if (stepIndex !== undefined && steps[stepIndex]) {
        steps[stepIndex].classList.add("active");
    }

    if (tabName === "location") {
        loadStationRecommendations();
    }
}

async function loadStationRecommendations() {
    const message = document.getElementById("stationMessage");
    const resultsContainer = document.getElementById("stationResults");

    const latitude = document.getElementById("latitude")?.value;
    const longitude = document.getElementById("longitude")?.value;
    const rangeInput = document.getElementById("vehicleSafeRange");
    const rangeKm = Number(rangeInput?.value);

    const vehicleInput = document.querySelector(
        'input[name="vehicle_type"]:checked'
    ) || document.querySelector('input[name="vehicle_type"]');

    const vehicleType = vehicleInput?.value;

    if (!message || !resultsContainer) return;

    resultsContainer.replaceChildren();

    if (!vehicleType) {
        message.textContent = "Please select a vehicle first.";
        return;
    }

    if (!latitude || !longitude) {
        message.textContent =
            "Please select your current location or search for an address first.";
        return;
    }

    message.textContent = "Finding nearby stations…";

    try {
if (!rangeInput || !Number.isFinite(rangeKm) || rangeKm <= 0) {
    message.textContent =
        "Please calculate a valid vehicle range first.";
    return;
}

const params = new URLSearchParams({
    vehicle_type: vehicleType,
    lat: latitude,
    lon: longitude,
    range_km: String(rangeKm)
});
        

        const response = await fetch(
            `/station-recommendations?${params.toString()}`
        );

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(
              data.message || data.error || "Unable to load station recommendations."
            );
        }

        if (!data.stations || data.stations.length === 0) {
            message.textContent = "";
            resultsContainer.innerHTML = `
                <div class="station-empty">
                    <div class="station-empty-icon">⌖</div>
                    <strong>No nearby stations found</strong>
                    <p>Try selecting another location and refreshing your results.</p>
                </div>
            `;
            return;
        }

        message.textContent =
            `${data.stations.length} station(s) found for ${vehicleType}.`;

        data.stations.forEach(station => {
            const card = document.createElement("article");
            card.className = "station-card";

            const top = document.createElement("div");
            top.className = "station-card-top";

            const icon = document.createElement("div");
            icon.className = "station-card-icon";
            icon.textContent =
                station.station_type === "EV Charging" ? "⚡" : "⛽";

            const badge = document.createElement("span");
            badge.className = "station-type-badge";
            badge.textContent = station.station_type || "Station";

            top.append(icon, badge);

            
const title = document.createElement("h3");

title.textContent =
    station.station_name ||
    station.name ||
    station.poi?.name ||
    "Nearby Station";

title.className = "station-name-link";
title.tabIndex = 0;
title.setAttribute("role", "button");
title.setAttribute("aria-label", `View route to ${title.textContent}`);

title.addEventListener("click", function () {
    selectRouteWiseStation(station, card);
});

title.addEventListener("keydown", function (event) {
    if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectRouteWiseStation(station, card);
    }
});


            const address = document.createElement("p");
            address.className = "station-address";

            const addressIcon = document.createElement("span");
            addressIcon.className = "station-address-icon";
            addressIcon.textContent = "📍";

            const addressText = document.createElement("span");
            const addressValue =
                typeof station.address === "string"
                    ? station.address
                    : station.address?.freeformAddress ||
                      station.poi?.address?.freeformAddress ||
                      station.address?.municipality ||
                      "Address not available";

            addressText.textContent = addressValue;

            
address.append(addressIcon, addressText);

// Display the station distance
const distance = document.createElement("p");
distance.className = "station-distance";

const distanceKm = Number(station.distance_km);

distance.textContent = Number.isFinite(distanceKm)
    ? `Distance: ${distanceKm.toFixed(1)} km`
    : "Distance unavailable";



card.append(top, title, address, distance);
resultsContainer.appendChild(card);


    } );}catch (error) {
        console.error("Station recommendations error:", error);

        message.textContent =error.message || "Could not load station recommendations.";
    }
}

window.addEventListener("DOMContentLoaded", function () {
    const activeTab = document.body.dataset.activeTab || "vehicle";
    switchTab(activeTab);
});

