/* ============================================================
   VOLTIQ - BATTERY INTELLIGENCE PLATFORM
   Frontend application
   Battery: 12V, 7Ah Lead-Acid
   ============================================================ */

"use strict";

/* ============================================================
   CONFIGURATION
   ============================================================ */

const API_BASE = "";

const REFRESH_INTERVAL = 5000;

const BATTERY_CONFIG = {
    type: "Lead-Acid",
    voltage: 12,
    capacity: 7
};

let currentMode = "demo";
let currentUser = null;
let authToken = localStorage.getItem("voltiq_token");

let latestBatteryData = null;
let latestAlerts = [];
let refreshTimer = null;
let demoTimer = null;

let currentSettings = {
    temperature_warning: 40,
    temperature_critical: 45,
    soc_warning: 20,
    soh_warning: 70,
    email_enabled: false,
    whatsapp_enabled: false,
    weekly_reports: false
};


/* ============================================================
   DEMO DATA
   These values are samples, NOT physical battery readings.
   ============================================================ */

const DEMO_READINGS = [
    {
        voltage: 12.65,
        current: 0.45,
        power: 0.00569,
        soc: 95,
        soh: 96,
        temperature: 29,
        operating_state: "Charging"
    },
    {
        voltage: 12.48,
        current: 0.72,
        power: 0.00899,
        soc: 87,
        soh: 96,
        temperature: 30,
        operating_state: "Charging"
    },
    {
        voltage: 12.32,
        current: -0.85,
        power: 0.01047,
        soc: 78,
        soh: 95,
        temperature: 31,
        operating_state: "Discharging"
    },
    {
        voltage: 12.18,
        current: -1.10,
        power: 0.01340,
        soc: 65,
        soh: 95,
        temperature: 32,
        operating_state: "Discharging"
    },
    {
        voltage: 12.05,
        current: -0.60,
        power: 0.00723,
        soc: 52,
        soh: 94,
        temperature: 30,
        operating_state: "Discharging"
    }
];

let demoIndex = 0;


/* ============================================================
   DOM HELPERS
   ============================================================ */

function getElement(id) {
    return document.getElementById(id);
}

function setText(id, value) {
    const element = getElement(id);

    if (element) {
        element.textContent = value;
    }
}

function setHTML(id, value) {
    const element = getElement(id);

    if (element) {
        element.innerHTML = value;
    }
}

function formatNumber(value, decimals = 2) {
    const number = Number(value);

    if (!Number.isFinite(number)) {
        return "--";
    }

    return number.toFixed(decimals);
}

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => {
        const replacements = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#039;"
        };

        return replacements[character];
    });
}


/* ============================================================
   API REQUEST HELPER
   ============================================================ */

async function apiRequest(path, options = {}) {

    const headers = {
        ...(options.headers || {})
    };

    if (options.body && !(options.body instanceof FormData)) {
        headers["Content-Type"] = "application/json";
    }

    if (authToken) {
        headers["Authorization"] = `Bearer ${authToken}`;
    }

    const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers
    });

    const contentType = response.headers.get("content-type") || "";

    let data = null;

    if (contentType.includes("application/json")) {
        data = await response.json();
    } else {
        data = await response.text();
    }

    if (!response.ok) {

        if (response.status === 401) {
            localStorage.removeItem("voltiq_token");
            authToken = null;
        }

        const message =
            typeof data === "object"
                ? data.detail || data.message || "Request failed."
                : data || "Request failed.";

        throw new Error(message);
    }

    return data;
}


/* ============================================================
   TOAST NOTIFICATIONS
   ============================================================ */

function showToast(message, type = "info") {

    const container = getElement("toastContainer");

    if (!container) {
        console.log(message);
        return;
    }

    const toast = document.createElement("div");

    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add("toast-visible");
    }, 10);

    setTimeout(() => {
        toast.classList.remove("toast-visible");

        setTimeout(() => toast.remove(), 300);

    }, 3500);
}


/* ============================================================
   LOGIN
   ============================================================ */

async function handleLogin(event) {

    event.preventDefault();

    const email = getElement("email")?.value.trim();
    const password = getElement("password")?.value;

    const button = getElement("loginButton");
    const errorElement = getElement("loginError");

    if (errorElement) {
        errorElement.textContent = "";
    }

    if (!email || !password) {
        if (errorElement) {
            errorElement.textContent = "Enter your email and password.";
        }

        return;
    }

    if (button) {
        button.disabled = true;
        button.textContent = "Signing in...";
    }

    try {

        const result = await apiRequest("/api/auth/login", {
            method: "POST",
            body: JSON.stringify({
                email,
                password
            })
        });

        if (!result.access_token) {
            throw new Error("The server did not return an access token.");
        }

        authToken = result.access_token;

        localStorage.setItem("voltiq_token", authToken);

        await loadUserInformation();

        showApplication();

        showToast("Welcome to VoltIQ!", "success");

    } catch (error) {

        if (errorElement) {
            errorElement.textContent = error.message;
        }

    } finally {

        if (button) {
            button.disabled = false;
            button.textContent = "Sign In";
        }
    }
}


/* ============================================================
   LOAD CURRENT USER
   ============================================================ */

async function loadUserInformation() {

    currentUser = await apiRequest("/api/auth/me");

    const username =
        currentUser.name ||
        currentUser.full_name ||
        currentUser.email ||
        "VoltIQ User";

    const role = currentUser.role || "User";

    setText("sidebarUserName", username);
    setText("sidebarUserRole", role);

    const avatar = getElement("sidebarUserName");

    if (avatar) {
        const firstLetter = username.charAt(0).toUpperCase();

        const avatarElement = document.querySelector(".user-avatar");

        if (avatarElement) {
            avatarElement.textContent = firstLetter;
        }
    }
}


/* ============================================================
   SHOW APPLICATION
   ============================================================ */

function showApplication() {

    const loginScreen = getElement("loginScreen");
    const application = getElement("app");

    if (loginScreen) {
        loginScreen.style.display = "none";
    }

    if (application) {
        application.style.display = "flex";
    }

    updateDate();

    switchMode("demo");

    loadSettings();

    loadAlerts();

    startApplicationRefresh();
}


/* ============================================================
   LOGOUT
   ============================================================ */

function logout() {

    stopApplicationRefresh();

    localStorage.removeItem("voltiq_token");

    authToken = null;
    currentUser = null;
    latestBatteryData = null;

    const application = getElement("app");
    const loginScreen = getElement("loginScreen");

    if (application) {
        application.style.display = "none";
    }

    if (loginScreen) {
        loginScreen.style.display = "flex";
    }

    const form = getElement("loginForm");

    if (form) {
        form.reset();
    }

    showToast("You have signed out.", "info");
}


/* ============================================================
   DATE AND TIME
   ============================================================ */

function updateDate() {

    const element = getElement("currentDate");

    if (!element) return;

    element.textContent = new Date().toLocaleString(undefined, {
        weekday: "short",
        day: "numeric",
        month: "short",
        year: "numeric"
    });
}


/* ============================================================
   MODE SWITCHING
   ============================================================ */

function switchMode(mode) {

    currentMode = mode;

    const demoButton = getElement("demoModeButton");
    const liveButton = getElement("liveModeButton");
    const notice = getElement("modeNotice");

    if (demoButton) {
        demoButton.classList.toggle("active", mode === "demo");
    }

    if (liveButton) {
        liveButton.classList.toggle("active", mode === "live");
    }

    if (notice) {

        if (mode === "demo") {

            notice.className = "mode-notice demo-notice";

            notice.innerHTML = `
                <strong>DEMO MODE</strong>
                <span>
                    Sample readings are displayed.
                    These are not readings from your physical battery.
                </span>
            `;

        } else {

            notice.className = "mode-notice live-notice";

            notice.innerHTML = `
                <strong>LIVE MODE</strong>
                <span>
                    Waiting for actual ESP32 telemetry.
                    No sample readings are used in this mode.
                </span>
            `;
        }
    }

    if (mode === "demo") {

        stopLiveRefresh();

        startDemoMode();

    } else {

        stopDemoMode();

        clearBatteryDisplay();

        fetchLiveTelemetry();

        startLiveRefresh();
    }
}


/* ============================================================
   DEMO MODE
   ============================================================ */

function startDemoMode() {

    demoIndex = 0;

    displayBatteryData(DEMO_READINGS[demoIndex], "DEMO");

    clearInterval(demoTimer);

    demoTimer = setInterval(() => {

        if (currentMode !== "demo") return;

        demoIndex = (demoIndex + 1) % DEMO_READINGS.length;

        displayBatteryData(DEMO_READINGS[demoIndex], "DEMO");

    }, 6000);
}


function stopDemoMode() {

    clearInterval(demoTimer);

    demoTimer = null;
}


/* ============================================================
   LIVE MODE
   ============================================================ */

function startLiveRefresh() {

    stopLiveRefresh();

    refreshTimer = setInterval(() => {

        if (currentMode === "live") {
            fetchLiveTelemetry();
        }

    }, REFRESH_INTERVAL);
}


function stopLiveRefresh() {

    clearInterval(refreshTimer);

    refreshTimer = null;
}


async function fetchLiveTelemetry() {

    if (currentMode !== "live") return;

    try {

        const result = await apiRequest("/api/telemetry/device");

        const reading = normalizeTelemetry(result);

        if (!reading) {

            clearBatteryDisplay();

            updateConnection(false, "No device readings");

            return;
        }

        displayBatteryData(reading, "LIVE");

        updateConnection(true, "ESP32 connected");

        setText("monitorDataSource", "ESP32 Live");

    } catch (error) {

        clearBatteryDisplay();

        updateConnection(false, "Live data unavailable");

        setText("monitorDataSource", "No live data");

        console.error("Live telemetry error:", error);

    }
}


/* ============================================================
   NORMALIZE TELEMETRY RESPONSE
   Accepts either a single object or a list of readings.
   ============================================================ */

function normalizeTelemetry(result) {

    if (!result) return null;

    let reading = result;

    if (Array.isArray(result)) {

        if (result.length === 0) return null;

        reading = result[0];

    } else if (Array.isArray(result.devices)) {

        if (result.devices.length === 0) return null;

        reading = result.devices[0];

    } else if (Array.isArray(result.readings)) {

        if (result.readings.length === 0) return null;

        reading = result.readings[0];
    }

    if (reading.data && typeof reading.data === "object") {
        reading = reading.data;
    }

    const voltage = Number(reading.voltage);
    const current = Number(reading.current);

    if (!Number.isFinite(voltage) || !Number.isFinite(current)) {
        return null;
    }

    let power = Number(
        reading.power_kw ??
        reading.power ??
        (voltage * current / 1000)
    );

    if (!Number.isFinite(power)) {
        power = null;
    }

    return {
        device_id: reading.device_id || reading.battery_id || "ESP32",
        voltage,
        current,
        power,
        soc: validNumber(reading.soc),
        soh: validNumber(reading.soh),
        temperature: validNumber(reading.temperature),
        timestamp: reading.timestamp || null,
        operating_state: reading.operating_state || null
    };
}


function validNumber(value) {

    if (value === null || value === undefined || value === "") {
        return null;
    }

    const number = Number(value);

    return Number.isFinite(number) ? number : null;
}


/* ============================================================
   CONNECTION STATUS
   ============================================================ */

function updateConnection(connected, message) {

    const status = getElement("connectionStatus");

    if (status) {
        status.classList.toggle("connected", connected);
        status.classList.toggle("disconnected", !connected);
    }

    setText("connectionText", message);
}


/* ============================================================
   DISPLAY LIVE DATA OR DEMO DATA
   ============================================================ */

function displayBatteryData(data, source) {

    latestBatteryData = {
        ...data,
        source
    };

    const voltage = validNumber(data.voltage);
    const current = validNumber(data.current);
    const power = validNumber(data.power);
    const soc = validNumber(data.soc);
    const soh = validNumber(data.soh);
    const temperature = validNumber(data.temperature);

    /* OVERVIEW */

    setHTML(
        "overviewVoltage",
        voltage === null ? "--<small> V</small>" :
            `${formatNumber(voltage)}<small> V</small>`
    );

    setHTML(
        "overviewCurrent",
        current === null ? "--<small> A</small>" :
            `${formatNumber(current)}<small> A</small>`
    );

    setHTML(
        "overviewPower",
        power === null ? "-- <small>kW</small>" :
            `${formatNumber(power, 4)} <small>kW</small>`
    );

    setHTML(
        "overviewTemperature",
        temperature === null ? "--<small> °C</small>" :
            `${formatNumber(temperature, 1)}<small> °C</small>`
    );

    setHTML(
        "overviewSoc",
        soc === null ? "--<small>%</small>" :
            `${formatNumber(soc, 0)}<small>%</small>`
    );

    setHTML(
        "overviewSoh",
        soh === null ? "--" : formatNumber(soh, 0)
    );

    /* SOC PROGRESS */

    const progress = getElement("socProgress");

    if (progress) {

        progress.style.width =
            soc === null ? "0%" : `${Math.max(0, Math.min(100, soc))}%`;
    }

    setText(
        "socStatus",
        soc === null ? "SOC unavailable" :
            soc >= 80 ? "High charge" :
            soc >= 40 ? "Moderate charge" :
            soc >= 20 ? "Low charge" : "Very low charge"
    );

    /* TEMPERATURE STATUS */

    setText(
        "temperatureStatus",
        temperature === null ? "Temperature unavailable" :
            temperature >= currentSettings.temperature_critical
                ? "Critical temperature"
                : temperature >= currentSettings.temperature_warning
                    ? "Temperature warning"
                    : "Temperature within configured limits"
    );

    /* HEALTH ANALYSIS */

    updateHealth(soh);

    /* OPERATING STATE */

    let operatingState = data.operating_state || "Unknown";

    if (!data.operating_state && current !== null) {

        operatingState =
            current > 0 ? "Current positive" :
            current < 0 ? "Current negative" :
            "No current";
    }

    setText("operatingState", operatingState);

    /* LAST UPDATE */

    const timestamp = data.timestamp
        ? new Date(data.timestamp)
        : new Date();

    setText(
        "lastUpdated",
        Number.isNaN(timestamp.getTime())
            ? "Available"
            : timestamp.toLocaleTimeString()
    );

    /* MONITOR PAGE */

    setHTML(
        "monitorVoltage",
        voltage === null ? "--<small> V</small>" :
            `${formatNumber(voltage)}<small> V</small>`
    );

    setHTML(
        "monitorCurrent",
        current === null ? "--<small> A</small>" :
            `${formatNumber(current)}<small> A</small>`
    );

    setHTML(
        "monitorPower",
        power === null ? "--<small> kW</small>" :
            `${formatNumber(power, 4)}<small> kW</small>`
    );

    setHTML(
        "monitorTemperature",
        temperature === null ? "--<small> °C</small>" :
            `${formatNumber(temperature, 1)}<small> °C</small>`
    );

    /* CHARGING PAGE */

    setHTML(
        "chargingSoc",
        soc === null ? "--<small>%</small>" :
            `${formatNumber(soc, 0)}<small>%</small>`
    );

    setHTML(
        "chargingCurrent",
        current === null ? "--<small> A</small>" :
            `${formatNumber(current)}<small> A</small>`
    );

    setHTML(
        "chargingVoltage",
        voltage === null ? "--<small> V</small>" :
            `${formatNumber(voltage)}<small> V</small>`
    );

    setText(
        "chargingState",
        operatingState
    );

    /* DEVICE INFORMATION */

    setHTML(
        "deviceReading",
        `
        <div class="spec-grid">
            <div><span>Device</span><strong>${escapeHTML(data.device_id || "ESP32")}</strong></div>
            <div><span>Data source</span><strong>${escapeHTML(source)}</strong></div>
            <div><span>Voltage</span><strong>${voltage === null ? "--" : formatNumber(voltage) + " V"}</strong></div>
            <div><span>Current</span><strong>${current === null ? "--" : formatNumber(current) + " A"}</strong></div>
        </div>
        `
    );

    /* REPORT */

    setHTML(
        "reportContent",
        `
        <div class="spec-grid">
            <div><span>Data source</span><strong>${escapeHTML(source)}</strong></div>
            <div><span>Voltage</span><strong>${voltage === null ? "--" : formatNumber(voltage) + " V"}</strong></div>
            <div><span>Current</span><strong>${current === null ? "--" : formatNumber(current) + " A"}</strong></div>
            <div><span>SOC</span><strong>${soc === null ? "--" : formatNumber(soc, 0) + "%"}</strong></div>
            <div><span>SOH</span><strong>${soh === null ? "--" : formatNumber(soh, 0) + "%"}</strong></div>
            <div><span>Temperature</span><strong>${temperature === null ? "--" : formatNumber(temperature, 1) + " °C"}</strong></div>
        </div>
        `
    );

    updateConnection(
        source === "DEMO" ? false : true,
        source === "DEMO" ? "Demo data" : "ESP32 connected"
    );

    if (source === "DEMO") {
        setText("monitorDataSource", "Demo sample");
    }
}


/* ============================================================
   BATTERY HEALTH
   ============================================================ */

function updateHealth(soh) {

    const badge = getElement("healthBadge");
    const ring = getElement("healthRing");

    if (soh === null || soh === undefined) {

        setText("healthTitle", "Health analysis pending");

        setText(
            "healthDescription",
            "A valid SOH reading is not available."
        );

        if (badge) {
            badge.textContent = "Awaiting data";
            badge.className = "status-pill neutral";
        }

        if (ring) {
            ring.style.background = "";
        }

        return;
    }

    let title;
    let description;
    let status;

    if (soh >= 85) {

        title = "Good Battery Health";
        description = "The reported SOH indicates good battery condition.";
        status = "good";

    } else if (soh >= currentSettings.soh_warning) {

        title = "Moderate Battery Health";
        description = "Monitor battery performance and condition.";
        status = "warning";

    } else {

        title = "Battery Health Warning";
        description = "The reported SOH is below the configured warning threshold.";
        status = "critical";
    }

    setText("healthTitle", title);
    setText("healthDescription", description);

    if (badge) {
        badge.textContent = title;
        badge.className = `status-pill ${status}`;
    }

    if (ring) {

        const percentage = Math.max(0, Math.min(100, soh));

        ring.style.background =
            `conic-gradient(#24c78b ${percentage}%, #253244 ${percentage}% 100%)`;
    }
}


/* ============================================================
   CLEAR LIVE DISPLAY
   ============================================================ */

function clearBatteryDisplay() {

    latestBatteryData = null;

    const ids = [
        "overviewVoltage",
        "overviewCurrent",
        "overviewTemperature",
        "overviewPower",
        "overviewSoc",
        "overviewSoh",
        "monitorVoltage",
        "monitorCurrent",
        "monitorPower",
        "monitorTemperature",
        "chargingSoc",
        "chargingCurrent",
        "chargingVoltage"
    ];

    ids.forEach(id => {

        const element = getElement(id);

        if (element) {

            if (id === "overviewPower") {
                element.innerHTML = "-- <small>kW</small>";
            } else if (id === "overviewVoltage" || id === "monitorVoltage" || id === "chargingVoltage") {
                element.innerHTML = "--<small> V</small>";
            } else if (id === "overviewCurrent" || id === "monitorCurrent" || id === "chargingCurrent") {
                element.innerHTML = "--<small> A</small>";
            } else if (id === "overviewTemperature" || id === "monitorTemperature") {
                element.innerHTML = "--<small> °C</small>";
            } else if (id === "overviewSoc" || id === "chargingSoc") {
                element.innerHTML = "--<small>%</small>";
            } else {
                element.textContent = "--";
            }
        }
    });

    setText("socStatus", "Waiting for live readings");
    setText("temperatureStatus", "Waiting for live readings");
    setText("healthTitle", "Waiting for ESP32 data");
    setText("healthDescription", "No live battery health reading is currently available.");
    setText("healthBadge", "No live data");
    setText("operatingState", "Unknown");
    setText("lastUpdated", "No live data");
    setText("chargingState", "Waiting for ESP32 readings");

    setText("deviceReading", "No live device reading available.");
    setText("reportContent", "No live report data available.");

    const progress = getElement("socProgress");

    if (progress) {
        progress.style.width = "0%";
    }

    const ring = getElement("healthRing");

    if (ring) {
        ring.style.background = "";
    }

    const badge = getElement("healthBadge");

    if (badge) {
        badge.className = "status-pill neutral";
    }
}


/* ============================================================
   NAVIGATION
   ============================================================ */

function navigateToPage(page) {

    const validPages = [
        "overview",
        "monitor",
        "alerts",
        "charging",
        "reports",
        "settings",
        "guide"
    ];

    if (!validPages.includes(page)) return;

    document.querySelectorAll(".page-section").forEach(section => {
        section.classList.remove("active");
    });

    document.querySelectorAll(".nav-item").forEach(button => {
        button.classList.remove("active");
    });

    const selectedPage = getElement(`page-${page}`);

    if (selectedPage) {
        selectedPage.classList.add("active");
    }

    const navButton = document.querySelector(
        `.nav-item[data-page="${page}"]`
    );

    if (navButton) {
        navButton.classList.add("active");
    }

    const pageTitles = {
        overview: ["Overview", "Your battery performance at a glance."],
        monitor: ["Battery Monitor", "Detailed battery measurements."],
        alerts: ["Alerts & Notifications", "Review battery warnings and events."],
        charging: ["Charging & Discharging", "Understand battery energy flow."],
        reports: ["Reports", "Review battery performance information."],
        settings: ["Settings", "Manage battery monitoring preferences."],
        guide: ["Battery User Guide", "Learn about your battery."]
    };

    setText("pageTitle", pageTitles[page][0]);
    setText("pageSubtitle", pageTitles[page][1]);

    if (page === "alerts") {
        loadAlerts();
    }

    if (page === "settings") {
        loadSettings();
    }
}


/* ============================================================
   ALERTS
   ============================================================ */

async function loadAlerts() {

    try {

        const result = await apiRequest("/api/alerts");

        latestAlerts = Array.isArray(result)
            ? result
            : result.alerts || [];

        renderAlerts();

    } catch (error) {

        console.error("Alert loading error:", error);

        latestAlerts = [];

        renderAlerts();

    }
}


function renderAlerts() {

    const unreadCount = latestAlerts.filter(alert => {
        return !alert.acknowledged;
    }).length;

    setText("alertBadge", unreadCount);

    setText("totalAlerts", latestAlerts.length);

    const warnings = latestAlerts.filter(alert => {
        return String(alert.severity).toLowerCase() === "warning";
    }).length;

    const critical = latestAlerts.filter(alert => {
        return String(alert.severity).toLowerCase() === "critical";
    }).length;

    setText("warningAlerts", warnings);
    setText("criticalAlerts", critical);

    const html = latestAlerts.length
        ? latestAlerts.map(alert => {

            const severity = escapeHTML(
                String(alert.severity || "info").toLowerCase()
            );

            const date = alert.created_at
                ? new Date(alert.created_at).toLocaleString()
                : "Date unavailable";

            return `
                <div class="alert-item ${severity}">
                    <div class="alert-item-content">
                        <strong>${escapeHTML(alert.type || alert.alert_type || "Battery Alert")}</strong>
                        <p>${escapeHTML(alert.message || "No description provided.")}</p>
                        <small>${escapeHTML(date)}</small>
                    </div>

                    <div class="alert-item-actions">
                        <span class="severity-label">${severity.toUpperCase()}</span>

                        ${
                            alert.acknowledged
                                ? "<span class='acknowledged-label'>Acknowledged</span>"
                                : `<button class="acknowledge-button" data-alert-id="${Number(alert.id)}">Acknowledge</button>`
                        }
                    </div>
                </div>
            `;

        }).join("")
        : "<div class='empty-state'>No alerts available.</div>";

    setHTML("alertsList", html);

    const recent = latestAlerts.slice(0, 3);

    setHTML(
        "overviewAlerts",
        recent.length
            ? recent.map(alert => `
                <div class="alert-item ${escapeHTML(String(alert.severity || "info").toLowerCase())}">
                    <div class="alert-item-content">
                        <strong>${escapeHTML(alert.type || alert.alert_type || "Battery Alert")}</strong>
                        <p>${escapeHTML(alert.message || "")}</p>
                    </div>
                </div>
            `).join("")
            : "No alerts to display."
    );
}


async function acknowledgeAlert(alertId) {

    try {

        await apiRequest(`/api/alerts/${alertId}/acknowledge`, {
            method: "POST"
        });

        showToast("Alert acknowledged.", "success");

        await loadAlerts();

    } catch (error) {

        showToast(error.message, "error");

    }
}


/* ============================================================
   SETTINGS
   ============================================================ */

async function loadSettings() {

    try {

        const settings = await apiRequest("/api/settings");

        currentSettings = {
            ...currentSettings,
            ...settings
        };

        setInputValue("temperatureWarning", settings.temperature_warning);
        setInputValue("temperatureCritical", settings.temperature_critical);
        setInputValue("socWarning", settings.soc_warning);
        setInputValue("sohWarning", settings.soh_warning);

        setCheckbox("emailEnabled", settings.email_enabled);
        setCheckbox("whatsappEnabled", settings.whatsapp_enabled);
        setCheckbox("weeklyReports", settings.weekly_reports);

        if (latestBatteryData) {
            updateHealth(validNumber(latestBatteryData.soh));
        }

    } catch (error) {

        console.error("Settings loading error:", error);

    }
}


function setInputValue(id, value) {

    const element = getElement(id);

    if (element && value !== undefined && value !== null) {
        element.value = value;
    }
}


function setCheckbox(id, value) {

    const element = getElement(id);

    if (element) {
        element.checked = Boolean(value);
    }
}


async function saveSettings(event) {

    event.preventDefault();

    const payload = {

        temperature_warning: Number(getElement("temperatureWarning").value),

        temperature_critical: Number(getElement("temperatureCritical").value),

        soc_warning: Number(getElement("socWarning").value),

        soh_warning: Number(getElement("sohWarning").value),

        email_enabled: getElement("emailEnabled").checked,

        whatsapp_enabled: getElement("whatsappEnabled").checked,

        weekly_reports: getElement("weeklyReports").checked
    };

    if (payload.temperature_critical <= payload.temperature_warning) {

        showToast(
            "Critical temperature must be higher than warning temperature.",
            "error"
        );

        return;
    }

    try {

        await apiRequest("/api/settings", {
            method: "PUT",
            body: JSON.stringify(payload)
        });

        currentSettings = {
            ...currentSettings,
            ...payload
        };

        setText("settingsMessage", "Settings saved successfully.");

        showToast("Settings saved successfully.", "success");

        if (latestBatteryData) {
            updateHealth(validNumber(latestBatteryData.soh));
        }

    } catch (error) {

        setText("settingsMessage", error.message);

        showToast(error.message, "error");

    }
}


/* ============================================================
   REFRESH CONTROL
   ============================================================ */

function startApplicationRefresh() {

    stopApplicationRefresh();

    if (currentMode === "demo") {
        startDemoMode();
    } else {
        startLiveRefresh();
    }
}


function stopApplicationRefresh() {

    stopDemoMode();

    stopLiveRefresh();
}


/* ============================================================
   EVENT LISTENERS
   ============================================================ */

function setupEventListeners() {

    const loginForm = getElement("loginForm");

    if (loginForm) {
        loginForm.addEventListener("submit", handleLogin);
    }

    const logoutButton = getElement("logoutButton");

    if (logoutButton) {
        logoutButton.addEventListener("click", logout);
    }

    const demoButton = getElement("demoModeButton");

    if (demoButton) {
        demoButton.addEventListener("click", () => {
            switchMode("demo");
        });
    }

    const liveButton = getElement("liveModeButton");

    if (liveButton) {
        liveButton.addEventListener("click", () => {
            switchMode("live");
        });
    }

    document.querySelectorAll("[data-page]").forEach(button => {

        button.addEventListener("click", () => {

            navigateToPage(button.dataset.page);

        });

    });

    const settingsForm = getElement("settingsForm");

    if (settingsForm) {
        settingsForm.addEventListener("submit", saveSettings);
    }

    const alertsList = getElement("alertsList");

    if (alertsList) {

        alertsList.addEventListener("click", event => {

            const button = event.target.closest(".acknowledge-button");

            if (!button) return;

            const alertId = Number(button.dataset.alertId);

            if (Number.isInteger(alertId) && alertId > 0) {
                acknowledgeAlert(alertId);
            }

        });
    }

}


/* ============================================================
   APPLICATION INITIALIZATION
   ============================================================ */

async function initializeApplication() {

    setupEventListeners();

    updateDate();

    setInterval(updateDate, 60000);

    if (authToken) {

        try {

            await loadUserInformation();

            showApplication();

        } catch (error) {

            console.error("Session validation failed:", error);

            localStorage.removeItem("voltiq_token");

            authToken = null;

            if (getElement("loginScreen")) {
                getElement("loginScreen").style.display = "flex";
            }

            if (getElement("app")) {
                getElement("app").style.display = "none";
            }

        }

    } else {

        if (getElement("loginScreen")) {
            getElement("loginScreen").style.display = "flex";
        }

        if (getElement("app")) {
            getElement("app").style.display = "none";
        }

    }

}


/* ============================================================
   START APPLICATION
   ============================================================ */

document.addEventListener("DOMContentLoaded", initializeApplication);