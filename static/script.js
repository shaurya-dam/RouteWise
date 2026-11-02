// ============================================================
// ROUTEWISE — GLOBAL APPLICATION STATE & CONFIGURATION
// ============================================================

let currentEnergyPercent = 85;
let simulationInterval = null;
let safeRangeKm = 0;
let userCoords = { lat: 30.3165, lon: 78.0322 }; // Default: Dehradun

// Global Leaflet Map References
let routewiseMap = null;
let routewiseMarkersGroup = null;
let routewisePolyline = null;

// Load Config passed from Flask Jinja2 Template
const appConfig = window.RouteWiseConfig || { 
    vehicleType: '', 
    backendStations: [], 
    cppRouteData: null, 
    tomtomMapKey: 'KAPybFJvNpPrXre1o4F2dy7ywR0IYTtB' 
};

// ============================================================
// 1. TAB SWITCHING & MAP RESIZE FIX
// ============================================================

function switchTab(tabName) {
    // Hide all tab sections
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.add('hidden');
    });

    // Show target tab
    const targetTab = document.getElementById(`tab-${tabName}`);
    if (targetTab) {
        targetTab.classList.remove('hidden');
    }

    // Update progress stepper indicators
    document.querySelectorAll('.step').forEach(step => {
        step.classList.remove('active');
        if (step.getAttribute('data-step') === tabName) {
            step.classList.add('active');
        }
    });

    // Invalidate Leaflet Map size when tab becomes visible
    if (tabName === 'result') {
        setTimeout(() => {
            if (routewiseMap) {
                routewiseMap.invalidateSize();
            } else {
                initLeafletMap();
            }
        }, 150);
    }
}

// ============================================================
// 2. LIVE ENERGY SIMULATION & MINI WIDGET UPDATES
// ============================================================

function updateEnergyDisplays(percent) {
    currentEnergyPercent = percent;

    // Update Main Dashboard Gauge
    const energyText = document.getElementById('energyPercent');
    const rangeKmText = document.getElementById('rangeKm');
    const energyState = document.getElementById('energyState');

    if (energyText) energyText.textContent = `${percent}%`;

    const remainingKm = Math.max(0, Math.round((safeRangeKm * percent) / 100));
    if (rangeKmText) rangeKmText.textContent = safeRangeKm > 0 ? remainingKm : '--';

    if (energyState) {
        if (percent <= 20) {
            energyState.textContent = 'Critical Energy Warning';
            energyState.className = 'sim-state critical';
        } else if (percent <= 50) {
            energyState.textContent = 'Low Energy Margin';
            energyState.className = 'sim-state low';
        } else {
            energyState.textContent = 'Normal Operating Energy';
            energyState.className = 'sim-state';
        }
    }

    // Update Floating Mini Live Energy Widget on Map Overlay
    const miniText = document.getElementById('miniEnergyPercent');
    const miniFill = document.getElementById('miniEnergyFill');

    if (miniText && miniFill) {
        miniText.textContent = `${percent}%`;
        miniFill.style.width = `${percent}%`;

        if (percent <= 20) {
            miniFill.style.backgroundColor = '#ef4444';
            miniText.style.color = '#ef4444';
        } else if (percent <= 50) {
            miniFill.style.backgroundColor = '#eab308';
            miniText.style.color = '#eab308';
        } else {
            miniFill.style.backgroundColor = '#10b981';
            miniText.style.color = '#10b981';
        }
    }

    // Trigger Critical Alert Popup if energy drops below 20%
    if (percent <= 20) {
        const modal = document.getElementById('criticalEnergyModal');
        const critPercent = document.getElementById('criticalPercent');
        if (modal && modal.classList.contains('hidden')) {
            if (critPercent) critPercent.textContent = `${percent}%`;
            modal.classList.remove('hidden');
        }
    }
}

function startEnergySimulation() {
    if (simulationInterval) clearInterval(simulationInterval);

    simulationInterval = setInterval(() => {
        if (currentEnergyPercent > 5) {
            updateEnergyDisplays(currentEnergyPercent - 1);
        } else {
            clearInterval(simulationInterval);
        }
    }, 4000);
}

// ============================================================
// 3. LEAFLET.JS MAP INITIALIZATION & REAL ROAD ROUTING
// ============================================================

function initLeafletMap() {
    const mapContainer = document.getElementById('resultMap');
    if (!mapContainer || routewiseMap) return;

    // Initialize Map Instance
    routewiseMap = L.map('resultMap').setView([userCoords.lat, userCoords.lon], 13);

    // Get TomTom Key from config or fallback
    const apiKey = (appConfig && appConfig.tomtomMapKey) ? appConfig.tomtomMapKey : 'KAPybFJvNpPrXre1o4F2dy7ywR0IYTtB';

    // Official TomTom Night Mode Map Tile Layer
    L.tileLayer(`https://{s}.api.tomtom.com/map/1/tile/basic/night/{z}/{x}/{y}.png?key=${apiKey}`, {
        attribution: '&copy; TomTom &copy; OpenStreetMap',
        subdomains: 'abcd',
        maxZoom: 19
    }).addTo(routewiseMap);

    routewiseMarkersGroup = L.layerGroup().addTo(routewiseMap);
}

function selectStationAndDrawRoute(name, lat, lon, distanceKm, stationType) {
    // 1. Update Navigation Floating Info Box
    const targetName = document.getElementById('resultStationName');
    const targetAddr = document.getElementById('resultStationAddress');
    const distText = document.getElementById('routeDistance');
    const durationText = document.getElementById('routeDuration');

    if (targetName) targetName.textContent = name;
    if (targetAddr) targetAddr.textContent = `${stationType || 'Station'} • ${distanceKm} km away`;
    if (distText) distText.textContent = `Calculating route...`;
    if (durationText) durationText.textContent = `Calculating...`;

    // 2. Switch to Full-Screen Result/Map Screen
    switchTab('result');

    // 3. Fetch Real Turn-by-Turn Road Geometry from TomTom Routing API
    setTimeout(() => {
        if (!routewiseMap) initLeafletMap();
        routewiseMap.invalidateSize();

        routewiseMarkersGroup.clearLayers();
        if (routewisePolyline) {
            routewiseMap.removeLayer(routewisePolyline);
        }

        // Add Start & Destination Markers
        L.marker([userCoords.lat, userCoords.lon])
            .bindPopup(`<b>📍 Your Location</b><br>Lat: ${userCoords.lat.toFixed(4)}, Lon: ${userCoords.lon.toFixed(4)}`)
            .addTo(routewiseMarkersGroup);

        const stationMarker = L.marker([lat, lon])
            .bindPopup(`<b>⚡ ${name}</b><br>${stationType || 'Station'}`)
            .addTo(routewiseMarkersGroup);

        // Fetch turn-by-turn road coordinates from Flask backend
        fetch(`/calculate-route?origin_lat=${userCoords.lat}&origin_lon=${userCoords.lon}&dest_lat=${lat}&dest_lon=${lon}`)
            .then(res => res.json())
            .then(routeData => {
                let routePoints = [];

                if (routeData.success && routeData.points && routeData.points.length > 0) {
                    // Extract exact turn-by-turn street coordinates
                    routePoints = routeData.points.map(p => [p.lat, p.lon]);

                    if (distText) distText.textContent = `${routeData.distance_km} km`;
                    if (durationText) durationText.textContent = `${routeData.travel_time_minutes} mins`;
                } else {
                    // Fallback to straight line if API fails
                    routePoints = [[userCoords.lat, userCoords.lon], [lat, lon]];
                    if (distText) distText.textContent = `${distanceKm} km`;
                    if (durationText) durationText.textContent = `${Math.round(distanceKm * 2.2)} mins`;
                }

                // Draw Blue Polyline along actual roads
                routewisePolyline = L.polyline(routePoints, {
                    color: '#38bdf8',
                    weight: 6,
                    opacity: 0.9,
                    lineCap: 'round',
                    lineJoin: 'round'
                }).addTo(routewiseMap);

                // Auto-fit bounds around the route
                routewiseMap.fitBounds(routewisePolyline.getBounds(), { padding: [50, 50] });
                stationMarker.openPopup();
            })
            .catch(err => {
                console.error("Error fetching road route:", err);
                routewisePolyline = L.polyline([[userCoords.lat, userCoords.lon], [lat, lon]], {
                    color: '#38bdf8', weight: 5, opacity: 0.8
                }).addTo(routewiseMap);
                routewiseMap.fitBounds(routewisePolyline.getBounds(), { padding: [50, 50] });
            });
    }, 200);
}

// ============================================================
// 4. STATION RECOMMENDATION FETCHING & RENDERING
// ============================================================

function loadStationRecommendations() {
    const resultsContainer = document.getElementById('stationResults');
    const msgContainer = document.getElementById('stationMessage');

    if (!resultsContainer) return;

    const vType = appConfig.vehicleType || 'EV';
    const rangeToUse = safeRangeKm > 0 ? safeRangeKm : 50;

    msgContainer.textContent = "Fetching nearest reachable stations using C++ range filtering...";
    resultsContainer.innerHTML = '<div class="station-empty">Searching nearby stations...</div>';

    fetch(`/station-recommendations?vehicle_type=${encodeURIComponent(vType)}&lat=${userCoords.lat}&lon=${userCoords.lon}&range_km=${rangeToUse}`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.stations && data.stations.length > 0) {
                msgContainer.textContent = `Found ${data.count} reachable stations within your safe usable range (${rangeToUse} km).`;
                resultsContainer.innerHTML = '';

                data.stations.forEach(st => {
                    const card = document.createElement('div');
                    card.className = 'station-card';
                    card.innerHTML = `
                        <div class="station-card-top">
                            <div class="station-card-icon">${st.station_type === 'EV Charging' ? '⚡' : '⛽'}</div>
                            <span class="station-type-badge">${st.station_type || 'Station'}</span>
                        </div>
                        <h3>${st.name}</h3>
                        <p class="station-address">📍 ${st.address || 'Location nearby'}</p>
                        <p class="station-distance">Distance: <strong>${st.distance_km} km</strong></p>
                        <div style="margin-top: 14px;">
                            <button type="button" class="primary-button" style="width: 100%;"
                                onclick="selectStationAndDrawRoute('${st.name.replace(/'/g, "\\'")}', ${st.latitude}, ${st.longitude}, ${st.distance_km}, '${st.station_type}')">
                                View Full Route Map ↗
                            </button>
                        </div>
                    `;
                    resultsContainer.appendChild(card);
                });
            } else {
                msgContainer.textContent = "No stations found within calculated range.";
                resultsContainer.innerHTML = `
                    <div class="station-empty">
                        <div class="station-empty-icon">⚠️</div>
                        <strong>No reachable stations in range</strong>
                        <p>${data.message || 'Try adjusting your vehicle energy level or range input.'}</p>
                    </div>
                `;
            }
        })
        .catch(err => {
            console.error("Error loading stations:", err);
            msgContainer.textContent = "Failed to load station recommendations.";
        });
}

// ============================================================
// 5. DOM INITIALIZATION & EVENT LISTENERS
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    // Geolocation API
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                userCoords.lat = pos.coords.latitude;
                userCoords.lon = pos.coords.longitude;
                const latInput = document.getElementById('latitude');
                const lonInput = document.getElementById('longitude');
                if (latInput) latInput.value = userCoords.lat;
                if (lonInput) lonInput.value = userCoords.lon;
            },
            (err) => {
                console.warn("Geolocation warning, using default coordinates:", err.message);
            }
        );
    }

    // Read C++ Range output if present
    if (appConfig.cppRouteData && appConfig.cppRouteData.safe_range) {
        safeRangeKm = appConfig.cppRouteData.safe_range;
    } else {
        safeRangeKm = 65;
    }

    // Setup Start Dashboard Button
    const startDashBtn = document.getElementById('startDashboard');
    if (startDashBtn) {
        startDashBtn.disabled = false;
        startDashBtn.addEventListener('click', () => {
            switchTab('dashboard');
            startEnergySimulation();
        });
    }

    // Stepper click listeners
    document.querySelectorAll('.step').forEach(step => {
        step.addEventListener('click', () => {
            const stepName = step.getAttribute('data-step');
            if (stepName) switchTab(stepName);
        });
    });

    // Modal actions
    const dismissBtn = document.getElementById('dismissCritical');
    const findNowBtn = document.getElementById('findStationNow');
    const modal = document.getElementById('criticalEnergyModal');

    if (dismissBtn) {
        dismissBtn.addEventListener('click', () => {
            if (modal) modal.classList.add('hidden');
        });
    }

    if (findNowBtn) {
        findNowBtn.addEventListener('click', () => {
            if (modal) modal.classList.add('hidden');
            switchTab('location');
            loadStationRecommendations();
        });
    }

    // Initialize map container immediately
    initLeafletMap();
    updateEnergyDisplays(currentEnergyPercent);
});