const locationBtn = document.getElementById("locationBtn");
const addressBtn = document.getElementById("addressBtn");

const locationName = document.getElementById("locationName");
const locationStatus = document.getElementById("locationStatus");

const latitudeInput = document.getElementById("latitude");
const longitudeInput = document.getElementById("longitude");


// ============================================================
// USE CURRENT LOCATION
// ============================================================

locationBtn.addEventListener("click", function () {

    if (!navigator.geolocation) {
        locationName.textContent = "Location not supported";
        locationStatus.textContent =
            "Your browser does not support location detection.";
        return;
    }

    locationName.textContent = "Detecting location...";
    locationStatus.textContent =
        "Please allow location access in your browser.";

    navigator.geolocation.getCurrentPosition(

        async function (position) {

            const latitude = position.coords.latitude;
            const longitude = position.coords.longitude;

            // Store coordinates secretly
            latitudeInput.value = latitude;
            longitudeInput.value = longitude;

            try {

                const response = await fetch(
                    `https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}&zoom=18&addressdetails=1`
                );

                const result = await response.json();

                if (result.display_name) {

                    locationName.textContent =
                        "📍 " + result.display_name;

                    locationStatus.textContent =
                        "Current location detected successfully.";

                } else {

                    locationName.textContent =
                        "📍 Current Location";

                    locationStatus.textContent =
                        "Location detected successfully.";

                }

            } catch (error) {

                locationName.textContent =
                    "📍 Current Location";

                locationStatus.textContent =
                    "Location detected, but address could not be loaded.";

            }

            locationBtn.textContent =
                "✓ Current Location Selected";

        },

        function (error) {

            locationName.textContent =
                "Location not detected";

            locationStatus.textContent =
                "Please allow location access and try again.";

        }

    );

});


// ============================================================
// MANUAL ADDRESS
// ============================================================

addressBtn.addEventListener("click", async function () {

    const address =
        document.getElementById("address").value.trim();

    if (!address) {

        locationName.textContent =
            "No address entered";

        locationStatus.textContent =
            "Please enter an address.";

        return;
    }

    locationName.textContent =
        "Searching address...";

    locationStatus.textContent =
        "Finding your location.";


    try {

        const response = await fetch(
            `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(address)}&limit=1`
        );

        const results = await response.json();


        if (results.length === 0) {

            locationName.textContent =
                "Address not found";

            locationStatus.textContent =
                "Try entering a more specific address.";

            return;
        }


        const result = results[0];


        // Store coordinates secretly

        latitudeInput.value = result.lat;
        longitudeInput.value = result.lon;


        // Show address to user

        locationName.textContent =
            "📍 " + result.display_name;

        locationStatus.textContent =
            "Address selected successfully.";

        addressBtn.textContent =
            "✓ Address Selected";

    }

    catch (error) {

        locationName.textContent =
            "Unable to find address";

        locationStatus.textContent =
            "Please check your internet connection.";

    }

});