"use strict";

/* =========================================================
   VOLTIQ — BACKEND BATTERY INTELLIGENCE INTEGRATION

   Connects the six Battery Intelligence features to FastAPI.

   Existing app.js, login, reports, fleet and ESP32 code
   remain unchanged.

========================================================= */

const VOLTIQ_API = {
    base: "/api/battery-intelligence",
    loading: false,
    lastData: null,
    error: null
};


/* ================= HELPERS ================= */

function viEscape(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[char]);
}

function viNumber(value, decimals = 1) {
    const number = Number(value);

    return Number.isFinite(number)
        ? number.toFixed(decimals)
        : "—";
}

function viBatteryId() {
    const vehicle = String(
        typeof selectedVehicleId !== "undefined"
            ? selectedVehicleId
            : ""
    );

    if (!vehicle) return null;

    if (vehicle.startsWith("BAT-")) return vehicle;

    if (vehicle.startsWith("EV-")) {
        return vehicle.replace("EV-", "BAT-");
    }

    return "BAT-" + vehicle;
}

function viToken() {
    return localStorage.getItem("voltiq_token");
}

async function viRequest(path, options = {}) {
    const token = viToken();

    if (!token) {
        throw new Error("Please log in again.");
    }

    const response = await fetch(
        VOLTIQ_API.base + path,
        {
            ...options,
            headers: {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + token,
                ...(options.headers || {})
            },
            cache: "no-store"
        }
    );

    let result;

    try {
        result = await response.json();
    } catch {
        result = {};
    }

    if (!response.ok) {
        throw new Error(
            result.detail ||
            "Battery Intelligence API error: HTTP " + response.status
        );
    }

    return result;
}

function viStatusClass(value) {
    const status = String(value || "").toUpperCase();

    if (
        status.includes("CRITICAL") ||
        status.includes("UNRELIABLE") ||
        status.includes("FAILED")
    ) return "critical";

    if (
        status.includes("WARNING") ||
        status.includes("CHECK") ||
        status.includes("PARTIAL")
    ) return "warning";

    return "healthy";
}

function viCard(title, value, description, status = "healthy") {
    return `
        <article class="feature-card">
            <label>${viEscape(title)}</label>
            <span class="big">${viEscape(value)}</span>
            <h3>
                <span class="status ${viStatusClass(status)}">
                    ${viEscape(status)}
                </span>
            </h3>
            <p>${viEscape(description)}</p>
        </article>
    `;
}


/* ================= LOAD ALL SIX FEATURES ================= */

async function viLoadAll() {
    const batteryId = viBatteryId();

    if (!batteryId) {
        throw new Error("Select a vehicle first.");
    }

    VOLTIQ_API.loading = true;
    VOLTIQ_API.error = null;

    const requests = await Promise.allSettled([
        viRequest("/risk/" + encodeURIComponent(batteryId)),
        viRequest("/sensor-reliability/" + encodeURIComponent(batteryId)),
        viRequest("/stress/" + encodeURIComponent(batteryId), {
            method: "POST"
        }),
        viRequest("/recovery/" + encodeURIComponent(batteryId)),
        viRequest("/events?battery_id=" + encodeURIComponent(batteryId)),
        viRequest("/overview")
    ]);

    VOLTIQ_API.loading = false;

    const names = [
        "risk",
        "sensor",
        "stress",
        "recovery",
        "events",
        "overview"
    ];

    const data = {};

    requests.forEach((result, index) => {
        data[names[index]] = result.status === "fulfilled"
            ? result.value
            : {
                success: false,
                error: result.reason?.message || "Request failed"
            };
    });

    VOLTIQ_API.lastData = data;

    return data;
}


/* ================= RENDER BACKEND RESULTS ================= */

function viRenderResults(data) {
    const root = document.getElementById("viBackendResults");

    if (!root) return;

    const risk = data.risk?.data || {};
    const sensor = data.sensor || {};
    const stress = data.stress || {};
    const recovery = data.recovery || {};
    const events = data.events?.events || [];
    const overview = data.overview || {};

    const riskError = data.risk?.error;
    const sensorError = data.sensor?.error;
    const stressError = data.stress?.error;
    const recoveryError = data.recovery?.error;

    const errorMessages = [
        riskError,
        sensorError,
        stressError,
        recoveryError,
        data.events?.error,
        data.overview?.error
    ].filter(Boolean);

    root.innerHTML = `

        <div class="panel vi-api-panel">

            <div class="panel-head">
                <div>
                    <div class="eyebrow">BACKEND CONNECTED</div>
                    <h2>Battery Intelligence Results</h2>
                    <p>
                        Vehicle ${viEscape(viBatteryId())}
                        · Live API assessment
                    </p>
                </div>

                <button
                    class="primary-btn"
                    id="viRefreshButton"
                    type="button"
                >
                    ↻ Refresh Intelligence
                </button>
            </div>

            ${
                errorMessages.length
                    ? `
                        <div class="vi-error">
                            ${errorMessages.map(
                                viEscape
                            ).join("<br>")}
                        </div>
                    `
                    : `
                        <div class="vi-success">
                            ✓ Backend intelligence requests completed.
                        </div>
                    `
            }

            <div class="feature-grid">

                ${viCard(
                    "01 · BATTERY RISK INDEX",
                    risk.risk_score !== undefined
                        ? risk.risk_score + " / 100"
                        : riskError || "Unavailable",
                    risk.recommendation || risk.detail || "Risk assessment",
                    risk.risk_level || "UNAVAILABLE"
                )}

                ${viCard(
                    "02 · SENSOR RELIABILITY",
                    sensor.overall_status || sensorError || "Unavailable",
                    sensor.sensors
                        ? Object.entries(sensor.sensors)
                            .map(([name, item]) =>
                                name + ": " + item.status
                            ).join(" · ")
                        : "Sensor assessment",
                    sensor.overall_status || "UNAVAILABLE"
                )}

                ${viCard(
                    "03 · BATTERY STRESS ANALYSIS",
                    stress.stress_detected === true
                        ? "STRESS DETECTED"
                        : stress.stress_detected === false
                            ? "NO ACTIVE STRESS"
                            : stressError || "Unavailable",
                    stress.active_stress_conditions?.join(", ") ||
                        "No active stress conditions reported.",
                    stress.stress_detected
                        ? "WARNING"
                        : "HEALTHY"
                )}

                ${viCard(
                    "04 · RECOVERY TIME TRACKING",
                    recovery.active_count !== undefined
                        ? recovery.active_count + " active"
                        : recoveryError || "Unavailable",
                    recovery.completed_count !== undefined
                        ? recovery.completed_count + " completed recoveries"
                        : "Recovery tracking",
                    recovery.active_count > 0
                        ? "WARNING"
                        : "HEALTHY"
                )}

                ${viCard(
                    "05 · PROTECTION RESPONSE VERIFICATION",
                    "Ready",
                    "Run a verification using before-and-after readings below.",
                    "INFO"
                )}

                ${viCard(
                    "06 · BATTERY FAULT SIMULATOR",
                    "Ready",
                    "Select a fault scenario below to run a backend simulation.",
                    "INFO"
                )}

            </div>

        </div>


        <div class="panel">

            <div class="panel-head">
                <div>
                    <h2>Fault Simulator</h2>
                    <p>
                        Software-only fault simulation.
                        No physical battery controls are activated.
                    </p>
                </div>
            </div>

            <div class="vi-action-grid">

                <button class="vi-action-btn" data-vi-fault="overvoltage">
                    ⚡ Overvoltage
                </button>

                <button class="vi-action-btn" data-vi-fault="undervoltage">
                    ↓ Undervoltage
                </button>

                <button class="vi-action-btn" data-vi-fault="overcurrent">
                    ⇧ Overcurrent
                </button>

                <button class="vi-action-btn" data-vi-fault="overheating">
                    ♨ Overheating
                </button>

            </div>

            <div id="viFaultResult" class="vi-result-box">
                Select a fault scenario to see its simulation result.
            </div>

        </div>


        <div class="panel">

            <h2>Protection Response Verification</h2>

            <p class="muted">
                Enter readings before and after a protective action.
            </p>

            <div class="vi-form-grid">

                <div class="field">
                    <label>Protection action</label>
                    <input
                        id="viAction"
                        value="Cooling system activated"
                    >
                </div>

                <div class="field">
                    <label>Baseline voltage (V)</label>
                    <input id="viBeforeVoltage" type="number" value="460" step="0.1">
                </div>

                <div class="field">
                    <label>Baseline current (A)</label>
                    <input id="viBeforeCurrent" type="number" value="150" step="0.1">
                </div>

                <div class="field">
                    <label>Baseline temperature (°C)</label>
                    <input id="viBeforeTemperature" type="number" value="48" step="0.1">
                </div>

                <div class="field">
                    <label>After-action voltage (V)</label>
                    <input id="viAfterVoltage" type="number" value="400" step="0.1">
                </div>

                <div class="field">
                    <label>After-action current (A)</label>
                    <input id="viAfterCurrent" type="number" value="70" step="0.1">
                </div>

                <div class="field">
                    <label>After-action temperature (°C)</label>
                    <input id="viAfterTemperature" type="number" value="35" step="0.1">
                </div>

            </div>

            <button
                id="viVerifyButton"
                class="primary-btn"
                type="button"
            >
                Verify Protection Response
            </button>

            <div id="viProtectionResult" class="vi-result-box">
                No protection verification performed yet.
            </div>

        </div>


        <div class="panel">

            <div class="panel-head">
                <div>
                    <h2>Recovery History</h2>
                    <p>Recorded battery stress and recovery events.</p>
                </div>
            </div>

            ${
                recovery.completed_recoveries?.length
                    ? `
                        <div class="table-wrap">
                            <table class="data-table">
                                <thead>
                                    <tr>
                                        <th>EVENT</th>
                                        <th>RECOVERY TIME</th>
                                        <th>STATUS</th>
                                    </tr>
                                </thead>

                                <tbody>
                                    ${recovery.completed_recoveries.map(item => `
                                        <tr>
                                            <td>${viEscape(item.message)}</td>
                                            <td>${viNumber(item.recovery_time_seconds)} sec</td>
                                            <td>
                                                <span class="status healthy">
                                                    RECOVERED
                                                </span>
                                            </td>
                                        </tr>
                                    `).join("")}
                                </tbody>
                            </table>
                        </div>
                    `
                    : `
                        <p class="muted">
                            No completed recovery events recorded yet.
                        </p>
                    `
            }

        </div>


        <div class="panel">

            <div class="panel-head">
                <div>
                    <h2>Intelligence Event History</h2>
                    <p>Backend-stored battery intelligence events.</p>
                </div>

                <span class="mode-badge">
                    ${events.length} EVENTS
                </span>
            </div>

            ${
                events.length
                    ? `
                        <div class="table-wrap">
                            <table class="data-table">
                                <thead>
                                    <tr>
                                        <th>EVENT</th>
                                        <th>SEVERITY</th>
                                        <th>MESSAGE</th>
                                        <th>DATE</th>
                                    </tr>
                                </thead>

                                <tbody>
                                    ${events.map(event => `
                                        <tr>
                                            <td>${viEscape(event.event_type)}</td>
                                            <td>
                                                <span class="status ${viStatusClass(event.severity)}">
                                                    ${viEscape(event.severity)}
                                                </span>
                                            </td>
                                            <td>${viEscape(event.message)}</td>
                                            <td>${viEscape(event.created_at || "—")}</td>
                                        </tr>
                                    `).join("")}
                                </tbody>
                            </table>
                        </div>
                    `
                    : `
                        <p class="muted">
                            No intelligence events have been recorded yet.
                        </p>
                    `
            }

        </div>


        <div class="panel">
            <h2>Fleet Intelligence Summary</h2>

            <div class="stats-grid">

                ${`
                    <div class="stat-card">
                        <small>TOTAL EVENTS</small>
                        <strong>${overview.total_events ?? "—"}</strong>
                        <p>Stored intelligence events</p>
                    </div>

                    <div class="stat-card">
                        <small>ACTIVE STRESS</small>
                        <strong>${overview.active_stress_events ?? "—"}</strong>
                        <p>Unresolved stress events</p>
                    </div>

                    <div class="stat-card">
                        <small>FAULT SIMULATIONS</small>
                        <strong>${overview.fault_simulations ?? "—"}</strong>
                        <p>Recorded simulations</p>
                    </div>

                    <div class="stat-card">
                        <small>SENSOR WARNINGS</small>
                        <strong>${overview.sensor_warnings ?? "—"}</strong>
                        <p>Reliability warnings</p>
                    </div>
                `}

            </div>
        </div>

    `;

    const refreshButton = document.getElementById("viRefreshButton");

    if (refreshButton) {
        refreshButton.addEventListener("click", viRefresh);
    }

    root.querySelectorAll("[data-vi-fault]").forEach(button => {
        button.addEventListener("click", () => {
            viRunFault(button.dataset.viFault);
        });
    });

    const verifyButton = document.getElementById("viVerifyButton");

    if (verifyButton) {
        verifyButton.addEventListener("click", viVerifyProtection);
    }
}


/* ================= REFRESH ================= */

async function viRefresh() {
    const root = document.getElementById("viBackendResults");

    if (root) {
        root.innerHTML = `
            <div class="panel">
                <p class="muted">Loading backend intelligence...</p>
            </div>
        `;
    }

    try {
        const data = await viLoadAll();
        viRenderResults(data);
    } catch (error) {
        if (root) {
            root.innerHTML = `
                <div class="panel vi-error">
                    ${viEscape(error.message)}
                </div>
            `;
        }
    }
}


/* ================= FAULT SIMULATOR ================= */

async function viRunFault(type) {
    const output = document.getElementById("viFaultResult");

    if (output) {
        output.textContent = "Running fault simulation...";
    }

    try {
        const result = await viRequest(
            "/simulate/" + encodeURIComponent(viBatteryId()),
            {
                method: "POST",
                body: JSON.stringify({
                    fault_type: type
                })
            }
        );

        const data = result.data || {};

        if (output) {
            output.innerHTML = `
                <h3>${viEscape(data.fault_type || type).toUpperCase()}</h3>

                <p>
                    Risk score:
                    <strong>
                        ${viEscape(data.risk_assessment?.risk_score ?? "—")}
                    </strong>
                </p>

                <p>
                    Risk level:
                    <strong>
                        ${viEscape(data.risk_assessment?.risk_level ?? "—")}
                    </strong>
                </p>

                <p>
                    Recommendation:
                    ${viEscape(data.recommended_response || "—")}
                </p>

                <p class="muted">
                    Software simulation only.
                </p>
            `;
        }

        toast("Backend fault simulation completed.");

        await viRefresh();

    } catch (error) {
        if (output) {
            output.textContent = error.message;
        }
    }
}


/* ================= PROTECTION VERIFICATION ================= */

async function viVerifyProtection() {
    const output = document.getElementById("viProtectionResult");

    const number = id => {
        const value = Number(document.getElementById(id)?.value);

        if (!Number.isFinite(value)) {
            throw new Error("Please enter valid numeric readings.");
        }

        return value;
    };

    try {
        const payload = {
            action: document.getElementById("viAction").value.trim(),

            baseline_voltage: number("viBeforeVoltage"),
            baseline_current: number("viBeforeCurrent"),
            baseline_temperature: number("viBeforeTemperature"),

            after_voltage: number("viAfterVoltage"),
            after_current: number("viAfterCurrent"),
            after_temperature: number("viAfterTemperature")
        };

        if (!payload.action) {
            throw new Error("Enter a protection action.");
        }

        if (output) {
            output.textContent = "Verifying protection response...";
        }

        const result = await viRequest(
            "/protection/verify/" + encodeURIComponent(viBatteryId()),
            {
                method: "POST",
                body: JSON.stringify(payload)
            }
        );

        if (output) {
            output.innerHTML = `
                <h3>
                    ${viEscape(result.verification_result)}
                </h3>

                <p>
                    Before-action issues:
                    ${viEscape(
                        result.before_issues?.join(", ") || "None"
                    )}
                </p>

                <p>
                    After-action issues:
                    ${viEscape(
                        result.after_issues?.join(", ") || "None"
                    )}
                </p>

                <p class="muted">
                    ${viEscape(result.note || "")}
                </p>
            `;
        }

        toast("Protection verification recorded.");

        await viRefresh();

    } catch (error) {
        if (output) {
            output.textContent = error.message;
        }
    }
}


/* ================= INTEGRATE WITH EXISTING BATTERY PAGE ================= */

function viAttachPanel() {
    const pageContent = document.getElementById("pageContent");

    if (!pageContent) return;

    if (document.getElementById("viBackendResults")) return;

    const container = document.createElement("div");

    container.id = "viBackendResults";

    pageContent.appendChild(container);

    viRefresh();
}


/* ================= WRAP EXISTING PAGE RENDERER ================= */

(function integrateVoltIQ() {

    const originalRenderPage = window.renderPage;

    if (typeof originalRenderPage !== "function") {
        console.error(
            "VoltIQ integration: existing renderPage function not found."
        );
        return;
    }

    window.renderPage = function(which) {

        const result = originalRenderPage.apply(this, arguments);

        if (which === "battery") {
            setTimeout(viAttachPanel, 0);
        }

        return result;
    };

})();


/* ================= GLOBAL ACCESS ================= */

window.viRefresh = viRefresh;
window.viRunFault = viRunFault;
window.viVerifyProtection = viVerifyProtection;

console.log("VoltIQ backend Battery Intelligence integration loaded.");