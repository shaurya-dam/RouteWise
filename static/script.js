
// GLOBAL LIGHT / DARK MODE
const themeToggle = document.getElementById("themeToggle");
const themeIcon = document.getElementById("themeIcon");
const themeText = document.getElementById("themeText");

function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);

    if (theme === "dark") {
        themeIcon.textContent = "☀️";
        themeText.textContent = "Light mode";
    } else {
        themeIcon.textContent = "🌙";
        themeText.textContent = "Dark mode";
    }
}

const savedTheme = localStorage.getItem("routewise-theme") || "light";
applyTheme(savedTheme);

if (themeToggle) {
    themeToggle.addEventListener("click", function () {
        const currentTheme =
            document.documentElement.getAttribute("data-theme");

        const newTheme = currentTheme === "dark" ? "light" : "dark";

        applyTheme(newTheme);
        localStorage.setItem("routewise-theme", newTheme);
    });
}
 // AUTOMATIC LOCATION DETECTION

function detectCurrentLocation() {

    const latitudeInput = document.getElementById("latitude");
    const longitudeInput = document.getElementById("longitude");
    const status = document.getElementById("autoLocationStatus");
    const startButton = document.getElementById("startDashboard");

    if (!navigator.geolocation) {
        if (status) {
            status.textContent = "Location is not supported by this browser.";
        }
        return;
    }

    if (status) {
        status.textContent = "Detecting your current location...";
    }

    navigator.geolocation.getCurrentPosition(

        function (position) {

            const latitude = position.coords.latitude;
            const longitude = position.coords.longitude;

            latitudeInput.value = latitude;
            longitudeInput.value = longitude;

            if (status) {
                status.textContent = "✓ Current location detected successfully.";
            }

            if (startButton) {
                startButton.disabled = false;
            }

            console.log("Latitude:", latitude);
            console.log("Longitude:", longitude);
        },

        function (error) {

            console.error("Location error:", error);

            if (status) {
                status.textContent =
                    "Unable to detect location. Please allow location access and refresh the page.";
            }

            if (startButton) {
                startButton.disabled = true;
            }
        },

        {
            enableHighAccuracy: true,
            timeout: 15000,
            maximumAge: 0
        }
    );
}





// RouteWise simulated dashboard and navigation

let routeMap = null;
let routeLine = null;
let originMarker = null;
let destinationMarker = null;

let selectedRouteWiseStation = null;
let energyLevel = 0;
let energyTimer = null;
let simulationPaused = false;
let criticalAlertShown = false;

let vehicleType = document.body.dataset.vehicleType || "";
let currentTab = "vehicle";

const demoRanges = {
    PETROL: 420,
    EV: 360,
    HYBRID: 520
};

const CRITICAL_LEVEL = 20;


function getDemoRange() {
    return Math.round(
        (demoRanges[vehicleType] || 400) * energyLevel / 100
    );
}


function updateEnergyUI() {

    const percent = Math.max(0, Math.round(energyLevel));
    const range = getDemoRange();

    [
        "energyPercent",
        "energyMeterLabel",
        "resultEnergyPercent",
        "resultEnergyRingText"
    ].forEach(id => {

        const el = document.getElementById(id);

        if (el) {
            el.textContent =
                id === "resultEnergyPercent"
                    ? percent
                    : percent + "%";
        }

    });

    const rangeEl = document.getElementById("rangeKm");

    if (rangeEl) {
        rangeEl.textContent = range;
    }

    const fill = document.getElementById("energyMeterFill");

    if (fill) {
        fill.style.width = percent + "%";
    }

    const gauge = document.getElementById("simGauge");

    if (gauge) {
        gauge.style.setProperty("--energy-value", percent + "%");
    }

    const ring = document.getElementById("resultEnergyRing");

    if (ring) {
        ring.style.setProperty("--energy-value", percent + "%");
    }

    const state = document.getElementById("energyState");

    if (state) {

        state.textContent =
            percent <= CRITICAL_LEVEL
                ? "Critical energy — station recommended"
                : percent <= 40
                    ? "Energy getting low"
                    : "Energy level normal";

        state.className =
            "sim-state " +
            (
                percent <= CRITICAL_LEVEL
                    ? "critical"
                    : percent <= 40
                        ? "low"
                        : ""
            );
    }

    const label = document.getElementById("dashboardVehicleTitle");

    if (label) {
        label.textContent = (vehicleType || "Vehicle") + " dashboard";
    }

   

    const critical = document.getElementById("criticalPercent");

    if (critical) {
        critical.textContent = percent + "%";
    }
}


function startEnergySimulation() {

    if (energyTimer) {
        clearInterval(energyTimer);
    }

    // Random starting energy: 55% to 80%
    energyLevel = Math.floor(Math.random() * 26) + 55;

    simulationPaused = false;
    criticalAlertShown = false;

    updateEnergyUI();

    const pause = document.getElementById("pauseSimulation");

    if (pause) {
        pause.textContent = "Pause simulation";
    }

    energyTimer = setInterval(() => {

        if (simulationPaused || energyLevel <= 0) {
            return;
        }

        energyLevel = Math.max(0, energyLevel - 1);

        updateEnergyUI();

       if (
    energyLevel <= CRITICAL_LEVEL &&
    !criticalAlertShown &&
    currentTab === "dashboard"
) {
    criticalAlertShown = true;

    document
        .getElementById("criticalEnergyModal")
        ?.classList.remove("hidden");
}

    }, 4000);
}


function switchTab(tabName) {
currentTab = tabName;
    document.querySelectorAll(".tab-content").forEach(el => {
        el.classList.add("hidden");
    });

    const target = document.getElementById("tab-" + tabName);

    if (!target) {
        return;
    }

    target.classList.remove("hidden");

    const stepMap = {
        vehicle: 0,
        dashboard: 1,
        location: 2,
        result: 2
    };

    document.querySelectorAll(".step").forEach((el, i) => {
        el.classList.toggle("active", i === stepMap[tabName]);
    });

    if (tabName === "location") {
        loadStationRecommendations();
    }

    if (tabName === "result") {
        setTimeout(() => routeMap?.invalidateSize(), 150);
    }
}


function initializeRouteMap(lat, lon) {

    const el = document.getElementById("resultMap");

    if (!el || typeof L === "undefined") {
        throw new Error("Map library or map container is missing.");
    }

    const key = el.dataset.mapKey;

    if (!key) {
        throw new Error("TomTom map display key is missing.");
    }

    if (!routeMap) {

        routeMap = L.map(el).setView([lat, lon], 12);

        L.tileLayer(
            `https://{s}.api.tomtom.com/map/1/tile/basic/main/{z}/{x}/{y}.png?key=${encodeURIComponent(key)}`,
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
    const distanceEl = document.getElementById("routeDistance");
    const durationEl = document.getElementById("routeDuration");

    const lat = Number(document.getElementById("latitude")?.value);
    const lon = Number(document.getElementById("longitude")?.value);

    const destLat = Number(station.latitude);
    const destLon = Number(station.longitude);

    if (
        !Number.isFinite(lat) ||
        !Number.isFinite(lon) ||
        !Number.isFinite(destLat) ||
        !Number.isFinite(destLon)
    ) {

        if (status) {
            status.textContent =
                "Valid coordinates for your location and station are required.";
        }

        return;
    }

    try {

        const map = initializeRouteMap(lat, lon);

        if (status) status.textContent = "Calculating road route…";
        if (distanceEl) distanceEl.textContent = "Calculating…";
        if (durationEl) durationEl.textContent = "Calculating…";

        const q = new URLSearchParams({
            origin_lat: lat,
            origin_lon: lon,
            dest_lat: destLat,
            dest_lon: destLon
        });

        const response = await fetch(`/calculate-route?${q}`);

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.message || "Unable to calculate route.");
        }

        if (!Array.isArray(data.points) || data.points.length < 2) {
            throw new Error("No route geometry was returned.");
        }

        if (routeLine) map.removeLayer(routeLine);
        if (originMarker) map.removeLayer(originMarker);
        if (destinationMarker) map.removeLayer(destinationMarker);

        originMarker = L.marker([lat, lon])
            .addTo(map)
            .bindPopup("Your starting location");

        destinationMarker = L.marker([destLat, destLon])
            .addTo(map)
            .bindPopup(station.station_name || station.name || "Selected station");

        routeLine = L.polyline(
            data.points.map(p => [p.lat, p.lon]),
            {
                color: "#325b33",
                weight: 6,
                opacity: 0.85
            }
        ).addTo(map);

        map.fitBounds(routeLine.getBounds(), {
            padding: [35, 35]
        });

        if (distanceEl) {
            distanceEl.textContent = `${Number(data.distance_km).toFixed(2)} km`;
        }

        if (durationEl) {
            durationEl.textContent = `${data.travel_time_minutes} min`;
        }

        if (status) {
            status.textContent = "Road route calculated successfully.";
        }

    } catch (err) {

        console.error(err);

        if (status) status.textContent = err.message;
        if (distanceEl) distanceEl.textContent = "Unavailable";
        if (durationEl) durationEl.textContent = "Unavailable";
    }
}


function selectRouteWiseStation(station, card) {

    selectedRouteWiseStation = station;

    document.querySelectorAll(".station-card").forEach(el => {
        el.classList.remove("selected-station");
    });

    card?.classList.add("selected-station");

    const name =
        station.station_name ||
        station.name ||
        station.poi?.name ||
        "Selected station";

    const address =
        typeof station.address === "string"
            ? station.address
            : station.address?.freeformAddress ||
              station.poi?.address?.freeformAddress ||
              station.address?.municipality ||
              "Address not available";

    const put = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    };

    put("resultStationName", name);
    put("resultStationAddress", address);

    put(
        "resultStationDistance",
        Number.isFinite(Number(station.distance_km))
            ? Number(station.distance_km).toFixed(1) + " km"
            : "Unavailable"
    );

    put("resultStationType", station.station_type || "Station");

    switchTab("result");

    setTimeout(() => calculateAndDisplayRoute(station), 180);
}


async function loadStationRecommendations() {

    const message = document.getElementById("stationMessage");
    const container = document.getElementById("stationResults");

    if (!message || !container) {
        return;
    }

    container.replaceChildren();

    const lat = document.getElementById("latitude")?.value;
    const lon = document.getElementById("longitude")?.value;

    if (!vehicleType) {
        message.textContent = "Please select a vehicle first.";
        return;
    }

    if (!lat || !lon) {
        message.textContent = "Please set your starting location first.";
        return;
    }

    const rangeKm = Math.max(1, getDemoRange());

    message.textContent = "Finding nearby stations…";

    try {

        const q = new URLSearchParams({
            vehicle_type: vehicleType,
            lat,
            lon,
            range_km: String(rangeKm)
        });

        const response = await fetch(`/station-recommendations?${q}`);

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(
                data.message ||
                data.error ||
                "Unable to load stations."
            );
        }

        if (!data.stations?.length) {
            message.textContent =
                "No nearby stations found. Try another location or refresh.";
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
            title.className = "station-name-link";
            title.textContent =
                station.station_name ||
                station.name ||
                station.poi?.name ||
                "Nearby Station";

            const addr = document.createElement("p");
            addr.className = "station-address";
            addr.textContent =
                typeof station.address === "string"
                    ? station.address
                    : station.address?.freeformAddress ||
                      station.poi?.address?.freeformAddress ||
                      "Address not available";

            const dist = document.createElement("p");
            dist.className = "station-distance";
            dist.textContent =
                Number.isFinite(Number(station.distance_km))
                    ? `Distance: ${Number(station.distance_km).toFixed(1)} km`
                    : "Distance unavailable";

            title.addEventListener("click", () => {
                selectRouteWiseStation(station, card);
            });

            card.append(top, title, addr, dist);
            container.append(card);
        });

    } catch (err) {

        console.error(err);

        message.textContent =
            err.message || "Could not load station recommendations.";
    }
}



document.addEventListener("DOMContentLoaded", () => {

    // Automatically detect location when page loads
    if (vehicleType) {
        detectCurrentLocation();
    }

    const start = document.getElementById("startDashboard");

    start?.addEventListener("click", () => {

        const lat = document.getElementById("latitude")?.value;
        const lon = document.getElementById("longitude")?.value;

        if (!lat || !lon) {
            alert("Please wait for your location to be detected.");
            return;
        }

        startEnergySimulation();
        switchTab("dashboard");
    });

    document.getElementById("pauseSimulation")?.addEventListener("click", e => {

        simulationPaused = !simulationPaused;

        e.currentTarget.textContent =
            simulationPaused
                ? "Resume simulation"
                : "Pause simulation";
    });

    document.getElementById("dismissCritical")?.addEventListener("click", () => {

        document
            .getElementById("criticalEnergyModal")
            ?.classList.add("hidden");
    });

    document.getElementById("findStationNow")?.addEventListener("click", () => {

        document
            .getElementById("criticalEnergyModal")
            ?.classList.add("hidden");

        switchTab("location");
    });

});
