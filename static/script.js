let currentEnergyPercent = 85;
let simulationInterval = null;
let dashboardTimeout = null;
let criticalWarningShown = false;   // 20% warning ek hi baar dikhe
let energyReady = false;          // start battery % sirf ek baar set ho
const DROP_INTERVAL_MS = 15000;   // har 15 second me 1% battery kam (zyada slow chahiye to number badha do)
let safeRangeKm = 0;
let userCoords = { lat: 30.3165, lon: 78.0322 };

let routewiseMap = null;
let routewiseMarkersGroup = null;
let routewisePolyline = null;
let routewisePreview = null;      // route aane tak dikhne wali dotted seedhi line

let stationRequestId = 0;  
let routeRequestId = 0;
let currentTab = 'vehicle';

const appConfig = window.RouteWiseConfig || { vehicleType: 'EV', cppRouteData: null };

function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function switchTab(tabName) {
    currentTab = tabName;

    
    if (dashboardTimeout) { clearTimeout(dashboardTimeout); dashboardTimeout = null; }

    document.querySelectorAll('.tab-content').forEach(tab => { tab.classList.add('hidden'); });
    const targetTab = document.getElementById(`tab-${tabName}`);
    if (targetTab) targetTab.classList.remove('hidden');

    document.querySelectorAll('.step').forEach(step => {
        step.classList.remove('active');
        if (step.getAttribute('data-step') === tabName) step.classList.add('active');
    });

    if (tabName === 'dashboard') {
        showDashboardFetchingState();
        dashboardTimeout = setTimeout(() => {
            initEnergy();
            updateEnergyDisplays(currentEnergyPercent);
            startEnergySimulation();
        }, 900);
    }

    if (tabName === 'location') {
        initEnergy();
        updateEnergyDisplays(currentEnergyPercent);
        startEnergySimulation();
       
        setTimeout(() => {
            if (!routewiseMap) initLeafletMap();
            if (routewiseMap) routewiseMap.invalidateSize();
            loadStationRecommendations();
        }, 200);
    }
}

function showDashboardFetchingState() {
    const energyText = document.getElementById('energyPercent');
    const rangeKmText = document.getElementById('rangeKm');
    const energyState = document.getElementById('energyState');

    if (energyText) {
        energyText.style.fontSize = '1rem';
        energyText.style.color = '#38bdf8';
        energyText.textContent = 'Fetching details...';
    }
    if (rangeKmText) rangeKmText.textContent = '--';
    if (energyState) {
        energyState.textContent = '⚡ Connecting to Telemetry Engine...';
        energyState.className = 'sim-state';
        energyState.style.color = '#38bdf8';
    }
}

function updateEnergyDisplays(percent) {
    currentEnergyPercent = percent;
    checkCriticalWarning(percent);
    const energyText = document.getElementById('energyPercent');
    const rangeKmText = document.getElementById('rangeKm');
    const energyState = document.getElementById('energyState');

    if (energyText) {
        energyText.style.fontSize = '2.2rem';
        energyText.style.color = '#ffffff';
        energyText.textContent = `${percent}%`;
    }

    const remainingKm = Math.max(0, Math.round((safeRangeKm * percent) / 100));
    if (rangeKmText) rangeKmText.textContent = safeRangeKm > 0 ? remainingKm : '--';

    if (energyState) {
        energyState.style.color = '';
        if (percent <= 20) {
            energyState.textContent = 'Critical Energy Warning';
            energyState.className = 'sim-state critical';
        } else if (percent <= 50) {
            energyState.textContent = 'Low Energy Margin';
            energyState.className = 'sim-state low';
        } else {
            energyState.textContent = 'Normal';
            energyState.className = 'sim-state';
        }
    }

    const mapVal = document.getElementById('mapEnergyVal');
    const mapFill = document.getElementById('mapEnergyBarFill');

    if (mapVal && mapFill) {
        mapVal.textContent = `${percent}%`;
        mapFill.style.width = `${percent}%`;

        if (percent <= 20) {
            mapFill.style.background = 'linear-gradient(90deg, #ef4444, #f87171)';
            mapVal.style.color = '#ef4444';
        } else if (percent <= 50) {
            mapFill.style.background = 'linear-gradient(90deg, #f59e0b, #fbbf24)';
            mapVal.style.color = '#f59e0b';
        } else {
            mapFill.style.background = 'linear-gradient(90deg, #10b981, #34d399)';
            mapVal.style.color = '#10b981';
        }
    }
}

// ---------- 20% se kam hone par popup ----------
function checkCriticalWarning(percent) {
    const modal = document.getElementById('energyModal');
    if (!modal) return;

    if (percent <= 20) {
        setText('modalEnergyVal', `${percent}%`);     
        if (!criticalWarningShown) {
            criticalWarningShown = true;
            modal.classList.remove('hidden');
        }
    } else {
        criticalWarningShown = false;                 
        modal.classList.add('hidden');
    }
}

function closeEnergyModal() {
    const modal = document.getElementById('energyModal');
    if (modal) modal.classList.add('hidden');
}

function goToStations() {
    closeEnergyModal();
    if (currentTab !== 'location') switchTab('location');
}

function initEnergy() {
   
    if (energyReady) return;
    const start = appConfig.cppRouteData && appConfig.cppRouteData.battery_percent;
    if (start) currentEnergyPercent = start;
    energyReady = true;
}

function startEnergySimulation() {
    if (simulationInterval) return;    
    simulationInterval = setInterval(() => {
        if (currentEnergyPercent > 5) {
            updateEnergyDisplays(currentEnergyPercent - 1);
        } else {
            clearInterval(simulationInterval);
            simulationInterval = null;
        }
    }, DROP_INTERVAL_MS);
}

function initLeafletMap() {
    const mapContainer = document.getElementById('sideMap');
    if (!mapContainer || routewiseMap) return;
    if (typeof L === 'undefined') {
        console.error('Leaflet load nahi hua (unpkg.com blocked ya internet issue).');
        setText('resultStationName', 'Map library load nahi hui');
        return;
    }

    routewiseMap = L.map('sideMap', { zoomControl: true }).setView([userCoords.lat, userCoords.lon], 13);

    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
        className: 'dark-tiles'
    }).addTo(routewiseMap);

    
    let tileErrors = 0;
    tiles.on('tileerror', () => {
        tileErrors++;
        if (tileErrors === 5 && routewiseMap) {
            routewiseMap.removeLayer(tiles);
            L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', {
                attribution: 'Tiles &copy; Esri',
                maxZoom: 19,
                className: 'dark-tiles'
            }).addTo(routewiseMap);
        }
    });

    routewiseMarkersGroup = L.layerGroup().addTo(routewiseMap);
    setTimeout(() => { if (routewiseMap) routewiseMap.invalidateSize(); }, 250);
}

function createMarkerIcon(color, isFastest = false) {
    const size = isFastest ? 26 : 20;
    const border = isFastest ? '4px solid #ffffff' : '2px solid #ffffff';
    const shadow = isFastest ? `0 0 20px ${color}` : `0 0 10px ${color}`;

    return L.divIcon({
        className: 'custom-pin',
        html: `<div style="background-color: ${color}; width: ${size}px; height: ${size}px; border-radius: 50%; border: ${border}; box-shadow: ${shadow};"></div>`,
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2]
    });
}

function addUserMarker() {
    if (!routewiseMarkersGroup) return;
    L.marker([userCoords.lat, userCoords.lon], { icon: createMarkerIcon('#38bdf8'), zIndexOffset: 500 })
        .bindPopup("<b>📍 Your Location</b>").addTo(routewiseMarkersGroup);
}

function loadStationRecommendations() {
    if (!routewiseMap) initLeafletMap();
    if (!routewiseMap) return;

    const myRequest = ++stationRequestId;
    const vType = appConfig.vehicleType || 'EV';

    const routeCard = document.getElementById('mapRouteCard');
    if (routeCard) routeCard.style.display = 'block';

    setText('resultStationName', "Scanning route & stations...");
    setText('resultStationAddress', "Please wait, finding nearest road route...");
    setText('routeDistance', "Loading...");
    setText('routeDuration', "Loading...");

    if (routewiseMarkersGroup) {
        routewiseMarkersGroup.clearLayers();
        addUserMarker();
    }
    clearRouteLines();

    fetch(`/station-recommendations?vehicle_type=${encodeURIComponent(vType)}&lat=${userCoords.lat}&lon=${userCoords.lon}`)
        .then(res => res.json())
        .then(data => {
            if (myRequest !== stationRequestId) return;   
            if (data.success && data.stations && data.stations.length > 0 && routewiseMarkersGroup) {
                routewiseMarkersGroup.clearLayers();
                const mapBounds = [[userCoords.lat, userCoords.lon]];

                addUserMarker();

                const fastest = data.stations[0];
                drawRouteOnSideMap(fastest.name, fastest.address, fastest.latitude, fastest.longitude, true, fastest);

                data.stations.forEach((st, index) => {
                    let pinColor = '#f59e0b';
                    let isFastest = false;
                    let zIndex = 100;

                    if (index === 0) {
                        pinColor = '#10b981';
                        isFastest = true;
                        zIndex = 1000;
                    } else if (index === data.stations.length - 1) {
                        pinColor = '#ef4444';
                        zIndex = 200;
                    }

                    const marker = L.marker([st.latitude, st.longitude], {
                        icon: createMarkerIcon(pinColor, isFastest),
                        zIndexOffset: zIndex
                    }).bindPopup(`<b>${isFastest ? '🏆 NEAREST: ' : ''}${st.name}</b><br>${st.route_source === 'estimate' ? '~' : ''}${st.distance_km} km`)
                      .addTo(routewiseMarkersGroup);

                    marker.on('click', function () {
                        drawRouteOnSideMap(st.name, st.address, st.latitude, st.longitude, isFastest, st);
                    });

                    mapBounds.push([st.latitude, st.longitude]);
                });

                routewiseMap.fitBounds(mapBounds, { padding: [50, 50] });
            } else {
                setText('resultStationName', "No stations found nearby");
                setText('resultStationAddress', "");
                setText('routeDistance', "—");
                setText('routeDuration', "—");
            }
        })
        .catch(err => {
            if (myRequest !== stationRequestId) return;
            console.error("Loading error:", err);
            setText('resultStationName', "Connection Error");
            setText('resultStationAddress', "Could not fetch station data.");
            setText('routeDistance', "—");
            setText('routeDuration', "—");
        });
}

function clearRouteLines() {
    if (routewiseMap && routewisePolyline) routewiseMap.removeLayer(routewisePolyline);
    if (routewiseMap && routewisePreview) routewiseMap.removeLayer(routewisePreview);
    routewisePolyline = null;
    routewisePreview = null;
}

function drawRouteOnSideMap(name, address, lat, lon, isFastest, estimate) {
    const myRoute = ++routeRequestId;
    const routeCard = document.getElementById('mapRouteCard');
    const badge = document.getElementById('routeBadge');

    setText('resultStationName', name);
    setText('resultStationAddress', address || "");
    // Asli route aane tak andaza turant dikhao (~ matlab approximate)
    if (estimate && estimate.distance_km) {
        setText('routeDistance', `~${estimate.distance_km} km`);
        setText('routeDuration', `~${estimate.travel_time_minutes} mins`);
    } else {
        setText('routeDistance', "Calc...");
        setText('routeDuration', "Loading...");
    }
    if (routeCard) routeCard.style.display = 'block';

    if (badge) {
        if (isFastest) {
            badge.textContent = "🏆 SHORTEST ROAD ROUTE";
            badge.style.color = "#10b981";
        } else {
            badge.textContent = "⚡ ALTERNATIVE ROUTE";
            badge.style.color = "#f59e0b";
        }
    }

    clearRouteLines();
    if (routewiseMap) {
        // dotted seedhi line: road route aane tak
        routewisePreview = L.polyline([[userCoords.lat, userCoords.lon], [lat, lon]], {
            color: '#38bdf8', weight: 3, opacity: 0.6, dashArray: '8 10'
        }).addTo(routewiseMap);
    }

    fetch(`/calculate-route?origin_lat=${userCoords.lat}&origin_lon=${userCoords.lon}&dest_lat=${lat}&dest_lon=${lon}`)
        .then(res => res.json())
        .then(routeData => {
            if (myRoute !== routeRequestId) return;   

            if (routeData.success && routeData.points && routeData.points.length > 0 && routewiseMap) {
                const routePoints = routeData.points.map(p => [p.lat, p.lon]);

                const timeText = routeData.traffic_delay_minutes > 0
                    ? `${routeData.travel_time_minutes} mins (+${routeData.traffic_delay_minutes}m traffic)`
                    : `${routeData.travel_time_minutes} mins`;

                setText('routeDistance', `${routeData.distance_km} km`);
                setText('routeDuration', timeText);

                clearRouteLines();
                routewisePolyline = L.polyline(routePoints, {
                    color: '#38bdf8',
                    weight: 6,
                    opacity: 0.9,
                    lineCap: 'round',
                    lineJoin: 'round'
                }).addTo(routewiseMap);

                routewiseMap.fitBounds(routewisePolyline.getBounds(), { padding: [60, 60] });
            } else {
                setText('routeDistance', "N/A");
                setText('routeDuration', "N/A");
            }
        })
        .catch(err => {
            if (myRoute !== routeRequestId) return;
            console.error("Routing error:", err);
            setText('routeDistance', "N/A");
            setText('routeDuration', "N/A");
        });
}

// Page khulte hi background me stations + road graph taiyar karwao (map tab jaldi khule)
function warmUp() {
    const vType = appConfig.vehicleType || 'EV';
    fetch(`/warmup?vehicle_type=${encodeURIComponent(vType)}&lat=${userCoords.lat}&lon=${userCoords.lon}`)
        .catch(() => {});
}

document.addEventListener('DOMContentLoaded', () => {
    safeRangeKm = (appConfig.cppRouteData && appConfig.cppRouteData.safe_range)
        ? appConfig.cppRouteData.safe_range
        : 65;

    const initialTab = document.body.getAttribute('data-active-tab') || 'vehicle';
    switchTab(initialTab);
    warmUp();                           // default location ke liye abhi se tayyari

    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                userCoords.lat = pos.coords.latitude;
                userCoords.lon = pos.coords.longitude;
                warmUp();                       // asli location ke liye tayyari
                // Sirf tab reload karo jab user map tab par ho
                if (routewiseMap && currentTab === 'location') {
                    routewiseMap.setView([userCoords.lat, userCoords.lon], 13);
                    loadStationRecommendations();
                }
            },
            (err) => console.warn("Geolocation denied/failed, default location use ho rahi hai:", err.message),
            { timeout: 8000 }
        );
    }
});