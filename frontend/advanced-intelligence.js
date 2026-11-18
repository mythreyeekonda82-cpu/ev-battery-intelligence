/*
 * VoltIQ Advanced Battery Intelligence
 *
 * Displays:
 * 1. Predictive Battery Health
 * 2. Remaining Useful Life
 * 3. AI Anomaly Detection
 * 4. Smart Charging Optimization
 * 5. Battery Degradation Forecasting
 * 6. Intelligent Maintenance Prediction
 * 7. Driving Range Prediction
 * 8. Fleet Intelligence
 *
 * This module is separate from the existing battery-intelligence.js.
 */

(function () {
    "use strict";

    const API_BASE = "/api/advanced-intelligence";
    const REFRESH_INTERVAL = 15000;

    let refreshTimer = null;
    let isLoading = false;

    // -----------------------------------------------------
    // AUTHENTICATION
    // -----------------------------------------------------

    function getToken() {
        return (
            localStorage.getItem("voltiq_token") ||
            localStorage.getItem("access_token") ||
            ""
        );
    }

    // -----------------------------------------------------
    // BATTERY IDENTIFICATION
    // -----------------------------------------------------

    function getBatteryId() {
        let id =
            localStorage.getItem("selectedBatteryId") ||
            localStorage.getItem("selectedVehicleId") ||
            localStorage.getItem("selectedVehicle") ||
            "EV-001";

        id = String(id).trim().toUpperCase();

        if (id.startsWith("EV-")) {
            id = id.replace("EV-", "BAT-");
        }

        return id;
    }

    // -----------------------------------------------------
    // API REQUEST
    // -----------------------------------------------------

    async function apiRequest(endpoint) {
        const token = getToken();

        if (!token) {
            throw new Error("Please log in to view advanced intelligence.");
        }

        const response = await fetch(API_BASE + endpoint, {
            method: "GET",
            headers: {
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json"
            }
        });

        if (response.status === 401) {
            throw new Error("Your session has expired. Please log in again.");
        }

        if (response.status === 403) {
            throw new Error("You do not have permission to view this battery.");
        }

        const result = await response.json();

        if (!response.ok) {
            throw new Error(
                result.detail || "Unable to load advanced intelligence."
            );
        }

        return result.data !== undefined ? result.data : result;
    }

    // -----------------------------------------------------
    // HTML HELPERS
    // -----------------------------------------------------

    function escapeHTML(value) {
        return String(value ?? "").replace(/[&<>"']/g, function (char) {
            const replacements = {
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#039;"
            };

            return replacements[char];
        });
    }

    function displayValue(value, suffix = "") {
        if (value === null || value === undefined || value === "") {
            return "Not available";
        }

        if (typeof value === "number") {
            return escapeHTML(value.toFixed(2) + suffix);
        }

        return escapeHTML(value + suffix);
    }

    function listHTML(items) {
        if (!Array.isArray(items) || items.length === 0) {
            return "<p class='vi-muted'>No recommendations or events.</p>";
        }

        return `
            <ul class="vi-list">
                ${items.map(item => {
                    if (typeof item === "string") {
                        return `<li>${escapeHTML(item)}</li>`;
                    }

                    const label =
                        item.action ||
                        item.reason ||
                        item.parameter ||
                        JSON.stringify(item);

                    const priority = item.priority
                        ? `<span class="vi-priority">${escapeHTML(item.priority)}</span>`
                        : "";

                    return `<li>${priority}${escapeHTML(label)}</li>`;
                }).join("")}
            </ul>
        `;
    }

    function createCard(title, content, description = "") {
        return `
            <article class="vi-advanced-card">
                <h3>${escapeHTML(title)}</h3>
                ${description
                    ? `<p class="vi-card-description">${escapeHTML(description)}</p>`
                    : ""}
                <div class="vi-card-content">${content}</div>
            </article>
        `;
    }

    // -----------------------------------------------------
    // FEATURE CARD RENDERING
    // -----------------------------------------------------

    function renderPredictiveHealth(feature) {
        if (!feature || !feature.available) {
            return createCard(
                "Predictive Battery Health",
                `<p>${escapeHTML(feature?.message || "Data unavailable.")}</p>`
            );
        }

        const predictions = feature.predictions || {};

        const content = `
            <div class="vi-main-metric">
                ${displayValue(feature.current_soh, "%")}
            </div>
            <p>Current SOH</p>
            <div class="vi-metric-grid">
                <div>30 days: <strong>${displayValue(predictions["30_days"], "%")}</strong></div>
                <div>90 days: <strong>${displayValue(predictions["90_days"], "%")}</strong></div>
                <div>180 days: <strong>${displayValue(predictions["180_days"], "%")}</strong></div>
                <div>365 days: <strong>${displayValue(predictions["365_days"], "%")}</strong></div>
            </div>
            <p class="vi-muted">${escapeHTML(feature.message || "")}</p>
        `;

        return createCard("Predictive Battery Health", content);
    }

    function renderRUL(feature) {
        if (!feature || !feature.available) {
            return createCard(
                "Remaining Useful Life",
                `<p>${escapeHTML(feature?.message || "Insufficient data.")}</p>`
            );
        }

        return createCard(
            "Remaining Useful Life",
            `
                <div class="vi-main-metric">
                    ${displayValue(feature.estimated_years, " years")}
                </div>
                <p>Estimated remaining life</p>
                <p>${displayValue(feature.estimated_days, " days")}</p>
                <p class="vi-muted">${escapeHTML(feature.message || "")}</p>
            `
        );
    }

    function renderAnomalies(feature) {
        if (!feature) {
            return createCard("AI Anomaly Detection", "<p>Data unavailable.</p>");
        }

        return createCard(
            "AI Anomaly Detection",
            `
                <div class="vi-main-metric">
                    ${displayValue(feature.anomaly_count)}
                </div>
                <p>Unusual readings detected</p>
                ${listHTML(feature.anomalies)}
            `
        );
    }

    function renderCharging(feature) {
        if (!feature || !feature.available) {
            return createCard(
                "Smart Charging Optimization",
                `<p>${escapeHTML(feature?.message || "Data unavailable.")}</p>`
            );
        }

        return createCard(
            "Smart Charging Optimization",
            `
                <div class="vi-main-metric">
                    ${displayValue(feature.current_soc, "%")}
                </div>
                <p>Current state of charge</p>
                ${listHTML(feature.recommendations)}
                <p class="vi-muted">${escapeHTML(feature.note || "")}</p>
            `
        );
    }

    function renderDegradation(feature) {
        if (!feature || !feature.available) {
            return createCard(
                "Battery Degradation Forecast",
                `<p>${escapeHTML(feature?.message || "More history required.")}</p>`
            );
        }

        return createCard(
            "Battery Degradation Forecast",
            `
                <div class="vi-main-metric">
                    ${displayValue(feature.estimated_annual_change, "%")}
                </div>
                <p>Estimated annual SOH change</p>
                <p>Trend: <strong>${escapeHTML(feature.trend)}</strong></p>
                <p class="vi-muted">Based on historical SOH readings.</p>
            `
        );
    }

    function renderMaintenance(feature) {
        if (!feature || !feature.available) {
            return createCard(
                "Intelligent Maintenance Prediction",
                "<p>Maintenance data unavailable.</p>"
            );
        }

        return createCard(
            "Intelligent Maintenance Prediction",
            listHTML(feature.recommendations)
        );
    }

    function renderRange(feature) {
        if (!feature || !feature.available) {
            return createCard(
                "Driving Range Prediction",
                `<p>${escapeHTML(feature?.message || "Range data unavailable.")}</p>`
            );
        }

        return createCard(
            "Driving Range Prediction",
            `
                <div class="vi-main-metric">
                    ${displayValue(feature.estimated_range_km, " km")}
                </div>
                <p>Estimated remaining driving range</p>
                <p>Remaining energy: ${displayValue(feature.remaining_energy_kwh, " kWh")}</p>
                <p class="vi-muted">${escapeHTML(feature.note || "")}</p>
            `
        );
    }

    function renderFleet(feature) {
        if (!feature) {
            return createCard("Fleet Intelligence", "<p>Fleet data unavailable.</p>");
        }

        const batteries = feature.batteries || [];

        return createCard(
            "Fleet Intelligence",
            `
                <div class="vi-main-metric">
                    ${displayValue(feature.battery_count)}
                </div>
                <p>Batteries in fleet</p>
                <p>Average SOH: ${displayValue(feature.average_soh, "%")}</p>
                <div class="vi-fleet-list">
                    ${batteries.slice(0, 10).map(item => `
                        <div class="vi-fleet-row">
                            <strong>${escapeHTML(item.battery_id)}</strong>
                            <span>${displayValue(item.soh, "%")} SOH</span>
                            <span>${escapeHTML(item.status || "Unknown")}</span>
                        </div>
                    `).join("")}
                </div>
            `
        );
    }

    // -----------------------------------------------------
    // CONNECTION STATUS
    // -----------------------------------------------------

    function renderConnectionStatus(data) {
        const status = data.connection_status || "unknown";
        const source = data.data_source || "unknown";

        let label = "Unknown";
        let description = "Data source could not be identified.";

        if (status === "connected" && source === "hardware") {
            label = "Hardware Connected";
            description = "Fresh ESP32 telemetry is being used.";
        } else if (source === "simulator") {
            label = "Demo Simulator";
            description = "Displaying simulated readings. Hardware is not confirmed connected.";
        } else if (status === "stale") {
            label = "Telemetry Stale";
            description = "Showing the latest stored historical reading.";
        } else if (status === "disconnected") {
            label = "Hardware Disconnected";
            description = "Live hardware telemetry is not available.";
        }

        return `
            <div class="vi-connection-status">
                <strong>${escapeHTML(label)}</strong>
                <span>${escapeHTML(description)}</span>
            </div>
        `;
    }

    // -----------------------------------------------------
    // MAIN RENDERER
    // -----------------------------------------------------

    function renderAdvancedIntelligence(data) {
        if (!data || !data.available) {
            return `
                <div class="vi-advanced-error">
                    ${escapeHTML(data?.message || "Advanced intelligence is unavailable.")}
                </div>
            `;
        }

        const current = data.current_reading || {};

        return `
            ${renderConnectionStatus(data)}

            <div class="vi-current-readings">
                <div><span>Voltage</span><strong>${displayValue(current.voltage, " V")}</strong></div>
                <div><span>Current</span><strong>${displayValue(current.current, " A")}</strong></div>
                <div><span>Temperature</span><strong>${displayValue(current.temperature, " °C")}</strong></div>
                <div><span>SOC</span><strong>${displayValue(current.soc, "%")}</strong></div>
                <div><span>SOH</span><strong>${displayValue(current.soh, "%")}</strong></div>
                <div><span>Risk Index</span><strong>${displayValue(data.battery_risk_index?.score)}</strong></div>
            </div>

            <div class="vi-advanced-grid">
                ${renderPredictiveHealth(data.predictive_battery_health)}
                ${renderRUL(data.remaining_useful_life)}
                ${renderAnomalies(data.ai_anomaly_detection)}
                ${renderCharging(data.smart_charging_optimization)}
                ${renderDegradation(data.battery_degradation_forecast)}
                ${renderMaintenance(data.intelligent_maintenance_prediction)}
                ${renderRange(data.driving_range_prediction)}
                ${renderFleet(data.fleet_intelligence)}
            </div>

            <p class="vi-last-updated">
                Updated: ${escapeHTML(data.generated_at || "Unknown")}
            </p>
        `;
    }

    // -----------------------------------------------------
    // LOAD AND REFRESH
    // -----------------------------------------------------

    async function refreshAdvancedIntelligence() {
        if (isLoading) return;

        const container = document.getElementById("viAdvancedIntelligence");

        if (!container) return;

        isLoading = true;

        try {
            const batteryId = getBatteryId();

            container.innerHTML = "<p>Loading advanced battery intelligence...</p>";

            const data = await apiRequest(
                "/" + encodeURIComponent(batteryId)
            );

            container.innerHTML = renderAdvancedIntelligence(data);

        } catch (error) {
            container.innerHTML = `
                <div class="vi-advanced-error">
                    ${escapeHTML(error.message || "Unable to load intelligence.")}
                </div>
                <button type="button" id="viAdvancedRetry">Retry</button>
            `;

            const retry = document.getElementById("viAdvancedRetry");

            if (retry) {
                retry.addEventListener("click", refreshAdvancedIntelligence);
            }

        } finally {
            isLoading = false;
        }
    }

    // -----------------------------------------------------
    // ATTACH TO BATTERY PAGE
    // -----------------------------------------------------

    function attachAdvancedIntelligence() {
        const page = document.querySelector(
            "#mainContent, #main-content, main, .main-content"
        );

        if (!page) return;

        if (document.getElementById("viAdvancedSection")) return;

        const section = document.createElement("section");

        section.id = "viAdvancedSection";
        section.className = "vi-advanced-section";

        section.innerHTML = `
            <div class="vi-advanced-heading">
                <div>
                    <h2>Advanced Battery Intelligence</h2>
                    <p>Predictive insights and fleet intelligence</p>
                </div>

                <button type="button" id="viAdvancedRefresh">
                    Refresh
                </button>
            </div>

            <div id="viAdvancedIntelligence">
                <p>Loading advanced battery intelligence...</p>
            </div>
        `;

        page.appendChild(section);

        document.getElementById("viAdvancedRefresh")
            ?.addEventListener("click", refreshAdvancedIntelligence);

        refreshAdvancedIntelligence();
    }

    // -----------------------------------------------------
    // PUBLIC FUNCTIONS
    // -----------------------------------------------------

    window.VoltIQAdvanced = {
        refresh: refreshAdvancedIntelligence,
        attach: attachAdvancedIntelligence
    };

    // -----------------------------------------------------
    // PAGE DETECTION
    // -----------------------------------------------------

    function initialise() {
        const currentPage = String(
            window.page ||
            window.currentPage ||
            ""
        ).toLowerCase();

        if (
            currentPage.includes("battery") ||
            currentPage.includes("monitor")
        ) {
            attachAdvancedIntelligence();
        }

        if (refreshTimer) {
            clearInterval(refreshTimer);
        }

        refreshTimer = setInterval(function () {
            if (document.getElementById("viAdvancedSection")) {
                refreshAdvancedIntelligence();
            }
        }, REFRESH_INTERVAL);
    }

    document.addEventListener("DOMContentLoaded", initialise);

    // Also expose initialisation for the existing app renderer.
    window.addEventListener("load", initialise);

})();