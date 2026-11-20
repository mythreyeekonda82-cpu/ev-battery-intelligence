(function () {
    "use strict";

    function token() {
        return localStorage.getItem("voltiq_token") ||
               localStorage.getItem("access_token") ||
               "";
    }

    function batteryId() {
        let id =
            localStorage.getItem("voltiq_battery_id") ||
            localStorage.getItem("selectedBatteryId") ||
            localStorage.getItem("voltiq_vehicle_id") ||
            "EV-001";

        id = id.toUpperCase();

        if (id.startsWith("EV-")) {
            id = id.replace("EV-", "BAT-");
        }

        return id;
    }

    async function api(url, options = {}) {
        const response = await fetch(url, {
            ...options,
            headers: {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + token(),
                ...(options.headers || {})
            }
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "Request failed."
            );
        }

        return data;
    }

    function addStyles() {
        if (document.getElementById("voltiqAddonStyles")) return;

        const link = document.createElement("link");
        link.id = "voltiqAddonStyles";
        link.rel = "stylesheet";
        link.href = "/voltiq-assistant.css";

        document.head.appendChild(link);
    }

    function addPanel() {
        const content = document.getElementById("pageContent");

        if (!content) return;

        if (document.getElementById("voltiqAddonPanel")) return;

        const panel = document.createElement("section");

        panel.id = "voltiqAddonPanel";
        panel.innerHTML = `
            <div class="vi-addon-grid">

                <div class="vi-addon-card">
                    <div class="vi-addon-heading">
                        <div>
                            <span class="vi-addon-label">AI ASSISTANT</span>
                            <h2>Ask VoltIQ</h2>
                            <p>Ask questions about your selected battery.</p>
                        </div>
                        <span class="vi-addon-icon">✦</span>
                    </div>

                    <div id="viChatMessages" class="vi-chat-messages">
                        <div class="vi-chat-bot">
                            Hello! Ask me about battery health, charge,
                            temperature, voltage, range or maintenance.
                        </div>
                    </div>

                    <form id="viChatForm" class="vi-chat-form">
                        <input
                            id="viChatInput"
                            placeholder="Ask about your battery..."
                            maxlength="1000"
                            required
                        >
                        <button type="submit">Send</button>
                    </form>
                </div>

                <div class="vi-addon-card">
                    <span class="vi-addon-label">GPS LOCATION</span>
                    <h2>Nearby Charging Stations</h2>
                    <p>Find the nearest demonstration charging stations.</p>

                    <button id="viLocateButton" class="vi-addon-button">
                        📍 Find Nearby Stations
                    </button>

                    <div id="viLocationStatus" class="vi-location-status">
                        Location has not been requested.
                    </div>

                    <div id="viStationResults"></div>
                </div>

                <div class="vi-addon-card">
                    <span class="vi-addon-label">BATTERY REPORT</span>
                    <h2>WhatsApp Health Report</h2>
                    <p>Send the current battery summary through WhatsApp.</p>

                    <input
                        id="viWhatsappNumber"
                        placeholder="Country code + phone number"
                        type="tel"
                    >

                    <button id="viWhatsappButton" class="vi-addon-button">
                        Send WhatsApp Report
                    </button>

                    <div id="viWhatsappStatus" class="vi-location-status"></div>
                </div>

            </div>
        `;

        content.appendChild(panel);

        document.getElementById("viChatForm")
            .addEventListener("submit", sendChat);

        document.getElementById("viLocateButton")
            .addEventListener("click", findStations);

        document.getElementById("viWhatsappButton")
            .addEventListener("click", sendWhatsAppReport);
    }

    function addMessage(message, type) {
        const box = document.getElementById("viChatMessages");

        if (!box) return;

        const item = document.createElement("div");

        item.className =
            type === "user" ? "vi-chat-user" : "vi-chat-bot";

        item.textContent = message;

        box.appendChild(item);
        box.scrollTop = box.scrollHeight;
    }

    async function sendChat(event) {
        event.preventDefault();

        const input = document.getElementById("viChatInput");
        const question = input.value.trim();

        if (!question) return;

        input.value = "";

        addMessage(question, "user");

        try {
            const result = await api("/api/voltiq/chat", {
                method: "POST",
                body: JSON.stringify({
                    battery_id: batteryId(),
                    question: question
                })
            });

            addMessage(result.answer, "bot");

        } catch (error) {
            addMessage("Unable to answer: " + error.message, "bot");
        }
    }

    function findStations() {
        const status = document.getElementById("viLocationStatus");
        const results = document.getElementById("viStationResults");

        if (!navigator.geolocation) {
            status.textContent = "GPS is not supported by this browser.";
            return;
        }

        status.textContent = "Getting your location...";
        results.innerHTML = "";

        navigator.geolocation.getCurrentPosition(
            async function (position) {
                try {
                    const latitude = position.coords.latitude;
                    const longitude = position.coords.longitude;

                    status.textContent =
                        "Location received. Finding nearest stations...";

                    const query =
                        "/api/voltiq/stations?latitude=" +
                        encodeURIComponent(latitude) +
                        "&longitude=" +
                        encodeURIComponent(longitude) +
                        "&limit=5";

                    const data = await api(query);

                    status.textContent =
                        "Showing demonstration station data. Availability is not live-verified.";

                    if (!data.stations.length) {
                        results.textContent = "No stations found.";
                        return;
                    }

                    results.innerHTML = data.stations.map(station => `
                        <div class="vi-station">
                            <strong>${escapeHTML(station.name)}</strong>
                            <span>${station.distance_km} km away</span>
                            <small>
                                ${escapeHTML(station.charger_type)}
                                · ${station.power_kw} kW
                                · ${station.available ? "Listed available" : "Listed unavailable"}
                            </small>
                            <a
                                target="_blank"
                                rel="noopener"
                                href="https://www.google.com/maps/dir/?api=1&destination=${station.latitude},${station.longitude}"
                            >
                                Directions →
                            </a>
                        </div>
                    `).join("");

                } catch (error) {
                    status.textContent = error.message;
                }
            },
            function (error) {
                status.textContent =
                    "Location unavailable: " + error.message;
            },
            {
                enableHighAccuracy: true,
                timeout: 15000,
                maximumAge: 30000
            }
        );
    }

    async function sendWhatsAppReport() {
        const number =
            document.getElementById("viWhatsappNumber").value.trim();

        const status =
            document.getElementById("viWhatsappStatus");

        if (!number) {
            status.textContent = "Enter a WhatsApp number with country code.";
            return;
        }

        if (!/^\+?[1-9]\d{7,14}$/.test(number)) {
            status.textContent = "Enter a valid international phone number.";
            return;
        }

        const button = document.getElementById("viWhatsappButton");
        button.disabled = true;
        status.textContent = "Sending report...";

        try {
            const response = await api(
                "/api/advanced-intelligence/" +
                encodeURIComponent(batteryId())
            );

            const data = response.data || {};

            const message = [
                "⚡ VoltIQ Battery Health Report",
                "Battery: " + batteryId(),
                "Date: " + new Date().toLocaleString(),
                "",
                "Predictive Battery Health: " +
                    JSON.stringify(data.predictive_battery_health || {}),
                "Remaining Useful Life: " +
                    JSON.stringify(data.remaining_useful_life || {}),
                "AI Anomaly Detection: " +
                    JSON.stringify(data.ai_anomaly_detection || {}),
                "Smart Charging: " +
                    JSON.stringify(data.smart_charging_optimization || {}),
                "Degradation Forecast: " +
                    JSON.stringify(data.battery_degradation_forecast || {}),
                "Maintenance: " +
                    JSON.stringify(data.intelligent_maintenance_prediction || {}),
                "Driving Range: " +
                    JSON.stringify(data.driving_range_prediction || {}),
                "",
                "Generated by VoltIQ. Estimates are not certified diagnostics."
            ].join("\n");

            const result = await api("/api/notifications/whatsapp", {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                body:
                    "whatsapp=" + encodeURIComponent(number) +
                    "&message=" + encodeURIComponent(message)
            });

            status.textContent =
                result.status === "sent"
                    ? "WhatsApp report sent successfully."
                    : "WhatsApp response received.";

        } catch (error) {
            status.textContent =
                "Unable to send: " + error.message;
        } finally {
            button.disabled = false;
        }
    }

    function escapeHTML(value) {
        return String(value).replace(/[&<>"']/g, function (character) {
            return {
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#039;"
            }[character];
        });
    }

   function integrate() {
    addStyles();

    if (typeof window.renderPage !== "function") {
        return false;
    }

    if (window.renderPage.__voltiqAddon) {
        return true;
    }

    const originalRenderPage = window.renderPage;

    function wrappedRenderPage(page) {
        const result = originalRenderPage.apply(this, arguments);

        if (String(page).toLowerCase() === "overview") {
            setTimeout(addPanel, 100);
        }

        return result;
    }

    wrappedRenderPage.__voltiqAddon = true;
    window.renderPage = wrappedRenderPage;

    return true;
}
    let attempts = 0;

    const timer = setInterval(function () {
        attempts++;

        if (integrate() || attempts >= 30) {
            clearInterval(timer);
        }
    }, 300);

})();