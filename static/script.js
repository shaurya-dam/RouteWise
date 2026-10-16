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

function switchTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.add('hidden');
    });

    const targetTab = document.getElementById('tab-' + tabName);
    if (targetTab) {
        targetTab.classList.remove('hidden');
    }

    document.querySelectorAll('.step').forEach(step => {
        step.classList.remove('active');
    });

    const tabMap = {
        'vehicle': 0,
        'energy': 1,
        'location': 2,
        'result': 3
    };

    const stepIndex = tabMap[tabName];
    if (stepIndex !== undefined) {
        document.querySelectorAll('.step')[stepIndex].classList.add('active');
    }
}

window.addEventListener('DOMContentLoaded', function() {
    const activeTab = document.body.dataset.activeTab || 'vehicle';
    switchTab(activeTab);
});