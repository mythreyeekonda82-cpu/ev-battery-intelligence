"use strict";

/* =========================================================
   VOLTIQ — COMPLETE EV BATTERY INTELLIGENCE APPLICATION
   Admin: Fleet access
   User: Assigned vehicle access
   Both: All seven dashboard sections and six intelligence
   features.
========================================================= */

/* ================= GLOBAL STATE ================= */

const $ = id => document.getElementById(id);

let VOLTIQ_MODE = localStorage.getItem("voltiq_mode") || "DEMO";
let role = "user";
let userName = "VoltIQ User";
let page = "overview";
let timer = null;
let te
let fleetVehicles = [];
let selectedVehicleId = null;
let fleetError = "";
let fleetLoading = false;

let demoTick = 0;

// ESP32 readings come from the backend: the ESP32 posts to
// /api/telemetry/device and the dashboard reads them back. Empty means
// "the most recent device that has posted".
let deviceId = localStorage.getItem("voltiq_device_id") || "";

// Last ESP32 error shown, so polling every few seconds does not
// repeat the same toast.
let esp32LastError = "";

let telemetry = {
    voltage: VOLTIQ_MODE === "DEMO" ? 12.6 : null,
    current: VOLTIQ_MODE === "DEMO" ? 1.1 : null,
    temperature: VOLTIQ_MODE === "DEMO" ? 29.4 : null,
    soc: VOLTIQ_MODE === "DEMO" ? 82 : null,
    soh: VOLTIQ_MODE === "DEMO" ? 96 : null,
    power: VOLTIQ_MODE === "DEMO" ? 13.86 : null,
    charging: false,
    updated: null
};

let esp32Connected = false;
let esp32HasData = false;

// A reading older than this is shown as stale, not live.
const ESP32_STALE_MS = 60 * 1000;

/* ================= HELPERS ================= */

function fmt(value, decimals = 1) {
    const n = Number(value);
    return Number.isFinite(n) ? n.toFixed(decimals) : "—";
}

function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[c]);
}

function toast(message) {
    const el = $("toast");
    if (!el) {
        console.log(message);
        return;
    }

    el.textContent = message;
    el.classList.add("show");

    setTimeout(() => el.classList.remove("show"), 2600);
}

/* The demo fleet uses ~400 V traction packs, while an ESP32 bench rig
   reads a 12 V battery. Pick limits by voltage scale so neither is
   judged against the other's thresholds. Pack limits match the
   backend protection intelligence. */
function batteryLimits(voltage) {
    if (voltage !== null && voltage !== undefined && Number(voltage) > 60) {
        return {
            vCritLow: 330, vWarnLow: 350, vWarnHigh: 430, vCritHigh: 450,
            vLowSlope: 3.25, vHighSlope: 3.25,
            tWarn: 40, tCrit: 45,
            iNominal: 100, iMax: 145
        };
    }

    return {
        vCritLow: 11.3, vWarnLow: 11.8, vWarnHigh: 14.7, vCritHigh: 15,
        vLowSlope: 35, vHighSlope: 45,
        tWarn: 38, tCrit: 45,
        iNominal: 2.1, iMax: 5.67
    };
}

function batteryStatus(b) {
    const lim = batteryLimits(b.voltage);
    const has = value => value !== null && value !== undefined;

    // State of health limits match the backend (85% warning, 70% critical).
    if (
        (has(b.temperature) && b.temperature >= lim.tCrit) ||
        (has(b.voltage) && (b.voltage < lim.vCritLow || b.voltage > lim.vCritHigh)) ||
        (has(b.soh) && b.soh < 70)
    ) return "CRITICAL";

    if (
        (has(b.temperature) && b.temperature >= lim.tWarn) ||
        (has(b.voltage) && (b.voltage < lim.vWarnLow || b.voltage > lim.vWarnHigh)) ||
        (has(b.soc) && b.soc < 20) ||
        (has(b.soh) && b.soh < 85)
    ) return "WARNING";

    return "HEALTHY";
}

function status() {
    return batteryStatus(telemetry);
}

function getRisk() {
    if (typeof calculateBatteryRisk === "function") {
        return calculateBatteryRisk(telemetry);
    }

    return {
        score: "—",
        level: "Unavailable",
        detail: "Battery risk module unavailable"
    };
}

function getLab() {
    return typeof VOLTIQ_LAB !== "undefined"
        ? VOLTIQ_LAB
        : {
            events: [],
            active: null,
            protection: null,
            simulation: null
        };
}


/* ================= LOGIN ================= */

const loginForm = $("loginForm");

if (loginForm) {
    loginForm.addEventListener("submit", async event => {
        event.preventDefault();

        const email = $("loginEmail").value.trim().toLowerCase();
        const password = $("loginPassword").value;
        const message = $("loginMessage");

        message.textContent = "Signing in...";

        try {
            const response = await fetch("/api/auth/login", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    email,
                    password
                })
            });

            const data = await response.json();

            if (!response.ok) {
                message.textContent =
                    data.detail || "Incorrect email or password.";
                return;
            }

            if (!data.access_token || !data.user) {
                message.textContent = "Invalid server login response.";
                return;
            }

            localStorage.setItem("voltiq_token", data.access_token);
            localStorage.setItem("voltiq_user", JSON.stringify(data.user));

            role = String(data.user.role || "user").toLowerCase();
            userName =
                data.user.name ||
                data.user.email ||
                "VoltIQ User";

            await loadFleetVehicles();

            VOLTIQ_MODE =
                $("connectionMode")?.value ||
                localStorage.getItem("voltiq_mode") ||
                "DEMO";

            localStorage.setItem("voltiq_mode", VOLTIQ_MODE);

            $("loginScreen").classList.add("hidden");
            $("app").classList.remove("hidden");

            buildShell();

            if (fleetVehicles.length) {
                selectVehicleData(fleetVehicles[0]);
            }

            renderPage("overview");

            if (timer) clearInterval(timer);

            if (VOLTIQ_MODE === "ESP32") {
                await pollEsp32();
            }

            timer = setInterval(() => {
                if (VOLTIQ_MODE === "DEMO") {
                    updateDemo();
                } else {
                    pollEsp32();
                }
            }, 3000);

        } catch (error) {
            console.error(error);
            message.textContent =
                "Unable to connect to server. Check that the backend is running.";
        }
    });
}


/* ================= AUTHENTICATION ================= */

function getToken() {
    return localStorage.getItem("voltiq_token");
}

async function authenticatedFetch(url, options = {}) {
    const headers = {
        ...(options.headers || {}),
        "Authorization": `Bearer ${getToken()}`
    };

    return fetch(url, {
        ...options,
        headers
    });
}


/* ================= FLEET API ================= */

async function loadFleetVehicles() {
    fleetLoading = true;
    fleetError = "";

    try {
        const response = await authenticatedFetch("/api/vehicles", {
            method: "GET",
            cache: "no-store"
        });

        if (!response.ok) {
            throw new Error(`Vehicle API returned HTTP ${response.status}`);
        }

        const payload = await response.json();

        fleetVehicles = Array.isArray(payload)
            ? payload
            : Array.isArray(payload.vehicles)
                ? payload.vehicles
                : Array.isArray(payload.items)
                    ? payload.items
                    : [];

        if (payload.role) {
            role = String(payload.role).toLowerCase();
        }

        if (fleetVehicles.length) {
            const exists = fleetVehicles.some(
                (v, i) => vehicleId(v, i) === selectedVehicleId
            );

            if (!exists) {
                selectedVehicleId = vehicleId(fleetVehicles[0], 0);
            }
        }

    } catch (error) {
        fleetError = error.message;
        fleetVehicles = [];
        console.error("Fleet API error:", error);

    } finally {
        fleetLoading = false;
    }
}

function vehicleId(v, index = 0) {
    return String(
        v?.vehicle_id ||
        v?.vehicle_code ||
        v?.registration_number ||
        v?.id ||
        `EV-${String(index + 1).padStart(3, "0")}`
    );
}

function vehicleBattery(v) {
    const b =
        v?.battery ||
        v?.telemetry ||
        v?.latest_telemetry ||
        v?.latestTelemetry ||
        v ||
        {};

    return {
        voltage: numberOrNull(
            b.voltage ?? b.pack_voltage ?? b.voltage_v
        ),
        current: numberOrNull(
            b.current ?? b.current_a
        ),
        temperature: numberOrNull(
            b.temperature ?? b.temp ?? b.temperature_c
        ),
        soc: numberOrNull(
            b.soc ?? b.state_of_charge
        ),
        soh: numberOrNull(
            b.soh ?? b.state_of_health
        )
    };
}

function numberOrNull(value) {
    if (value === null || value === undefined || value === "") {
        return null;
    }

    const n = Number(value);
    return Number.isFinite(n) ? n : null;
}

function vehicleStatus(v) {
    return batteryStatus(vehicleBattery(v));
}

function selectVehicleData(v) {
    const b = vehicleBattery(v);

    selectedVehicleId =
        vehicleId(v, fleetVehicles.indexOf(v));

    Object.entries(b).forEach(([key, value]) => {
        if (value !== null) {
            telemetry[key] = value;
        }
    });

    telemetry.updated =
        v.updated_at ||
        v.updated ||
        new Date().toISOString();

    telemetry.power = telemetry.voltage * telemetry.current;
}

function selectFleetVehicle(encodedId) {
    const id = decodeURIComponent(encodedId);

    const index = fleetVehicles.findIndex(
        (v, i) => vehicleId(v, i) === id
    );

    if (index < 0) {
        toast("Vehicle not found.");
        return;
    }

    selectVehicleData(fleetVehicles[index]);
    renderPage("vehicle");
}


/* ================= DASHBOARD SHELL ================= */

function buildShell() {
    $("app").innerHTML = `
        <aside class="sidebar">

            <div class="side-brand">
                <div class="brand-icon">⚡</div>
                <div>
                    <strong>VoltIQ</strong>
                    <small>BATTERY INTELLIGENCE</small>
                </div>
            </div>

            <div class="live-pill">
                <i></i>
                ${VOLTIQ_MODE === "DEMO" ? "DEMO SIMULATION" : "ESP32 TELEMETRY"}
            </div>

            <nav>
                <div class="nav-title">MAIN MENU</div>

                ${nav("overview", "◈", "Overview")}
                ${nav("battery", "▣", "Battery Monitor")}
                ${nav("alerts", "⚠", "Alerts & Notifications")}
                ${nav("charging", "ϟ", "Charging & Discharging")}
                ${nav("reports", "▤", "Reports")}
                ${nav("settings", "⚙", "Settings")}

                <div class="nav-title">RESOURCES</div>

                ${nav("guide", "▣", "Battery User Guide")}
            </nav>

            <div class="sidebar-bottom">

                <div class="system-card">
                    <b>● SYSTEM STATUS</b>
                    <p>
                        ${VOLTIQ_MODE === "DEMO"
                            ? "Demo data is simulated locally."
                            : "ESP32 telemetry connection enabled."}
                        <br>
                        Monitoring only — no hardware control.
                    </p>
                </div>

                <div class="side-user">
                    <div class="avatar">${role === "admin" ? "A" : "U"}</div>
                    <div>
                        <strong>${esc(userName)}</strong>
                        <small>
                            ${role === "admin"
                                ? "Fleet Administrator"
                                : "Vehicle Operator"}
                        </small>
                    </div>
                    <button id="logoutBtn">↪</button>
                </div>

            </div>
        </aside>

        <main class="main-content">

            <header class="topbar">
                <span class="topbar-title">
                    VoltIQ / <span id="crumb">Overview</span>
                </span>

                <div class="top-actions">
                    <span class="mode-badge">
                        ${VOLTIQ_MODE} MODE
                    </span>

                    <button id="refreshBtn">↻ Refresh</button>
                    <button id="logoutTop">Logout</button>
                </div>
            </header>

            <div id="pageContent" class="dashboard-section"></div>

        </main>
    `;

    document.querySelectorAll("[data-page]").forEach(button => {
        button.addEventListener("click", () => {
            renderPage(button.dataset.page);
        });
    });

    $("logoutBtn").onclick = logout;
    $("logoutTop").onclick = logout;
    $("refreshBtn").onclick = refreshNow;
}

function nav(id, icon, label) {
    return `
        <button
            class="nav-item ${page === id ? "active" : ""}"
            data-page="${id}">
            <span>${icon}</span>
            ${label}
        </button>
    `;
}


/* ================= UI COMPONENTS ================= */

function heading(kicker, title, description) {
    return `
        <div class="page-heading">
            <div>
                <div class="eyebrow">${kicker}</div>
                <h1>${title}</h1>
                <p>${description}</p>
            </div>

            <div class="heading-actions">
                <button class="secondary-btn" onclick="refreshNow()">
                    ↻ Refresh data
                </button>
            </div>
        </div>
    `;
}

function stat(label, value, description) {
    return `
        <div class="stat-card">
            <small>${label}</small>
            <strong>${value}</strong>
            <p>${description}</p>
        </div>
    `;
}
/* ================= MAIN PAGE RENDERER ================= */

function renderPage(which) {
    page = which;

    document.querySelectorAll("[data-page]").forEach(button => {
        button.classList.toggle(
            "active",
            button.dataset.page === page
        );
    });

    const pageNames = {
        overview: "Overview",
        vehicle: "Vehicle Details",
        battery: "Battery Monitor",
        alerts: "Alerts & Notifications",
        charging: "Charging & Discharging",
        reports: "Reports",
        settings: "Settings",
        guide: "Battery User Guide"
    };

    if ($("crumb")) {
        $("crumb").textContent = pageNames[page] || "Overview";
    }

    const b = telemetry;
    const s = status();
    const risk = getRisk();
    const lab = getLab();

    let html = "";

    /* =====================================================
       1. OVERVIEW
    ===================================================== */

    if (page === "overview") {
        html = heading(
            "EV FLEET COMMAND CENTER",
            "Battery <span style='color:var(--green)'>Overview</span>",
            "Real-time visibility into battery condition, energy flow and system health."
        ) + `

        <div class="hero-panel">
            <div>
                <div class="eyebrow">BATTERY STATUS · ${VOLTIQ_MODE}</div>
                <h2>Your EV. <span>Understood.</span></h2>
                <p>
                    Track state of charge, battery health and
                    electrical conditions from one monitoring workspace.
                </p>
            </div>

            <div class="hero-value">
                <strong>${fmt(b.soc, 0)}%</strong>
                <small>STATE OF CHARGE</small>
            </div>
        </div>

        <div class="stats-grid">
            ${stat("STATE OF HEALTH", fmt(b.soh, 1) + "%", "Estimated battery condition")}
            ${stat("PACK VOLTAGE", fmt(b.voltage, 2) + " V", "Measured voltage")}
            ${stat("CURRENT", fmt(b.current, 2) + " A", "Battery current")}
            ${stat("TEMPERATURE", fmt(b.temperature, 1) + " °C", "Battery temperature")}
        </div>

        <div class="panel">
            <div class="panel-head">
                <div>
                    <h2>Selected Vehicle</h2>
                    <p>Primary battery telemetry</p>
                </div>
                <span class="status ${s.toLowerCase()}">${s}</span>
            </div>

            <div class="vehicle-grid">
                <div class="vehicle-card">
                    <div class="card-top">
                        <b>${esc(selectedVehicleId || "VOLTIQ-EV-001")}</b>
                        <span class="status ${s.toLowerCase()}">${s}</span>
                    </div>
                    <h3>EV Battery Pack</h3>
                    <p>${VOLTIQ_MODE === "DEMO" ? "Simulated sensor feed" : "ESP32 sensor feed"}</p>
                    <div class="mini-grid">
                        <div><small>SOC</small><b>${fmt(b.soc, 0)}%</b></div>
                        <div><small>SOH</small><b>${fmt(b.soh, 0)}%</b></div>
                        <div><small>TEMP</small><b>${fmt(b.temperature)}°C</b></div>
                    </div>
                </div>

                <div class="vehicle-card">
                    <div class="eyebrow">BATTERY RISK INDEX</div>
                    <h3>${risk.score ?? "—"} / 100</h3>
                    <p>${esc(risk.level)} · ${esc(risk.detail)}</p>
                    <button class="secondary-btn" onclick="renderPage('battery')">
                        View Battery Intelligence
                    </button>
                </div>
            </div>
        </div>
        `;

        html += renderFleetOverview();
    }

    /* =====================================================
       2. VEHICLE DETAILS
    ===================================================== */

    if (page === "vehicle") {
        const v = fleetVehicles.find(
            (item, i) => vehicleId(item, i) === selectedVehicleId
        );

        if (!v) {
            html = heading(
                "VEHICLE DETAILS",
                "Vehicle not found",
                "Return to Overview and select an available vehicle."
            );
        } else {
            const vb = vehicleBattery(v);
            const vs = vehicleStatus(v);

            html = heading(
                "VEHICLE DETAILS",
                esc(vehicleId(v)),
                "Individual vehicle battery measurements and intelligence."
            ) + `

            <div class="stats-grid">
                ${stat("STATE OF CHARGE", vb.soc === null ? "—" : fmt(vb.soc) + "%", "Battery charge")}
                ${stat("STATE OF HEALTH", vb.soh === null ? "—" : fmt(vb.soh) + "%", "Battery health")}
                ${stat("VOLTAGE", vb.voltage === null ? "—" : fmt(vb.voltage, 2) + " V", "Pack voltage")}
                ${stat("CURRENT", vb.current === null ? "—" : fmt(vb.current, 2) + " A", "Battery current")}
                ${stat("TEMPERATURE", vb.temperature === null ? "—" : fmt(vb.temperature, 1) + " °C", "Battery temperature")}
                ${stat("STATUS", vs, "Vehicle condition")}
            </div>

            <div class="panel">
                <h2>Battery Intelligence Features</h2>
                <p>Open Battery Monitor to use all six features.</p>
                <button class="primary-btn" onclick="renderPage('battery')">
                    Open Battery Monitor
                </button>
            </div>

            <button class="secondary-btn" onclick="renderPage('overview')">
                ← Back to Overview
            </button>
            `;
        }
    }
/* =====================================================
   3. BATTERY MONITOR
===================================================== */

if (page === "battery") {
    html = heading(
        "BATTERY INTELLIGENCE",
        "Battery Monitor",
        "Existing battery intelligence and advanced AI predictions."
    ) + `
        <div class="panel">
            <div class="panel-head">
                <div>
                    <h2>${esc(selectedVehicleId || "EV-001")}</h2>
                    <p>Battery intelligence, advanced predictions and protection analysis for this vehicle.</p>
                </div>
                <span class="status ${s.toLowerCase()}">${s}</span>
            </div>
            <div class="stats-grid">
                ${stat("STATE OF CHARGE", fmt(b.soc, 0) + "%", "Battery charge")}
                ${stat("STATE OF HEALTH", fmt(b.soh, 1) + "%", "Battery condition")}
                ${stat("PACK VOLTAGE", fmt(b.voltage, 2) + " V", "Measured voltage")}
                ${stat("TEMPERATURE", fmt(b.temperature, 1) + " °C", "Battery temperature")}
            </div>
        </div>
    `;
}
 

    /* =====================================================
       4. ALERTS AND NOTIFICATIONS
    ===================================================== */

    if (page === "alerts") {
        html = heading(
            "EVENT CENTER",
            "Alerts & Notifications",
            "Warnings generated from current battery measurements."
        ) + `
        <div class="panel">
            <div class="panel-head">
                <div>
                    <h2>Current Battery Alerts</h2>
                    <p>Checked against the limits for this battery's voltage range.</p>
                </div>
            </div>
            ${alertRows()}
        </div>
        `;
    }

    /* =====================================================
       5. CHARGING AND DISCHARGING
    ===================================================== */

    if (page === "charging") {
        const charging = b.current >= 0;

        html = heading(
            "ENERGY FLOW",
            "Charging & Discharging",
            "Monitor current direction, voltage, power and state of charge."
        ) + `

        <div class="hero-panel">
            <div>
                <div class="eyebrow">CURRENT FLOW</div>
                <h2>${charging ? "Charging" : "Discharging"}</h2>
                <p>
                    Direction is inferred from current sign.
                    Confirm the polarity of your sensor wiring.
                </p>
            </div>

            <div class="hero-value">
                <strong>${fmt(Math.abs(b.current), 2)} A</strong>
                <small>${fmt(Math.abs(b.voltage * b.current), 2)} W</small>
            </div>
        </div>

        <div class="stats-grid">
            ${stat("VOLTAGE", fmt(b.voltage, 2) + " V", "Pack voltage")}
            ${stat("CURRENT", fmt(b.current, 2) + " A", "Signed current")}
            ${stat("POWER", fmt(Math.abs(b.voltage * b.current), 2) + " W", "Calculated power")}
            ${stat("SOC", fmt(b.soc, 0) + "%", "State of charge")}
        </div>
        `;
    }

    /* =====================================================
       6. REPORTS
    ===================================================== */

    if (page === "reports") {
        html = heading(
            "ANALYTICS",
            "Battery Reports",
            "View and share the report for the currently selected vehicle."
        ) + `

        <div class="panel">
            <div class="panel-head">
                <div>
                    <h2>Battery Snapshot</h2>
                    <p>Vehicle / Battery: ${esc(selectedVehicleId || "EV-001")}</p>
                    <p>${new Date(b.updated).toLocaleString()}</p>
                </div>
                <span class="status ${status().toLowerCase()}">${status()}</span>
            </div>

            <table class="data-table">
                <tr><th>PARAMETER</th><th>VALUE</th></tr>
                <tr><td>Vehicle / Battery</td><td>${esc(selectedVehicleId || "EV-001")}</td></tr>
                <tr><td>Voltage</td><td>${fmt(b.voltage, 2)} V</td></tr>
                <tr><td>Current</td><td>${fmt(b.current, 2)} A</td></tr>
                <tr><td>Temperature</td><td>${fmt(b.temperature, 1)} °C</td></tr>
                <tr><td>State of Charge</td><td>${fmt(b.soc, 1)}%</td></tr>
                <tr><td>State of Health</td><td>${fmt(b.soh, 1)}%</td></tr>
                <tr><td>Power</td><td>${fmt(b.voltage * b.current, 2)} W</td></tr>
                <tr><td>Battery Risk Index</td><td>${esc(risk.score ?? "—")}</td></tr>
                <tr><td>Risk Level</td><td>${esc(risk.level ?? "Unavailable")}</td></tr>
                <tr><td>Battery Status</td><td>${status()}</td></tr>
                <tr><td>Last Updated</td><td>${new Date(b.updated).toLocaleString()}</td></tr>
            </table>

            <div class="report-actions">
                <button class="whatsapp-btn" onclick="shareBatteryWhatsApp()">
                    WhatsApp Report
                </button>

                <button class="email-btn" onclick="shareBatteryEmail()">
                    Email Report
                </button>

                <button class="primary-btn" onclick="downloadReport()">
                    Download Report
                </button>
            </div>
        </div>
        `;
    }

    /* =====================================================
       7. SETTINGS
    ===================================================== */

    if (page === "settings") {
        html = heading(
            "CONFIGURATION",
            "Settings",
            "Configure the ESP32 telemetry connection."
        ) + `

        <div class="panel">
            <div class="panel-head">
                <div>
                    <h2>Device Connection</h2>
                    <p>
                        The ESP32 sends readings to this server, and the
                        dashboard reads them from here in ESP32 mode.
                    </p>
                </div>
                ${VOLTIQ_MODE === "ESP32"
                    ? `<span class="status ${esp32Connected ? "healthy" : "warning"}">
                           ${esp32Connected ? "RECEIVING" : esp32HasData ? "STALE" : "NO DATA"}
                       </span>`
                    : ""}
            </div>

            <div class="field">
                <label>ESP32 device ID</label>
                <input
                    id="deviceId"
                    value="${esc(deviceId)}"
                    placeholder="Leave empty to use the most recent device">
            </div>

            <button class="primary-btn" onclick="saveDeviceId()">
                Save device
            </button>

            ${VOLTIQ_MODE === "ESP32" && esp32LastError
                ? `<p class="muted">Last result: ${esc(esp32LastError)}</p>`
                : VOLTIQ_MODE === "ESP32" && esp32HasData && telemetry.updated
                    ? `<p class="muted">Last reading received ${esc(new Date(telemetry.updated).toLocaleString())}.</p>`
                    : ""}
        </div>

        <div class="panel">
            <h2>ESP32 Firmware Setup</h2>
            <p>Program the ESP32 to send an HTTPS POST every few seconds:</p>

            <table class="data-table">
                <tr><th>SETTING</th><th>VALUE</th></tr>
                <tr><td>URL</td><td>${esc(location.origin)}/api/telemetry/device</td></tr>
                <tr><td>Method</td><td>POST</td></tr>
                <tr><td>Headers</td><td>Content-Type: application/json · X-API-Key: your ESP32_API_KEY</td></tr>
                <tr><td>JSON body</td><td>device_id, voltage, current, power, soc, soh, temperature</td></tr>
            </table>

            <p class="muted">
                ESP32_API_KEY must be set as an environment variable on the
                server. The ESP32 needs internet access; its local address
                (such as 192.168.4.1) cannot be reached from this website.
            </p>
        </div>

        <div class="panel">
            <h2>Application Information</h2>
            <p>Logged in as: ${esc(userName)}</p>
            <p>Account role: ${esc(role)}</p>
            <p>Connection mode: ${esc(VOLTIQ_MODE)}</p>
            <p>Vehicle access: ${role === "admin" ? "Fleet vehicles" : "Assigned vehicles only"}</p>
        </div>
        `;
    }

    /* =====================================================
       8. BATTERY USER GUIDE
    ===================================================== */

    if (page === "guide") {
        html = heading(
            "KNOW YOUR BATTERY",
            "Battery User Guide",
            "Instructions for understanding the VoltIQ dashboard."
        ) + `

        <div class="panel">
            <h2>How to read VoltIQ</h2>

            <ol class="guide-list">
                <li><b>SOC:</b> State of Charge — estimated remaining battery charge.</li>
                <li><b>SOH:</b> State of Health — estimated battery condition.</li>
                <li><b>Voltage:</b> Electrical potential measured at the battery pack.</li>
                <li><b>Current:</b> Positive is treated as charging and negative as discharging in this dashboard.</li>
                <li><b>Temperature:</b> Battery temperature in degrees Celsius.</li>
                <li><b>Battery Risk Index:</b> Illustrative score derived from battery readings.</li>
                <li><b>Sensor Reliability:</b> Checks for missing or implausible readings.</li>
                <li><b>Battery Stress:</b> Tracks unusual operating conditions.</li>
                <li><b>Recovery Time:</b> Tracks recovery after a stress event.</li>
                <li><b>Protection Verification:</b> Demonstrates a simulated protection response.</li>
                <li><b>Fault Simulator:</b> Runs software-only fault demonstrations.</li>
            </ol>

            <p class="muted">
                Always compare thresholds and sensor polarity
                with the battery and sensor manufacturer documentation.
                VoltIQ is not a replacement for a certified BMS.
            </p>
        </div>
        `;
    }

    $("pageContent").innerHTML = html;
}
/* ================= FLEET OVERVIEW ================= */

function renderFleetOverview() {
    const total = fleetVehicles.length;

    const counts = {
        HEALTHY: 0,
        WARNING: 0,
        CRITICAL: 0
    };

    fleetVehicles.forEach(v => {
        counts[vehicleStatus(v)]++;
    });

    const socs = fleetVehicles
        .map(v => vehicleBattery(v).soc)
        .filter(v => v !== null);

    const sohs = fleetVehicles
        .map(v => vehicleBattery(v).soh)
        .filter(v => v !== null);

    const average = values => values.length
        ? (
            values.reduce((a, b) => a + b, 0) /
            values.length
        ).toFixed(1)
        : "—";

    const cards = fleetVehicles.map((v, i) => {
        const id = vehicleId(v, i);
        const b = vehicleBattery(v);
        const st = vehicleStatus(v);
        const selected = id === selectedVehicleId;

        return `
            <button
                class="vehicle-card ${selected ? "is-selected" : ""}"
                onclick="selectFleetVehicle('${encodeURIComponent(id)}')">

                <div class="card-top">
                    <b>${esc(id)}</b>
                    <span class="status ${st.toLowerCase()}">${st}</span>
                </div>

                <h3>${esc(v.name || v.model || "EV Battery Pack")}</h3>

                <p>${esc(v.battery_id || v.battery_code || "Battery telemetry")}</p>

                <div class="mini-grid">
                    <div>
                        <small>SOC</small>
                        <b>${b.soc === null ? "—" : fmt(b.soc, 0) + "%"}</b>
                    </div>

                    <div>
                        <small>SOH</small>
                        <b>${b.soh === null ? "—" : fmt(b.soh, 0) + "%"}</b>
                    </div>

                    <div>
                        <small>TEMP</small>
                        <b>${b.temperature === null ? "—" : fmt(b.temperature, 1) + "°C"}</b>
                    </div>
                </div>

                <div class="card-link">
                    Open vehicle details <span>→</span>
                </div>
            </button>
        `;
    }).join("");

    return `
        <section class="panel">

            <div class="panel-head">
                <div>
                    <h2>
                        ${role === "admin"
                            ? "Admin Fleet Overview"
                            : "My Vehicle Overview"}
                    </h2>

                    <p>
                        ${role === "admin"
                            ? "All vehicles permitted for this administrator."
                            : "Vehicles assigned to your user account."}
                    </p>
                </div>

                <span class="mode-badge">
                    ${total} VEHICLES
                </span>
            </div>

            ${fleetError
                ? `<p class="muted">Fleet API: ${esc(fleetError)}</p>`
                : ""}

            <div class="stats-grid">
                ${stat("TOTAL VEHICLES", total, "Vehicles available to this account")}
                ${stat("HEALTHY", counts.HEALTHY, "Healthy vehicles")}
                ${stat("WARNING", counts.WARNING, "Vehicles needing attention")}
                ${stat("CRITICAL", counts.CRITICAL, "Vehicles requiring investigation")}
            </div>

            <div class="stats-grid">
                ${stat("AVERAGE SOC", average(socs) === "—" ? "—" : average(socs) + "%", "Available readings")}
                ${stat("AVERAGE SOH", average(sohs) === "—" ? "—" : average(sohs) + "%", "Available readings")}
            </div>

            <div class="panel-head">
                <div>
                    <h2>Vehicle List</h2>
                    <p>Click a vehicle card to open its details.</p>
                </div>

                <button class="secondary-btn" onclick="refreshFleet()">
                    ↻ Refresh fleet
                </button>
            </div>

            ${total
                ? `<div class="vehicle-grid">${cards}</div>`
                : `<p class="muted">${
                    fleetLoading
                        ? "Loading vehicles..."
                        : "No vehicles were returned for this account. Check backend vehicle assignment."
                }</p>`}

        </section>
    `;
}


/* ================= ALERTS ================= */

function alertRows() {
    const alerts = [];
    const lim = batteryLimits(telemetry.voltage);

    if (telemetry.temperature >= lim.tWarn) {
        alerts.push([
            "High battery temperature",
            `Temperature is ${fmt(telemetry.temperature)} °C`,
            telemetry.temperature >= lim.tCrit ? "critical" : "warning"
        ]);
    }

    if (telemetry.voltage < lim.vWarnLow) {
        alerts.push([
            "Low battery voltage",
            `Voltage is ${fmt(telemetry.voltage, 2)} V`,
            telemetry.voltage < lim.vCritLow ? "critical" : "warning"
        ]);
    }

    if (telemetry.voltage > lim.vWarnHigh) {
        alerts.push([
            "High battery voltage",
            `Voltage is ${fmt(telemetry.voltage, 2)} V`,
            "critical"
        ]);
    }

    if (telemetry.soc < 20) {
        alerts.push([
            "Low state of charge",
            `SOC is ${fmt(telemetry.soc, 0)}%`,
            "warning"
        ]);
    }

    if (!alerts.length) {
        return `
            <div class="empty-state">
                No active alerts. Battery readings are within
                the configured thresholds.
            </div>
        `;
    }

    return `<div class="alert-list">${alerts.map(a => `
        <div class="alert-row ${a[2]}">
            <span class="status ${a[2]}">${a[2].toUpperCase()}</span>
            <div>
                <b>${esc(a[0])}</b>
                <span class="muted">${esc(a[1])}</span>
            </div>
        </div>
    `).join("")}</div>`;
}


/* ================= DEMO TELEMETRY ================= */

function updateDemo() {
    demoTick++;

    telemetry.voltage =
        12.55 + Math.sin(demoTick / 5) * 0.16;

    telemetry.current =
        1.05 + Math.sin(demoTick / 4) * 0.35;

    telemetry.temperature =
        29 + Math.sin(demoTick / 8) * 1.4;

    telemetry.soc = Math.max(
        20,
        Math.min(
            100,
            telemetry.soc +
            (demoTick % 8 === 0 ? -0.1 : 0)
        )
    );

    telemetry.power =
        telemetry.voltage * telemetry.current;

    telemetry.updated = new Date().toISOString();

    // Do not rebuild the page during automatic background updates.
}


/* ================= ESP32 TELEMETRY ================= */

async function pollEsp32() {
    try {
        const query = deviceId
            ? "?device_id=" + encodeURIComponent(deviceId)
            : "";

        const response = await authenticatedFetch(
            "/api/telemetry/device/latest" + query,
            { cache: "no-store" }
        );

        if (!response.ok) {
            let detail = "HTTP " + response.status;

            try {
                detail = (await response.json()).detail || detail;
            } catch {
                // Keep the status code.
            }

            throw new Error(detail);
        }

        const x = await response.json();

        esp32HasData = true;
        esp32LastError = "";

        [
            "voltage",
            "current",
            "temperature",
            "soc",
            "soh"
        ].forEach(key => {
            if (x[key] !== undefined) {
                const value = Number(x[key]);

                if (Number.isFinite(value)) {
                    telemetry[key] = value;
                }
            }
        });

        if (x.charging !== undefined) {
            telemetry.charging = !!x.charging;
        }

        // Backend timestamps are UTC without a zone suffix.
        telemetry.updated = x.timestamp
            ? (x.timestamp.endsWith("Z") ? x.timestamp : x.timestamp + "Z")
            : new Date().toISOString();

        telemetry.power =
            telemetry.voltage * telemetry.current;

        // Only a recent reading counts as a live connection.
        const age = Date.now() - new Date(telemetry.updated).getTime();
        esp32Connected = age <= ESP32_STALE_MS;

    } catch (error) {
        esp32Connected = false;

        if (error.message !== esp32LastError) {
            esp32LastError = error.message;
            console.warn("ESP32 telemetry:", error.message);
            toast("ESP32: " + error.message);
        }
    }
}


/* ================= REFRESH ================= */

async function refreshNow() {
    if (VOLTIQ_MODE === "DEMO") {
        updateDemo();
    } else {
        await pollEsp32();
    }

    // Manual refresh redraws once.
    // Automatic polling does not rebuild the page.
    renderPage(page);
}

async function refreshFleet() {
    await loadFleetVehicles();
    renderPage(page);

    toast(
        fleetError
            ? "Fleet refresh failed"
            : "Fleet refreshed"
    );
}


/* ================= ESP32 SETTINGS ================= */

function saveDeviceId() {
    const input = $("deviceId");
    if (!input) return;

    const value = input.value.trim();

    if (value && !/^[A-Za-z0-9_.:-]{1,50}$/.test(value)) {
        toast("Device ID may only use letters, numbers, - _ . and :");
        return;
    }

    deviceId = value;
    esp32LastError = "";

    if (value) {
        localStorage.setItem("voltiq_device_id", value);
    } else {
        localStorage.removeItem("voltiq_device_id");
    }

    toast(value ? "ESP32 device saved." : "Using the most recent ESP32 device.");

    if (VOLTIQ_MODE === "ESP32") {
        pollEsp32().then(() => renderPage(page));
    }
}


/* ================= FAULT SIMULATOR ================= */

function runFault(type) {
    if (typeof runLabFault !== "function") {
        toast("Battery intelligence module unavailable.");
        return;
    }

    runLabFault(type);
    renderPage("battery");

    toast("Software fault simulation executed.");
}

function clearFault() {
    if (typeof VOLTIQ_LAB !== "undefined") {
        VOLTIQ_LAB.simulation = null;
        VOLTIQ_LAB.protection = null;
    }

    renderPage("battery");
}


/* ================= BATTERY REPORT SHARING ================= */

function getBatteryReportText() {
    const risk = getRisk();
    const vehicle = selectedVehicleId || "EV-001";

    return [
        "VOLTIQ - EV BATTERY REPORT",
        "----------------------------",
        "Vehicle / Battery: " + vehicle,
        "Date: " + new Date(telemetry.updated).toLocaleString(),
        "",
        "BATTERY MEASUREMENTS",
        "Voltage: " + fmt(telemetry.voltage, 2) + " V",
        "Current: " + fmt(telemetry.current, 2) + " A",
        "Temperature: " + fmt(telemetry.temperature, 1) + " °C",
        "State of Charge: " + fmt(telemetry.soc, 1) + "%",
        "State of Health: " + fmt(telemetry.soh, 1) + "%",
        "Power: " + fmt(telemetry.voltage * telemetry.current, 2) + " W",
        "",
        "BATTERY INTELLIGENCE",
        "Battery Risk Index: " + (risk.score ?? "Unavailable"),
        "Risk Level: " + (risk.level ?? "Unavailable"),
        "Battery Status: " + status(),
        "",
        "Generated by VoltIQ Battery Intelligence.",
        "Monitoring report only. Not a certified BMS report."
    ].join("\n");
}

function shareBatteryWhatsApp() {
    const report = getBatteryReportText();

    const url =
        "https://wa.me/?text=" +
        encodeURIComponent(report);

    window.open(url, "_blank", "noopener,noreferrer");

    toast("WhatsApp report prepared. Choose a recipient.");
}

function shareBatteryEmail() {
    const subject =
        "VoltIQ Battery Report - " +
        (selectedVehicleId || "EV-001");

    const body = getBatteryReportText();

    const mailto =
        "mailto:?subject=" +
        encodeURIComponent(subject) +
        "&body=" +
        encodeURIComponent(body);

    window.location.href = mailto;

    toast("Email report prepared. Choose a recipient.");
}


/* ================= CSV REPORT DOWNLOAD ================= */

function downloadReport() {
    const risk = getRisk();

    const rows = [
        ["Parameter", "Value"],
        ["Vehicle / Battery", selectedVehicleId || "EV-001"],
        ["Voltage (V)", telemetry.voltage],
        ["Current (A)", telemetry.current],
        ["Temperature (C)", telemetry.temperature],
        ["State of Charge (%)", telemetry.soc],
        ["State of Health (%)", telemetry.soh],
        ["Power (W)", telemetry.voltage * telemetry.current],
        ["Battery Risk Index", risk.score ?? "Unavailable"],
        ["Risk Level", risk.level ?? "Unavailable"],
        ["Battery Status", status()],
        ["Updated", telemetry.updated]
    ];

    const csv = rows.map(row =>
        row.map(value =>
            '"' + String(value ?? "").replace(/"/g, '""') + '"'
        ).join(",")
    ).join("\n");

    const blob = new Blob(["\uFEFF" + csv], {
        type: "text/csv;charset=utf-8"
    });

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");

    const safeVehicle =
        (selectedVehicleId || "battery")
            .replace(/[^a-z0-9_-]/gi, "_");

    a.href = url;
    a.download =
        "voltiq-" + safeVehicle + "-battery-report.csv";

    document.body.appendChild(a);
    a.click();
    a.remove();

    setTimeout(() => URL.revokeObjectURL(url), 1000);

    toast("Selected battery report downloaded.");
}


/* ================= LOGOUT ================= */

function logout() {
    if (timer) {
        clearInterval(timer);
        timer = null;
    }

    localStorage.removeItem("voltiq_token");
    localStorage.removeItem("voltiq_user");

    fleetVehicles = [];
    selectedVehicleId = null;

    $("app").classList.add("hidden");
    $("loginScreen").classList.remove("hidden");

    if ($("loginPassword")) {
        $("loginPassword").value = "";
    }

    if ($("loginMessage")) {
        $("loginMessage").textContent = "";
    }
}


/* ================= GLOBAL FUNCTIONS ================= */

window.renderPage = renderPage;
window.refreshNow = refreshNow;
window.refreshFleet = refreshFleet;
window.selectFleetVehicle = selectFleetVehicle;
window.runFault = runFault;
window.clearFault = clearFault;
window.saveDeviceId = saveDeviceId;
window.downloadReport = downloadReport;
window.shareBatteryWhatsApp = shareBatteryWhatsApp;
window.shareBatteryEmail = shareBatteryEmail;
window.logout = logout;


/* ================= END OF VOLTIQ APP ================= */
