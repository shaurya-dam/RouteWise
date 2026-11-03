let currentEnergyPercent = 85;
let simulationInterval = null;
let safeRangeKm = 0;
let userCoords = { lat: 30.3165, lon: 78.0322 }; 

let routewiseMap = null;
let routewiseMarkersGroup = null;
let routewisePolyline = null;

const appConfig = window.RouteWiseConfig || { vehicleType: '', cppRouteData: null, tomtomMapKey: 'KAPybFJvNpPrXre1o4F2dy7ywR0IYTtB' };

function switchTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(tab => { tab.classList.add('hidden'); });
    const targetTab = document.getElementById(`tab-${tabName}`);
    if (targetTab) targetTab.classList.remove('hidden');

    document.querySelectorAll('.step').forEach(step => {
        step.classList.remove('active');
        if (step.getAttribute('data-step') === tabName) step.classList.add('active');
    });

    if (tabName === 'dashboard') {
        // Dashboard open hote hi pehle Fetching Details dikhayega
        showDashboardFetchingState();
        setTimeout(() => {
            let targetPercent = (appConfig.cppRouteData && appConfig.cppRouteData.battery_percent) ? appConfig.cppRouteData.battery_percent : 85;
            updateEnergyDisplays(targetPercent);
            startEnergySimulation();
        }, 1000);
    }

    if (tabName === 'location') {
        setTimeout(() => {
            if (!routewiseMap) initLeafletMap();
            else routewiseMap.invalidateSize();
            loadStationRecommendations();
        }, 150);
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
    const energyText = document.getElementById('energyPercent');
    const rangeKmText = document.getElementById('rangeKm');
    const energyState = document.getElementById('energyState');
    
    if (energyText) {
        energyText.style.fontSize = '2.2rem'; // Reset font size once loaded
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
            energyState.textContent = 'Telemetry Active • Normal Operation';
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

function startEnergySimulation() {
    if (simulationInterval) clearInterval(simulationInterval);
    simulationInterval = setInterval(() => {
        if (currentEnergyPercent > 5) updateEnergyDisplays(currentEnergyPercent - 1);
        else clearInterval(simulationInterval);
    }, 10000); 
}

function initLeafletMap() {
    const mapContainer = document.getElementById('sideMap');
    if (!mapContainer || routewiseMap) return;

    routewiseMap = L.map('sideMap').setView([userCoords.lat, userCoords.lon], 13);
    const apiKey = (appConfig && appConfig.tomtomMapKey) ? appConfig.tomtomMapKey : 'KAPybFJvNpPrXre1o4F2dy7ywR0IYTtB';

    L.tileLayer(`https://{s}.api.tomtom.com/map/1/tile/basic/night/{z}/{x}/{y}.png?key=${apiKey}`, {
        attribution: '&copy; TomTom &copy; OpenStreetMap', subdomains: 'abcd', maxZoom: 19
    }).addTo(routewiseMap);
    
    routewiseMarkersGroup = L.layerGroup().addTo(routewiseMap);
}

function createMarkerIcon(color, isFastest = false) {
    const size = isFastest ? 26 : 20;
    const border = isFastest ? '4px solid #ffffff' : '2px solid #ffffff';
    const shadow = isFastest ? `0 0 20px ${color}` : `0 0 10px ${color}`;
    
    return L.divIcon({
        className: 'custom-pin',
        html: `<div style="background-color: ${color}; width: ${size}px; height: ${size}px; border-radius: 50%; border: ${border}; box-shadow: ${shadow};"></div>`,
        iconSize: [size, size], 
        iconAnchor: [size/2, size/2]
    });
}

function loadStationRecommendations() {
    const vType = appConfig.vehicleType || 'EV';
    document.getElementById('mapRouteCard').style.display = 'block';
    
    document.getElementById('resultStationName').textContent = "Scanning route & stations...";
    document.getElementById('resultStationAddress').textContent = "Please wait, fetching live traffic & data...";
    document.getElementById('routeDistance').textContent = "Loading...";
    document.getElementById('routeDuration').textContent = "Loading...";

    fetch(`/station-recommendations?vehicle_type=${encodeURIComponent(vType)}&lat=${userCoords.lat}&lon=${userCoords.lon}`)
        .then(res => res.json())
        .then(data => {
            if (data.success && data.stations && data.stations.length > 0) {
                routewiseMarkersGroup.clearLayers();
                let mapBounds = [[userCoords.lat, userCoords.lon]];

                L.marker([userCoords.lat, userCoords.lon], { icon: createMarkerIcon('#38bdf8'), zIndexOffset: 500 })
                    .bindPopup("<b>📍 Your Location</b>").addTo(routewiseMarkersGroup);

                const fastest = data.stations[0];
                drawRouteOnSideMap(fastest.name, fastest.address, fastest.latitude, fastest.longitude, true);

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

                    let marker = L.marker([st.latitude, st.longitude], { 
                        icon: createMarkerIcon(pinColor, isFastest), 
                        zIndexOffset: zIndex 
                    }).bindPopup(`<b>${isFastest ? '🏆 FASTEST: ' : ''}${st.name}</b><br>${st.distance_km} km`)
                      .addTo(routewiseMarkersGroup);
                    
                    marker.on('click', function() {
                        drawRouteOnSideMap(st.name, st.address, st.latitude, st.longitude, false);
                    });
                    
                    mapBounds.push([st.latitude, st.longitude]);
                });

                routewiseMap.fitBounds(mapBounds, { padding: [50, 50] });
            } else {
                document.getElementById('resultStationName').textContent = "No stations found";
                document.getElementById('resultStationAddress').textContent = "";
            }
        })
        .catch(err => {
            console.error("Loading error:", err);
            document.getElementById('resultStationName').textContent = "Connection Error";
            document.getElementById('resultStationAddress').textContent = "Could not fetch station data.";
        });
}

function drawRouteOnSideMap(name, address, lat, lon, isFastest) {
    const routeCard = document.getElementById('mapRouteCard');
    const badge = document.getElementById('routeBadge');
    
    document.getElementById('resultStationName').textContent = name;
    document.getElementById('resultStationAddress').textContent = address || "";
    document.getElementById('routeDistance').textContent = "Calc...";
    document.getElementById('routeDuration').textContent = "--";
    routeCard.style.display = 'block';

    if (isFastest) {
        badge.textContent = "🏆 FASTEST TRAFFIC ROUTE";
        badge.style.color = "#10b981";
    } else {
        badge.textContent = "⚡ ALTERNATIVE ROUTE";
        badge.style.color = "#f59e0b";
    }

    if (routewisePolyline) {
        routewiseMap.removeLayer(routewisePolyline);
        routewisePolyline = null;
    }

    fetch(`/calculate-route?origin_lat=${userCoords.lat}&origin_lon=${userCoords.lon}&dest_lat=${lat}&dest_lon=${lon}`)
        .then(res => res.json())
        .then(routeData => {
            if (routeData.success && routeData.points && routeData.points.length > 0) {
                const routePoints = routeData.points.map(p => [p.lat, p.lon]);

                const timeText = routeData.traffic_delay_minutes > 0 
                    ? `${routeData.travel_time_minutes} mins (+${routeData.traffic_delay_minutes}m traffic)` 
                    : `${routeData.travel_time_minutes} mins`;

                document.getElementById('routeDistance').textContent = `${routeData.distance_km} km`;
                document.getElementById('routeDuration').textContent = timeText;

                routewisePolyline = L.polyline(routePoints, {
                    color: '#38bdf8', 
                    weight: 6, 
                    opacity: 0.9, 
                    lineCap: 'round', 
                    lineJoin: 'round'
                }).addTo(routewiseMap);
                
                routewiseMap.fitBounds(routewisePolyline.getBounds(), { padding: [60, 60] });
            }
        })
        .catch(err => console.error("Routing error:", err));
}

document.addEventListener('DOMContentLoaded', () => {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (pos) => { userCoords.lat = pos.coords.latitude; userCoords.lon = pos.coords.longitude; }
        );
    }
    safeRangeKm = (appConfig.cppRouteData && appConfig.cppRouteData.safe_range) ? appConfig.cppRouteData.safe_range : 65;

    const initialTab = document.body.getAttribute('data-active-tab') || 'vehicle';
    switchTab(initialTab);
});