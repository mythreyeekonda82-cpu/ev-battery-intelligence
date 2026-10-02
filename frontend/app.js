"use strict";

/*
=========================================================
 VOLTIQ | EV BATTERY INTELLIGENCE
 Complete plain JavaScript frontend
 FastAPI backend compatible
=========================================================
*/

const API_BASE = "";

const DEMO_USER = "user@evbattery.demo";
const DEMO_USER_PASSWORD = "user1234";

const DEMO_ADMIN = "admin@evbattery.demo";
const DEMO_ADMIN_PASSWORD = "admin1234";

let currentUser = null;
let currentRole = null;
let vehicles = [];
let selectedVehicle = null;
let refreshTimer = null;


/* ======================================================
   STORAGE
====================================================== */

function getAccessToken() {
    return localStorage.getItem("access_token") || "";
}

function saveAccessToken(token) {
    localStorage.setItem("access_token", token);
}

function saveCurrentUser(user) {
    localStorage.setItem("current_user", JSON.stringify(user));
}

function getStoredUser() {
    try {
        return JSON.parse(localStorage.getItem("current_user") || "null");
    } catch {
        return null;
    }
}

function clearAuthentication() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("current_user");
    localStorage.removeItem("logged_in");

    currentUser = null;
    currentRole = null;
    vehicles = [];
    selectedVehicle = null;
}


/* ======================================================
   API
====================================================== */

async function apiRequest(endpoint, options = {}, auth = true) {

    const headers = {
        "Accept": "application/json",
        ...(options.headers || {})
    };

    const token = getAccessToken();

    if (auth && token) {
        headers.Authorization = `Bearer ${token}`;
    }

    if (
        options.body &&
        typeof options.body === "object" &&
        !(options.body instanceof FormData)
    ) {
        headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(options.body);
    }

    let response;

    try {
        response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers
        });
    } catch (error) {
        throw new Error(
            "Cannot connect to the FastAPI backend. Make sure the server is running on port 8000."
        );
    }

    let data = {};

    try {
        data = await response.json();
    } catch {
        data = {};
    }

    if (response.status === 401 && auth) {
        clearAuthentication();
        showLoginScreen();
        throw new Error("SESSION_EXPIRED");
    }

    if (!response.ok) {
        throw new Error(
            data.detail ||
            data.message ||
            `Request failed with status ${response.status}`
        );
    }

    return data;
}


/* ======================================================
   LOGIN
====================================================== */

async function loginUser(email, password) {

    const cleanEmail = email.trim().toLowerCase();

    const response = await fetch(
        `${API_BASE}/api/auth/login`,
        {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            body: JSON.stringify({
                email: cleanEmail,
                password: password
            })
        }
    );

    let data = {};

    try {
        data = await response.json();
    } catch {
        data = {};
    }

    if (!response.ok) {
        throw new Error(
            data.detail ||
            data.message ||
            "Incorrect email or password."
        );
    }

    if (!data.access_token) {
        throw new Error(
            "Login succeeded but the backend did not return an access token."
        );
    }

    saveAccessToken(data.access_token);

    currentUser = data.user || null;

    currentRole = String(
        data.user?.role || "user"
    ).toLowerCase();

    saveCurrentUser(data.user || {});

    localStorage.setItem("logged_in", "true");

    hideLoginScreen();

    await loadApplication();

    return data;
}


/* ======================================================
   SESSION
====================================================== */

async function validateSession() {

    const token = getAccessToken();

    if (!token) {
        return false;
    }

    try {

        const data = await apiRequest("/api/vehicles");

        if (!data || !data.success) {
            return false;
        }

        vehicles = Array.isArray(data.vehicles)
            ? data.vehicles
            : [];

        currentRole = String(
            data.role || getStoredUser()?.role || "user"
        ).toLowerCase();

        currentUser =
            getStoredUser() ||
            null;

        return true;

    } catch (error) {

        console.error("Session validation:", error);

        clearAuthentication();

        return false;
    }
}


/* ======================================================
   APPLICATION START
====================================================== */

async function startApplication() {

    injectApplicationStyles();

    createLoginScreen();

    const loggedIn = await validateSession();

    if (!loggedIn) {
        showLoginScreen();
        return;
    }

    hideLoginScreen();

    await loadApplication();
}


async function loadApplication() {

    try {

        const data =
            await apiRequest("/api/vehicles");

        vehicles = Array.isArray(data.vehicles)
            ? data.vehicles
            : [];

        currentRole = String(
            data.role || currentRole || "user"
        ).toLowerCase();

        currentUser =
            getStoredUser() ||
            currentUser;

    } catch (error) {

        if (error.message === "SESSION_EXPIRED") {
            return;
        }

        console.error(error);

        showToast(error.message);

        return;
    }

    renderApplication();

    startAutoRefresh();
}


/* ======================================================
   LOGIN SCREEN
====================================================== */

function createLoginScreen() {

    if (document.getElementById("voltiq-login-screen")) {
        return;
    }

    const screen =
        document.createElement("div");

    screen.id = "voltiq-login-screen";

    screen.innerHTML = `
        <div class="voltiq-login-card">

            <div class="voltiq-logo">
                <div class="voltiq-logo-icon">⚡</div>

                <div>
                    <div class="voltiq-brand">
                        VoltIQ
                    </div>

                    <div class="voltiq-brand-sub">
                        BATTERY INTELLIGENCE
                    </div>
                </div>
            </div>

            <h1>
                EV Battery Intelligence
            </h1>

            <p class="voltiq-login-text">
                Secure EV battery monitoring,
                fleet intelligence and health analytics.
            </p>

            <form id="voltiq-login-form">

                <label>Email</label>

                <input
                    id="voltiq-email"
                    type="email"
                    placeholder="Enter email"
                    autocomplete="username"
                    required
                />

                <label>Password</label>

                <input
                    id="voltiq-password"
                    type="password"
                    placeholder="Enter password"
                    autocomplete="current-password"
                    required
                />

                <button
                    id="voltiq-login-button"
                    type="submit"
                >
                    LOGIN
                </button>

                <div
                    id="voltiq-login-error"
                    class="voltiq-login-error"
                ></div>

            </form>

            <div class="voltiq-demo">

                <strong>Demo Accounts</strong>

                <div>
                    User:
                    ${DEMO_USER}
                </div>

                <div>
                    Password:
                    ${DEMO_USER_PASSWORD}
                </div>

                <br>

                <div>
                    Admin:
                    ${DEMO_ADMIN}
                </div>

                <div>
                    Password:
                    ${DEMO_ADMIN_PASSWORD}
                </div>

            </div>

        </div>
    `;

    document.body.appendChild(screen);

    const form =
        document.getElementById(
            "voltiq-login-form"
        );

    form.addEventListener(
        "submit",
        async event => {

            event.preventDefault();

            const email =
                document.getElementById(
                    "voltiq-email"
                ).value;

            const password =
                document.getElementById(
                    "voltiq-password"
                ).value;

            const button =
                document.getElementById(
                    "voltiq-login-button"
                );

            const error =
                document.getElementById(
                    "voltiq-login-error"
                );

            error.textContent = "";

            button.disabled = true;
            button.textContent = "CONNECTING...";

            try {

                await loginUser(
                    email,
                    password
                );

            } catch (err) {

                console.error(err);

                error.textContent =
                    err.message ||
                    "Login failed.";

            } finally {

                button.disabled = false;
                button.textContent = "LOGIN";
            }
        }
    );
}


function showLoginScreen() {

    createLoginScreen();

    const screen =
        document.getElementById(
            "voltiq-login-screen"
        );

    if (screen) {
        screen.style.display = "flex";
    }

    document.body.classList.add(
        "voltiq-logged-out"
    );
}


function hideLoginScreen() {

    const screen =
        document.getElementById(
            "voltiq-login-screen"
        );

    if (screen) {
        screen.style.display = "none";
    }

    document.body.classList.remove(
        "voltiq-logged-out"
    );
}


/* ======================================================
   MAIN APPLICATION
====================================================== */

function renderApplication() {

    let root =
        document.getElementById(
            "voltiq-application"
        );

    if (!root) {

        root =
            document.createElement("div");

        root.id =
            "voltiq-application";

        document.body.appendChild(root);
    }

    const isAdmin =
        currentRole === "admin";

    const name =
        currentUser?.name ||
        (isAdmin
            ? "EV Battery Admin"
            : "EV Battery User");

    root.innerHTML = `
        <div class="voltiq-shell">

            <header class="voltiq-header">

                <div class="voltiq-header-brand">

                    <div class="voltiq-logo-icon small">
                        ⚡
                    </div>

                    <div>
                        <strong>
                            VoltIQ
                        </strong>

                        <span>
                            EV BATTERY INTELLIGENCE
                        </span>
                    </div>

                </div>

                <div class="voltiq-header-user">

                    <div class="voltiq-user-info">
                        <strong>
                            ${escapeHTML(name)}
                        </strong>

                        <span>
                            ${
                                isAdmin
                                    ? "Fleet Administrator"
                                    : "Vehicle Operator"
                            }
                        </span>
                    </div>

                    <span class="
                        voltiq-role-badge
                        ${isAdmin ? "admin" : "user"}
                    ">
                        ${isAdmin ? "ADMIN" : "USER"}
                    </span>

                    <button
                        id="voltiq-logout"
                        class="voltiq-logout"
                    >
                        Logout
                    </button>

                </div>

            </header>

            <main class="voltiq-main">

                ${
                    isAdmin
                        ? renderAdminDashboard()
                        : renderUserDashboard()
                }

            </main>

            <footer class="voltiq-footer">
                EV Battery Intelligence Platform
                · FastAPI Backend
                · Live Battery Monitoring
            </footer>

        </div>
    `;

    setupDashboardEvents();
}


/* ======================================================
   ADMIN DASHBOARD
====================================================== */

function renderAdminDashboard() {

    const total =
        vehicles.length;

    let healthy = 0;
    let warning = 0;
    let critical = 0;

    vehicles.forEach(vehicle => {

        const status =
            getBatteryStatus(
                vehicle.battery || {}
            );

        if (status === "HEALTHY") {
            healthy++;
        } else if (status === "WARNING") {
            warning++;
        } else {
            critical++;
        }
    });

    const avgSOC =
        calculateAverage("soc");

    const avgSOH =
        calculateAverage("soh");

    return `
        <section>

            <div class="voltiq-page-heading">

                <div>
                    <div class="voltiq-eyebrow">
                        ADMIN COMMAND CENTER
                    </div>

                    <h1>
                        Fleet Battery Intelligence
                    </h1>

                    <p>
                        Complete monitoring across
                        the EV fleet.
                    </p>
                </div>

                <div class="voltiq-access">
                    ADMIN ACCESS
                </div>

            </div>

            <div class="voltiq-stats">

                ${statCard(
                    "TOTAL VEHICLES",
                    total,
                    "Vehicles monitored"
                )}

                ${statCard(
                    "HEALTHY",
                    healthy,
                    "Battery systems"
                )}

                ${statCard(
                    "WARNING",
                    warning,
                    "Needs attention"
                )}

                ${statCard(
                    "CRITICAL",
                    critical,
                    "Immediate review"
                )}

                ${statCard(
                    "AVERAGE SOC",
                    `${avgSOC.toFixed(1)}%`,
                    "Fleet state of charge"
                )}

                ${statCard(
                    "AVERAGE SOH",
                    `${avgSOH.toFixed(1)}%`,
                    "Fleet state of health"
                )}

            </div>

            <div class="voltiq-panel">

                <div class="voltiq-panel-header">

                    <div>
                        <h2>
                            Fleet Vehicles
                        </h2>

                        <p>
                            Live vehicle battery status
                        </p>
                    </div>

                    <input
                        id="voltiq-search"
                        class="voltiq-search"
                        placeholder="Search vehicle..."
                    />

                </div>

                <div
                    id="voltiq-vehicle-grid"
                    class="voltiq-grid"
                >
                    ${renderVehicleCards()}
                </div>

            </div>

            ${renderFleetHealth()}

        </section>
    `;
}


/* ======================================================
   USER DASHBOARD
====================================================== */

function renderUserDashboard() {

    const vehicle =
        vehicles[0];

    if (!vehicle) {

        return `
            <section>

                <div class="voltiq-page-heading">

                    <div>

                        <div class="voltiq-eyebrow">
                            USER PORTAL
                        </div>

                        <h1>
                            My EV Battery
                        </h1>

                    </div>

                </div>

                <div class="voltiq-panel">

                    <h2>
                        No Vehicle Assigned
                    </h2>

                    <p>
                        Please ask the fleet administrator
                        to assign a vehicle to your account.
                    </p>

                </div>

            </section>
        `;
    }

    const battery =
        vehicle.battery || {};

    const status =
        getBatteryStatus(battery);

    return `
        <section>

            <div class="voltiq-page-heading">

                <div>

                    <div class="voltiq-eyebrow">
                        MY VEHICLE
                    </div>

                    <h1>
                        Battery Intelligence
                    </h1>

                    <p>
                        Monitor your assigned EV battery.
                    </p>

                </div>

                <div class="voltiq-access">
                    USER ACCESS
                </div>

            </div>

            <div class="voltiq-panel">

                <div class="voltiq-vehicle-title">

                    <div>

                        <div class="voltiq-eyebrow">
                            VEHICLE ONLINE
                        </div>

                        <h2>
                            ${escapeHTML(
                                vehicle.vehicle_id ||
                                "EV"
                            )}
                        </h2>

                        <p>
                            ${escapeHTML(
                                vehicle.name ||
                                vehicle.model ||
                                "My EV"
                            )}
                        </p>

                    </div>

                    <span class="
                        voltiq-status
                        ${status.toLowerCase()}
                    ">
                        ${status}
                    </span>

                </div>

                <div class="voltiq-stats">

                    ${statCard(
                        "STATE OF CHARGE",
                        `${number(battery.soc)}%`,
                        "Current battery level"
                    )}

                    ${statCard(
                        "STATE OF HEALTH",
                        `${number(battery.soh)}%`,
                        "Battery condition"
                    )}

                    ${statCard(
                        "TEMPERATURE",
                        `${number(battery.temperature)}°C`,
                        "Battery temperature"
                    )}

                    ${statCard(
                        "VOLTAGE",
                        `${number(battery.voltage)} V`,
                        "Pack voltage"
                    )}

                </div>

            </div>

            <div class="voltiq-panel">

                <h2>
                    Battery Condition
                </h2>

                ${renderBatteryExplanation(battery)}

            </div>

            <div class="voltiq-panel">

                <h2>
                    Vehicle Actions
                </h2>

                <div class="voltiq-actions">

                    <button
                        class="voltiq-action"
                        data-action="refresh"
                    >
                        Refresh Battery
                    </button>

                    <button
                        class="voltiq-action"
                        data-action="report"
                    >
                        Generate Report
                    </button>

                    <button
                        class="voltiq-action"
                        data-action="whatsapp"
                    >
                        WhatsApp Alert
                    </button>

                    <button
                        class="voltiq-action"
                        data-action="email"
                    >
                        Email Alert
                    </button>

                </div>

            </div>

        </section>
    `;
}


/* ======================================================
   VEHICLES
====================================================== */

function renderVehicleCards(list = vehicles) {

    if (!list.length) {

        return `
            <div class="voltiq-empty">
                No vehicles found.
            </div>
        `;
    }

    return list.map(vehicle => {

        const battery =
            vehicle.battery || {};

        const status =
            getBatteryStatus(battery);

        return `
            <div
                class="voltiq-vehicle-card"
                data-vehicle-id="${escapeHTML(
                    vehicle.vehicle_id || ""
                )}"
            >

                <div class="voltiq-card-top">

                    <strong>
                        ${escapeHTML(
                            vehicle.vehicle_id ||
                            "EV"
                        )}
                    </strong>

                    <span class="
                        voltiq-status
                        ${status.toLowerCase()}
                    ">
                        ${status}
                    </span>

                </div>

                <h3>
                    ${escapeHTML(
                        vehicle.name ||
                        vehicle.model ||
                        "EV Vehicle"
                    )}
                </h3>

                <p>
                    ${escapeHTML(
                        vehicle.model ||
                        "Electric Vehicle"
                    )}
                </p>

                <div class="voltiq-mini-grid">

                    <div>
                        <small>SOC</small>
                        <strong>
                            ${number(battery.soc)}%
                        </strong>
                    </div>

                    <div>
                        <small>SOH</small>
                        <strong>
                            ${number(battery.soh)}%
                        </strong>
                    </div>

                    <div>
                        <small>TEMP</small>
                        <strong>
                            ${number(
                                battery.temperature
                            )}°C
                        </strong>
                    </div>

                </div>

                <button
                    class="voltiq-view-button"
                    data-view-vehicle="${escapeHTML(
                        vehicle.vehicle_id || ""
                    )}"
                >
                    View Battery
                </button>

            </div>
        `;

    }).join("");
}


async function openVehicle(vehicleId) {

    try {

        const data =
            await apiRequest(
                `/api/vehicles/${encodeURIComponent(vehicleId)}`
            );

        selectedVehicle =
            data.vehicle || data;

        showVehicleModal(
            selectedVehicle
        );

    } catch (error) {

        if (error.message !== "SESSION_EXPIRED") {
            showToast(error.message);
        }
    }
}


function showVehicleModal(vehicle) {

    const old =
        document.getElementById(
            "voltiq-modal"
        );

    if (old) {
        old.remove();
    }

    const battery =
        vehicle.battery || {};

    const modal =
        document.createElement("div");

    modal.id =
        "voltiq-modal";

    modal.innerHTML = `
        <div class="voltiq-modal-backdrop">

            <div class="voltiq-modal-card">

                <button
                    class="voltiq-close"
                    id="voltiq-close-modal"
                >
                    ×
                </button>

                <div class="voltiq-eyebrow">
                    BATTERY DETAIL
                </div>

                <h2>
                    ${escapeHTML(
                        vehicle.vehicle_id ||
                        "EV"
                    )}
                </h2>

                <p>
                    ${escapeHTML(
                        vehicle.name ||
                        vehicle.model ||
                        "Electric Vehicle"
                    )}
                </p>

                <div class="voltiq-stats">

                    ${statCard(
                        "SOC",
                        `${number(battery.soc)}%`,
                        "State of charge"
                    )}

                    ${statCard(
                        "SOH",
                        `${number(battery.soh)}%`,
                        "State of health"
                    )}

                    ${statCard(
                        "TEMPERATURE",
                        `${number(
                            battery.temperature
                        )}°C`,
                        "Battery temperature"
                    )}

                    ${statCard(
                        "VOLTAGE",
                        `${number(
                            battery.voltage
                        )} V`,
                        "Pack voltage"
                    )}

                    ${statCard(
                        "CURRENT",
                        `${number(
                            battery.current
                        )} A`,
                        "Battery current"
                    )}

                    ${statCard(
                        "POWER",
                        `${number(
                            battery.power
                        )} kW`,
                        "Battery power"
                    )}

                </div>

                ${renderBatteryExplanation(
                    battery
                )}

            </div>

        </div>
    `;

    document.body.appendChild(modal);

    document
        .getElementById(
            "voltiq-close-modal"
        )
        .addEventListener(
            "click",
            () => modal.remove()
        );
}


/* ======================================================
   BATTERY HEALTH
====================================================== */

function getBatteryStatus(battery) {

    const soh =
        Number(battery.soh ?? 100);

    const temperature =
        Number(
            battery.temperature ?? 25
        );

    if (
        soh < 70 ||
        temperature >= 55
    ) {
        return "CRITICAL";
    }

    if (
        soh < 85 ||
        temperature >= 45
    ) {
        return "WARNING";
    }

    return "HEALTHY";
}


function renderBatteryExplanation(battery) {

    const status =
        getBatteryStatus(battery);

    let message = "";

    if (status === "HEALTHY") {

        message =
            "Battery parameters are currently within the normal operating range.";

    } else if (status === "WARNING") {

        message =
            "Battery parameters require monitoring. Review temperature and state-of-health trends.";

    } else {

        message =
            "Battery condition requires immediate attention. Review the vehicle and battery telemetry.";

    }

    return `
        <div class="
            voltiq-health-box
            ${status.toLowerCase()}
        ">

            <strong>
                ${status}
            </strong>

            <p>
                ${message}
            </p>

            <div class="voltiq-health-values">

                <div>
                    <small>SOC</small>
                    <strong>
                        ${number(battery.soc)}%
                    </strong>
                </div>

                <div>
                    <small>SOH</small>
                    <strong>
                        ${number(battery.soh)}%
                    </strong>
                </div>

                <div>
                    <small>TEMP</small>
                    <strong>
                        ${number(
                            battery.temperature
                        )}°C
                    </strong>
                </div>

            </div>

        </div>
    `;
}


function renderFleetHealth() {

    if (!vehicles.length) {
        return "";
    }

    const weakest =
        findWeakestVehicle();

    if (!weakest) {
        return "";
    }

    const battery =
        weakest.battery || {};

    return `
        <div class="voltiq-panel">

            <h2>
                Weakest Battery
            </h2>

            <div class="voltiq-weak">

                <div>
                    <strong>
                        ${escapeHTML(
                            weakest.vehicle_id ||
                            "EV"
                        )}
                    </strong>

                    <p>
                        ${escapeHTML(
                            weakest.name ||
                            weakest.model ||
                            "Vehicle"
                        )}
                    </p>
                </div>

                <div>
                    <strong>
                        SOH ${number(
                            battery.soh
                        )}%
                    </strong>

                    <p>
                        Temperature:
                        ${number(
                            battery.temperature
                        )}°C
                    </p>
                </div>

            </div>

        </div>
    `;
}


/* ======================================================
   EVENTS
====================================================== */

function setupDashboardEvents() {

    const logout =
        document.getElementById(
            "voltiq-logout"
        );

    if (logout) {
        logout.onclick =
            logoutUser;
    }

    document
        .querySelectorAll(
            "[data-view-vehicle]"
        )
        .forEach(button => {

            button.addEventListener(
                "click",
                event => {

                    event.stopPropagation();

                    openVehicle(
                        button.dataset.viewVehicle
                    );
                }
            );
        });

    document
        .querySelectorAll(
            ".voltiq-vehicle-card"
        )
        .forEach(card => {

            card.addEventListener(
                "click",
                event => {

                    if (
                        event.target.closest(
                            "button"
                        )
                    ) {
                        return;
                    }

                    openVehicle(
                        card.dataset.vehicleId
                    );
                }
            );
        });

    const search =
        document.getElementById(
            "voltiq-search"
        );

    if (search) {

        search.addEventListener(
            "input",
            () => {

                const value =
                    search.value
                        .trim()
                        .toLowerCase();

                const filtered =
                    vehicles.filter(vehicle => {

                        return (
                            String(
                                vehicle.vehicle_id ||
                                ""
                            )
                            .toLowerCase()
                            .includes(value)
                            ||
                            String(
                                vehicle.name ||
                                ""
                            )
                            .toLowerCase()
                            .includes(value)
                            ||
                            String(
                                vehicle.model ||
                                ""
                            )
                            .toLowerCase()
                            .includes(value)
                        );

                    });

                const grid =
                    document.getElementById(
                        "voltiq-vehicle-grid"
                    );

                if (grid) {
                    grid.innerHTML =
                        renderVehicleCards(
                            filtered
                        );

                    setupDashboardEvents();
                }
            }
        );
    }

    document
        .querySelectorAll(
            "[data-action]"
        )
        .forEach(button => {

            button.addEventListener(
                "click",
                async () => {

                    const action =
                        button.dataset.action;

                    const vehicle =
                        vehicles[0];

                    if (!vehicle) {
                        return;
                    }

                    if (action === "refresh") {
                        await refreshApplication();
                    }

                    if (action === "report") {
                        generateReport(vehicle);
                    }

                    if (action === "whatsapp") {
                        sendWhatsApp(vehicle);
                    }

                    if (action === "email") {
                        sendEmail(vehicle);
                    }
                }
            );
        });
}


/* ======================================================
   REFRESH
====================================================== */

async function refreshApplication() {

    try {

        const data =
            await apiRequest(
                "/api/vehicles"
            );

        vehicles =
            Array.isArray(data.vehicles)
                ? data.vehicles
                : vehicles;

        currentRole =
            String(
                data.role ||
                currentRole ||
                "user"
            ).toLowerCase();

        renderApplication();

        showToast(
            "Battery data refreshed."
        );

    } catch (error) {

        if (
            error.message !==
            "SESSION_EXPIRED"
        ) {
            showToast(
                error.message
            );
        }
    }
}


function startAutoRefresh() {

    if (refreshTimer) {
        clearInterval(refreshTimer);
    }

    refreshTimer =
        setInterval(
            async () => {

                if (
                    !getAccessToken()
                ) {
                    return;
                }

                try {

                    const data =
                        await apiRequest(
                            "/api/vehicles"
                        );

                    vehicles =
                        Array.isArray(
                            data.vehicles
                        )
                            ? data.vehicles
                            : vehicles;

                    currentRole =
                        String(
                            data.role ||
                            currentRole ||
                            "user"
                        ).toLowerCase();

                    renderApplication();

                } catch (error) {

                    console.error(
                        "Auto refresh:",
                        error
                    );
                }

            },
            30000
        );
}


/* ======================================================
   REPORT
====================================================== */

function generateReport(vehicle) {

    if (!vehicle) {
        showToast(
            "No vehicle selected."
        );
        return;
    }

    const battery =
        vehicle.battery || {};

    const report = `
VOLTIQ
EV BATTERY INTELLIGENCE REPORT
================================

Vehicle:
${vehicle.vehicle_id || "N/A"}

Name:
${vehicle.name || vehicle.model || "N/A"}

Battery Health:
${number(battery.soh)}%

State of Charge:
${number(battery.soc)}%

Temperature:
${number(battery.temperature)} °C

Voltage:
${number(battery.voltage)} V

Current:
${number(battery.current)} A

Power:
${number(battery.power)} kW

Battery Status:
${getBatteryStatus(battery)}

Generated:
${new Date().toLocaleString()}

================================
EV Battery Intelligence Platform
`;

    const blob =
        new Blob(
            [report],
            {
                type: "text/plain"
            }
        );

    const url =
        URL.createObjectURL(blob);

    const link =
        document.createElement("a");

    link.href = url;

    link.download =
        `${vehicle.vehicle_id || "EV"}-battery-report.txt`;

    link.click();

    URL.revokeObjectURL(url);

    showToast(
        "Battery report generated."
    );
}


/* ======================================================
   COMMUNICATION
====================================================== */

function sendWhatsApp(vehicle) {

    if (!vehicle) {
        return;
    }

    const battery =
        vehicle.battery || {};

    const message =
        `VoltIQ EV Battery Alert

Vehicle: ${vehicle.vehicle_id || "EV"}

Battery Status: ${getBatteryStatus(battery)}

SOC: ${number(battery.soc)}%
SOH: ${number(battery.soh)}%
Temperature: ${number(battery.temperature)}°C`;

    window.open(
        `https://wa.me/?text=${encodeURIComponent(
            message
        )}`,
        "_blank"
    );
}


function sendEmail(vehicle) {

    if (!vehicle) {
        return;
    }

    const battery =
        vehicle.battery || {};

    const subject =
        `EV Battery Alert - ${vehicle.vehicle_id || "EV"}`;

    const body =
        `VoltIQ Battery Alert

Vehicle: ${vehicle.vehicle_id || "EV"}

Status: ${getBatteryStatus(battery)}

SOC: ${number(battery.soc)}%
SOH: ${number(battery.soh)}%
Temperature: ${number(battery.temperature)}°C`;

    window.location.href =
        `mailto:?subject=${encodeURIComponent(
            subject
        )}&body=${encodeURIComponent(
            body
        )}`;
}


/* ======================================================
   LOGOUT
====================================================== */

function logoutUser() {

    if (refreshTimer) {
        clearInterval(
            refreshTimer
        );

        refreshTimer = null;
    }

    clearAuthentication();

    const app =
        document.getElementById(
            "voltiq-application"
        );

    if (app) {
        app.remove();
    }

    showLoginScreen();

    showToast(
        "Logged out successfully."
    );
}


/* ======================================================
   HELPERS
====================================================== */

function calculateAverage(field) {

    if (!vehicles.length) {
        return 0;
    }

    const values =
        vehicles
            .map(
                vehicle =>
                    Number(
                        vehicle.battery?.[field]
                    )
            )
            .filter(
                value =>
                    Number.isFinite(value)
            );

    if (!values.length) {
        return 0;
    }

    return (
        values.reduce(
            (sum, value) =>
                sum + value,
            0
        ) /
        values.length
    );
}


function findWeakestVehicle() {

    if (!vehicles.length) {
        return null;
    }

    return vehicles.reduce(
        (weakest, vehicle) => {

            const currentSOH =
                Number(
                    vehicle.battery?.soh ??
                    100
                );

            if (!weakest) {
                return vehicle;
            }

            const weakestSOH =
                Number(
                    weakest.battery?.soh ??
                    100
                );

            return currentSOH <
                weakestSOH
                ? vehicle
                : weakest;

        },
        null
    );
}


function statCard(
    title,
    value,
    description
) {

    return `
        <div class="voltiq-stat-card">

            <div class="voltiq-stat-title">
                ${escapeHTML(title)}
            </div>

            <div class="voltiq-stat-value">
                ${escapeHTML(String(value))}
            </div>

            <div class="voltiq-stat-description">
                ${escapeHTML(description)}
            </div>

        </div>
    `;
}


function number(value) {

    const n =
        Number(value);

    if (!Number.isFinite(n)) {
        return "0";
    }

    return n.toFixed(1);
}


function escapeHTML(value) {

    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function showToast(message) {

    let toast =
        document.getElementById(
            "voltiq-toast"
        );

    if (!toast) {

        toast =
            document.createElement("div");

        toast.id =
            "voltiq-toast";

        document.body.appendChild(
            toast
        );
    }

    toast.textContent =
        message;

    toast.classList.add(
        "show"
    );

    setTimeout(
        () => {
            toast.classList.remove(
                "show"
            );
        },
        3000
    );
}


/* ======================================================
   STYLES
====================================================== */

function injectApplicationStyles() {

    if (
        document.getElementById(
            "voltiq-runtime-styles"
        )
    ) {
        return;
    }

    const style =
        document.createElement("style");

    style.id =
        "voltiq-runtime-styles";

    style.textContent = `

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family:
        Inter,
        Arial,
        Helvetica,
        sans-serif;
    background: #03100a;
    color: #ecfff3;
}

button,
input {
    font: inherit;
}

.voltiq-logged-out {
    overflow: hidden;
}

#voltiq-login-screen {
    position: fixed;
    inset: 0;
    z-index: 999999;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    background:
        radial-gradient(
            circle at top,
            #123b25,
            #03100a 60%
        );
}

.voltiq-login-card {
    width: min(460px, 100%);
    padding: 38px;
    border: 1px solid
        rgba(72, 255, 143, .2);
    border-radius: 24px;
    background:
        rgba(6, 23, 15, .97);
    box-shadow:
        0 30px 80px
        rgba(0, 0, 0, .5);
}

.voltiq-logo {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 28px;
}

.voltiq-logo-icon {
    width: 48px;
    height: 48px;
    display: grid;
    place-items: center;
    border-radius: 14px;
    background: #35e982;
    color: #03100a;
    font-size: 25px;
    font-weight: 900;
}

.voltiq-logo-icon.small {
    width: 40px;
    height: 40px;
    font-size: 20px;
}

.voltiq-brand {
    font-size: 24px;
    font-weight: 900;
}

.voltiq-brand-sub {
    margin-top: 3px;
    color: #6e9a7d;
    font-size: 10px;
    letter-spacing: 2px;
}

.voltiq-login-card h1 {
    margin: 0 0 10px;
    font-size: 30px;
}

.voltiq-login-text {
    color: #8eac9a;
    line-height: 1.6;
}

.voltiq-login-card label {
    display: block;
    margin: 20px 0 8px;
    color: #a8c6b3;
    font-size: 13px;
}

.voltiq-login-card input {
    width: 100%;
    padding: 14px 15px;
    border: 1px solid
        rgba(255,255,255,.1);
    border-radius: 10px;
    outline: none;
    background: #091c12;
    color: white;
}

.voltiq-login-card input:focus {
    border-color: #35e982;
}

#voltiq-login-button {
    width: 100%;
    margin-top: 24px;
    padding: 14px;
    border: 0;
    border-radius: 10px;
    background: #35e982;
    color: #03100a;
    font-weight: 900;
    cursor: pointer;
}

#voltiq-login-button:disabled {
    opacity: .6;
    cursor: wait;
}

.voltiq-login-error {
    min-height: 24px;
    margin-top: 12px;
    color: #ff7777;
    font-size: 13px;
}

.voltiq-demo {
    margin-top: 25px;
    padding: 15px;
    border-radius: 12px;
    background: rgba(255,255,255,.04);
    color: #789686;
    font-size: 12px;
    line-height: 1.7;
}

.voltiq-demo strong {
    display: block;
    color: #dffff0;
    margin-bottom: 5px;
}

.voltiq-shell {
    min-height: 100vh;
}

.voltiq-header {
    min-height: 75px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    padding: 14px 30px;
    border-bottom: 1px solid
        rgba(255,255,255,.07);
    background: #06170f;
}

.voltiq-header-brand,
.voltiq-header-user {
    display: flex;
    align-items: center;
    gap: 12px;
}

.voltiq-header-brand strong {
    display: block;
    font-size: 20px;
}

.voltiq-header-brand span {
    display: block;
    margin-top: 2px;
    color: #5f8c70;
    font-size: 8px;
    letter-spacing: 1.5px;
}

.voltiq-user-info {
    text-align: right;
}

.voltiq-user-info strong {
    display: block;
}

.voltiq-user-info span {
    display: block;
    margin-top: 3px;
    color: #6e9580;
    font-size: 11px;
}

.voltiq-role-badge,
.voltiq-access {
    padding: 7px 11px;
    border-radius: 8px;
    font-size: 10px;
    font-weight: 900;
}

.voltiq-role-badge.admin,
.voltiq-access {
    background: rgba(255, 180, 70, .12);
    color: #ffca70;
}

.voltiq-role-badge.user {
    background: rgba(53,233,130,.1);
    color: #58ef98;
}

.voltiq-logout {
    padding: 9px 13px;
    border: 1px solid
        rgba(255,255,255,.1);
    border-radius: 8px;
    background: transparent;
    color: #b4cabc;
    cursor: pointer;
}

.voltiq-logout:hover {
    background: rgba(255,255,255,.06);
}

.voltiq-main {
    max-width: 1500px;
    margin: auto;
    padding: 35px;
}

.voltiq-page-heading {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 20px;
    margin-bottom: 30px;
}

.voltiq-page-heading h1 {
    margin: 7px 0;
    font-size: 32px;
}

.voltiq-page-heading p {
    margin: 0;
    color: #759584;
}

.voltiq-eyebrow {
    color: #45e88b;
    font-size: 10px;
    font-weight: 900;
    letter-spacing: 2px;
}

.voltiq-stats {
    display: grid;
    grid-template-columns:
        repeat(auto-fit, minmax(170px, 1fr));
    gap: 15px;
    margin-bottom: 22px;
}

.voltiq-stat-card {
    padding: 20px;
    border: 1px solid
        rgba(255,255,255,.07);
    border-radius: 16px;
    background: #071910;
}

.voltiq-stat-title {
    color: #709080;
    font-size: 10px;
    font-weight: 800;
}

.voltiq-stat-value {
    margin-top: 10px;
    font-size: 28px;
    font-weight: 900;
}

.voltiq-stat-description {
    margin-top: 5px;
    color: #597464;
    font-size: 11px;
}

.voltiq-panel {
    margin-top: 20px;
    padding: 25px;
    border: 1px solid
        rgba(255,255,255,.07);
    border-radius: 18px;
    background: #06160e;
}

.voltiq-panel h2 {
    margin-top: 0;
}

.voltiq-panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    margin-bottom: 20px;
}

.voltiq-panel-header p {
    color: #658171;
}

.voltiq-search {
    width: 250px;
    padding: 12px;
    border: 1px solid
        rgba(255,255,255,.1);
    border-radius: 9px;
    background: #091c12;
    color: white;
}

.voltiq-grid {
    display: grid;
    grid-template-columns:
        repeat(auto-fill, minmax(260px, 1fr));
    gap: 15px;
}

.voltiq-vehicle-card {
    padding: 18px;
    border: 1px solid
        rgba(255,255,255,.07);
    border-radius: 15px;
    background: #081c12;
    transition: .2s;
}

.voltiq-vehicle-card:hover {
    transform: translateY(-2px);
    border-color:
        rgba(53,233,130,.3);
}

.voltiq-card-top,
.voltiq-vehicle-title,
.voltiq-weak {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 15px;
}

.voltiq-vehicle-card h3 {
    margin: 15px 0 5px;
}

.voltiq-vehicle-card p {
    margin: 0 0 15px;
    color: #678575;
}

.voltiq-status {
    display: inline-block;
    padding: 5px 8px;
    border-radius: 7px;
    font-size: 9px;
    font-weight: 900;
}

.voltiq-status.healthy {
    background: rgba(53,233,130,.1);
    color: #50ed94;
}

.voltiq-status.warning {
    background: rgba(255,188,72,.1);
    color: #ffc45e;
}

.voltiq-status.critical {
    background: rgba(255,80,80,.1);
    color: #ff7474;
}

.voltiq-mini-grid {
    display: grid;
    grid-template-columns:
        repeat(3, 1fr);
    gap: 8px;
    margin-top: 15px;
}

.voltiq-mini-grid div {
    padding: 10px;
    border-radius: 9px;
    background: rgba(255,255,255,.035);
}

.voltiq-mini-grid small {
    display: block;
    color: #557363;
    font-size: 9px;
}

.voltiq-mini-grid strong {
    display: block;
    margin-top: 4px;
}

.voltiq-view-button,
.voltiq-action {
    width: 100%;
    margin-top: 15px;
    padding: 11px;
    border: 1px solid
        rgba(53,233,130,.18);
    border-radius: 9px;
    background: rgba(53,233,130,.07);
    color: #61ed9c;
    cursor: pointer;
}

.voltiq-view-button:hover,
.voltiq-action:hover {
    background: rgba(53,233,130,.14);
}

.voltiq-actions {
    display: grid;
    grid-template-columns:
        repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px;
}

.voltiq-actions .voltiq-action {
    margin-top: 0;
}

.voltiq-health-box {
    padding: 20px;
    border-radius: 15px;
    background: rgba(255,255,255,.035);
}

.voltiq-health-box.healthy {
    border-left: 4px solid #35e982;
}

.voltiq-health-box.warning {
    border-left: 4px solid #ffc45e;
}

.voltiq-health-box.critical {
    border-left: 4px solid #ff6464;
}

.voltiq-health-box p {
    color: #799688;
    line-height: 1.6;
}

.voltiq-health-values {
    display: grid;
    grid-template-columns:
        repeat(3, 1fr);
    gap: 10px;
    margin-top: 15px;
}

.voltiq-health-values div {
    padding: 12px;
    border-radius: 9px;
    background: rgba(255,255,255,.035);
}

.voltiq-health-values small {
    color: #5d7969;
    font-size: 9px;
}

.voltiq-health-values strong {
    display: block;
    margin-top: 4px;
}

.voltiq-weak {
    padding: 15px;
    border-radius: 12px;
    background: rgba(255,255,255,.03);
}

.voltiq-weak p {
    color: #698475;
}

.voltiq-empty {
    padding: 30px;
    color: #668174;
    text-align: center;
}

.voltiq-footer {
    padding: 25px;
    text-align: center;
    color: #466352;
    font-size: 11px;
}

#voltiq-toast {
    position: fixed;
    right: 25px;
    bottom: 25px;
    z-index: 1000000;
    max-width: 350px;
    padding: 14px 18px;
    border-radius: 10px;
    background: #183526;
    color: #eafff1;
    box-shadow:
        0 10px 30px
        rgba(0,0,0,.4);
    transform: translateY(120px);
    opacity: 0;
    transition: .25s;
}

#voltiq-toast.show {
    transform: translateY(0);
    opacity: 1;
}

#voltiq-modal {
    position: fixed;
    inset: 0;
    z-index: 999990;
}

.voltiq-modal-backdrop {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    background: rgba(0,0,0,.75);
}

.voltiq-modal-card {
    position: relative;
    width: min(850px, 100%);
    max-height: 90vh;
    overflow: auto;
    padding: 30px;
    border-radius: 20px;
    background: #06170f;
    border: 1px solid
        rgba(53,233,130,.15);
}

.voltiq-close {
    position: absolute;
    right: 15px;
    top: 15px;
    width: 35px;
    height: 35px;
    border: 0;
    border-radius: 50%;
    background: rgba(255,255,255,.07);
    color: white;
    font-size: 22px;
    cursor: pointer;
}

@media(max-width: 750px) {

    .voltiq-header {
        flex-direction: column;
        align-items: flex-start;
        padding: 15px;
    }

    .voltiq-header-user {
        width: 100%;
        justify-content: space-between;
    }

    .voltiq-main {
        padding: 18px;
    }

    .voltiq-page-heading,
    .voltiq-panel-header {
        flex-direction: column;
        align-items: stretch;
    }

    .voltiq-search {
        width: 100%;
    }

    .voltiq-user-info {
        text-align: left;
    }

    .voltiq-health-values {
        grid-template-columns: 1fr;
    }
}

`;

    document.head.appendChild(
        style
    );
}


/* ======================================================
   START
====================================================== */

document.addEventListener(
    "DOMContentLoaded",
    () => {
        startApplication();
    }
);


/* ======================================================
   GLOBAL ACCESS
====================================================== */

window.loginUser =
    loginUser;

window.logoutUser =
    logoutUser;

window.refreshApplication =
    refreshApplication;

window.generateReport =
    generateReport;

window.sendWhatsApp =
    sendWhatsApp;

window.sendEmail =
    sendEmail;

window.openVehicle =
    openVehicle;

window.getAccessToken =
    getAccessToken;

window.clearAuthentication =
    clearAuthentication;
    /* ======================================================
   LEGACY LOGIN COMPATIBILITY FIX
   Supports the original index.html login form
====================================================== */

async function login() {

    const emailInput =
        document.getElementById("loginEmail");

    const passwordInput =
        document.getElementById("loginPassword");

    const message =
        document.getElementById("loginMessage");

    if (!emailInput || !passwordInput) {

        console.error(
            "Original login fields were not found."
        );

        return;
    }

    const email =
        emailInput.value.trim();

    const password =
        passwordInput.value.trim();

    if (!email || !password) {

        if (message) {
            message.textContent =
                "Please enter your email and password.";
        }

        return;
    }

    if (message) {
        message.textContent =
            "Signing in...";
    }

    try {

        const data =
            await loginUser(email, password);

        /*
           Hide the ORIGINAL login screen
           from index.html.
        */

        const loginScreen =
            document.getElementById("loginScreen");

        if (loginScreen) {
            loginScreen.classList.add("hidden");
        }

        /*
           Show the original dashboard.
        */

        const app =
            document.getElementById("app");

        if (app) {
            app.classList.remove("hidden");
        }

        /*
           Update original user labels.
        */

        const loggedUser =
            document.getElementById("loggedUser");

        const loggedRole =
            document.getElementById("loggedRole");

        if (loggedUser) {

            loggedUser.textContent =
                data.user?.name ||
                (
                    currentRole === "admin"
                        ? "Administrator"
                        : "Operator"
                );
        }

        if (loggedRole) {

            loggedRole.textContent =
                currentRole === "admin"
                    ? "Administrator"
                    : "Operator";
        }

        /*
           Hide the newer dynamically-created
           login screen too.
        */

        const newLoginScreen =
            document.getElementById(
                "voltiq-login-screen"
            );

        if (newLoginScreen) {
            newLoginScreen.style.display = "none";
        }

        if (message) {
            message.textContent = "";
        }

        console.log(
            "LOGIN SUCCESS:",
            data.user
        );

    } catch (error) {

        console.error(
            "LOGIN ERROR:",
            error
        );

        if (message) {

            message.textContent =
                error.message ||
                "Login failed.";
        }
    }
}


/*
   Make login() available to the original
   index.html form.
*/

window.login = login;
/* =========================================================
   FINAL LOGIN + RESPONSIVE ADMIN SIDEBAR FIX
   Paste this entire block at the END of app.js
========================================================= */

(function () {

    "use strict";

    /* =====================================================
       LOGIN FIX
    ===================================================== */

    async function finalLogin() {

        const emailInput =
            document.getElementById("loginEmail");

        const passwordInput =
            document.getElementById("loginPassword");

        const message =
            document.getElementById("loginMessage");

        const loginScreen =
            document.getElementById("loginScreen");

        const app =
            document.getElementById("app");

        if (!emailInput || !passwordInput) {

            console.error(
                "Login fields not found."
            );

            return;
        }

        const email =
            emailInput.value.trim().toLowerCase();

        const password =
            passwordInput.value.trim();

        if (!email || !password) {

            if (message) {
                message.textContent =
                    "Please enter your email and password.";
            }

            return;
        }

        if (message) {
            message.textContent =
                "Signing in...";
        }

        try {

            /* ---------------------------------------------
               SEND LOGIN TO FASTAPI
            --------------------------------------------- */

            const response =
                await fetch(
                    "/api/auth/login",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json",

                            "Accept":
                                "application/json"
                        },

                        body: JSON.stringify({
                            email: email,
                            password: password
                        })
                    }
                );

            let data = {};

            try {
                data = await response.json();
            } catch (e) {
                data = {};
            }

            if (!response.ok) {

                throw new Error(
                    data.detail ||
                    data.message ||
                    "Incorrect email or password."
                );
            }

            if (!data.access_token) {

                throw new Error(
                    "Login succeeded but no access token was returned."
                );
            }

            /* ---------------------------------------------
               SAVE SESSION
            --------------------------------------------- */

            localStorage.setItem(
                "access_token",
                data.access_token
            );

            localStorage.setItem(
                "logged_in",
                "true"
            );

            if (data.user) {

                localStorage.setItem(
                    "current_user",
                    JSON.stringify(data.user)
                );

                currentUser = data.user;

                currentRole =
                    String(
                        data.user.role || "user"
                    ).toLowerCase();
            }

            console.log(
                "Backend login successful:",
                data.user
            );

            /* ---------------------------------------------
               HIDE LOGIN SCREEN
            --------------------------------------------- */

            if (loginScreen) {
                loginScreen.classList.add("hidden");
                loginScreen.style.display = "none";
            }

            const voltiqLogin =
                document.getElementById(
                    "voltiq-login-screen"
                );

            if (voltiqLogin) {
                voltiqLogin.style.display = "none";
            }

            /* ---------------------------------------------
               SHOW APPLICATION
            --------------------------------------------- */

            if (app) {

                app.classList.remove("hidden");

                app.style.display = "";
            }

            /* ---------------------------------------------
               USER INFORMATION
            --------------------------------------------- */

            const loggedUser =
                document.getElementById(
                    "loggedUser"
                );

            const loggedRole =
                document.getElementById(
                    "loggedRole"
                );

            if (loggedUser) {

                loggedUser.textContent =
                    data.user?.name ||
                    (
                        currentRole === "admin"
                            ? "EV Battery Admin"
                            : "EV Battery User"
                    );
            }

            if (loggedRole) {

                loggedRole.textContent =
                    currentRole === "admin"
                        ? "Fleet Administrator"
                        : "Vehicle Operator";
            }

            /* ---------------------------------------------
               LOAD VEHICLES
            --------------------------------------------- */

            try {

                const vehicleResponse =
                    await fetch(
                        "/api/vehicles",
                        {
                            method: "GET",

                            headers: {
                                "Accept":
                                    "application/json",

                                "Authorization":
                                    `Bearer ${data.access_token}`
                            }
                        }
                    );

                if (vehicleResponse.ok) {

                    const vehicleData =
                        await vehicleResponse.json();

                    vehicles =
                        Array.isArray(
                            vehicleData.vehicles
                        )
                            ? vehicleData.vehicles
                            : [];

                    if (
                        vehicleData.role
                    ) {

                        currentRole =
                            String(
                                vehicleData.role
                            ).toLowerCase();
                    }
                }

            } catch (vehicleError) {

                console.error(
                    "Vehicle loading error:",
                    vehicleError
                );
            }

            /* ---------------------------------------------
               BUILD ROLE INTERFACE
            --------------------------------------------- */

            if (
                typeof buildRoleBasedInterface ===
                "function"
            ) {

                buildRoleBasedInterface();
            }

            if (
                typeof renderDashboard ===
                "function"
            ) {

                renderDashboard();
            }

            if (
                typeof startAutoRefresh ===
                "function"
            ) {

                startAutoRefresh();
            }

            /* ---------------------------------------------
               CLOSE MOBILE SIDEBAR
            --------------------------------------------- */

            closeBatterySidebar();

            if (message) {
                message.textContent = "";
            }

            console.log(
                "LOGIN COMPLETE — ROLE:",
                currentRole
            );

        } catch (error) {

            console.error(
                "Login error:",
                error
            );

            if (message) {

                message.textContent =
                    error.message ||
                    "Login failed. Please try again.";
            }
        }
    }


    /* =====================================================
       CONNECT LOGIN FORM
    ===================================================== */

    function connectLoginForm() {

        const form =
            document.getElementById(
                "loginForm"
            );

        if (!form) {
            return;
        }

        /*
           Remove duplicate submit handlers by cloning
           the form.
        */

        const newForm =
            form.cloneNode(true);

        form.parentNode.replaceChild(
            newForm,
            form
        );

        newForm.addEventListener(
            "submit",
            function (event) {

                event.preventDefault();

                finalLogin();
            }
        );

        const button =
            newForm.querySelector(
                'button[type="submit"]'
            );

        if (button) {

            button.addEventListener(
                "click",
                function (event) {

                    /*
                       If the button is inside a form,
                       submit will handle it.
                    */

                    if (
                        newForm.tagName
                            .toLowerCase() !==
                        "form"
                    ) {

                        event.preventDefault();

                        finalLogin();
                    }
                }
            );
        }
    }


    /* =====================================================
       RESPONSIVE ADMIN SIDEBAR
    ===================================================== */

    let batterySidebar = null;
    let batterySidebarOverlay = null;


    function findBatterySidebar() {

        if (batterySidebar) {
            return batterySidebar;
        }

        batterySidebar =
            document.querySelector(
                ".sidebar, " +
                ".side-nav, " +
                ".navigation, " +
                ".admin-sidebar, " +
                "aside"
            );

        return batterySidebar;
    }


    function createBatteryMenuButton() {

        if (
            document.getElementById(
                "battery-mobile-menu"
            )
        ) {
            return;
        }

        const button =
            document.createElement("button");

        button.id =
            "battery-mobile-menu";

        button.type =
            "button";

        button.setAttribute(
            "aria-label",
            "Open navigation menu"
        );

        button.setAttribute(
            "title",
            "Navigation"
        );

        button.innerHTML = "☰";


        button.addEventListener(
            "click",
            function () {

                toggleBatterySidebar();
            }
        );

        document.body.appendChild(
            button
        );
    }


    function createBatteryOverlay() {

        if (
            document.getElementById(
                "battery-sidebar-overlay"
            )
        ) {
            batterySidebarOverlay =
                document.getElementById(
                    "battery-sidebar-overlay"
                );

            return;
        }

        batterySidebarOverlay =
            document.createElement("div");

        batterySidebarOverlay.id =
            "battery-sidebar-overlay";

        batterySidebarOverlay.addEventListener(
            "click",
            function () {

                closeBatterySidebar();
            }
        );

        document.body.appendChild(
            batterySidebarOverlay
        );
    }


    function toggleBatterySidebar() {

        const sidebar =
            findBatterySidebar();

        if (!sidebar) {

            console.warn(
                "Admin sidebar not found."
            );

            return;
        }

        const isOpen =
            sidebar.classList.contains(
                "battery-sidebar-open"
            );

        if (isOpen) {

            closeBatterySidebar();

        } else {

            openBatterySidebar();
        }
    }


    function openBatterySidebar() {

        const sidebar =
            findBatterySidebar();

        if (!sidebar) {
            return;
        }

        sidebar.classList.add(
            "battery-sidebar-open"
        );

        if (batterySidebarOverlay) {

            batterySidebarOverlay.classList.add(
                "battery-overlay-visible"
            );
        }

        document.body.classList.add(
            "battery-menu-open"
        );
    }


    function closeBatterySidebar() {

        const sidebar =
            findBatterySidebar();

        if (sidebar) {

            sidebar.classList.remove(
                "battery-sidebar-open"
            );
        }

        if (batterySidebarOverlay) {

            batterySidebarOverlay.classList.remove(
                "battery-overlay-visible"
            );
        }

        document.body.classList.remove(
            "battery-menu-open"
        );
    }


    /* =====================================================
       SIDEBAR STYLES
    ===================================================== */

    function injectBatterySidebarStyles() {

        if (
            document.getElementById(
                "battery-responsive-styles"
            )
        ) {
            return;
        }

        const style =
            document.createElement("style");

        style.id =
            "battery-responsive-styles";

        style.textContent = `

            /* =========================================
               MOBILE MENU BUTTON
            ========================================= */

            #battery-mobile-menu {

                position: fixed;

                top: 18px;

                left: 18px;

                width: 48px;

                height: 48px;

                border-radius: 14px;

                border: 1px solid
                    rgba(255,255,255,.15);

                background:
                    rgba(12,18,22,.92);

                color: #ffffff;

                font-size: 24px;

                line-height: 1;

                cursor: pointer;

                z-index: 10001;

                display: none;

                align-items: center;

                justify-content: center;

                box-shadow:
                    0 8px 30px
                    rgba(0,0,0,.35);

                backdrop-filter:
                    blur(12px);

            }


            #battery-mobile-menu:hover {

                transform: scale(1.04);

            }


            /* =========================================
               OVERLAY
            ========================================= */

            #battery-sidebar-overlay {

                position: fixed;

                inset: 0;

                background:
                    rgba(0,0,0,.60);

                opacity: 0;

                pointer-events: none;

                transition:
                    opacity .2s ease;

                z-index: 9997;

            }


            #battery-sidebar-overlay
            .battery-overlay-visible {

                opacity: 1;

                pointer-events: auto;

            }


            #battery-sidebar-overlay
            .battery-overlay-visible {

                opacity: 1;

                pointer-events: auto;

            }


            /* =========================================
               MOBILE / TABLET
            ========================================= */

            @media (max-width: 900px) {

                #battery-mobile-menu {

                    display: flex;

                }


                .sidebar,
                .side-nav,
                .navigation,
                .admin-sidebar,
                aside {

                    position: fixed !important;

                    left: 0 !important;

                    top: 0 !important;

                    bottom: 0 !important;

                    width: 280px !important;

                    max-width: 85vw !important;

                    z-index: 9999 !important;

                    transform:
                        translateX(-105%) !important;

                    transition:
                        transform .25s ease !important;

                    overflow-y: auto !important;

                    background:
                        #10171a !important;

                    box-shadow:
                        10px 0 35px
                        rgba(0,0,0,.35);

                }


                .sidebar.battery-sidebar-open,
                .side-nav.battery-sidebar-open,
                .navigation.battery-sidebar-open,
                .admin-sidebar.battery-sidebar-open,
                aside.battery-sidebar-open {

                    transform:
                        translateX(0) !important;

                }


                #battery-sidebar-overlay
                .battery-overlay-visible {

                    opacity: 1;

                    pointer-events: auto;

                }


                body.battery-menu-open {

                    overflow: hidden;

                }

            }


            /* =========================================
               SMALL PHONE
            ========================================= */

            @media (max-width: 520px) {

                #battery-mobile-menu {

                    top: 12px;

                    left: 12px;

                    width: 44px;

                    height: 44px;

                    font-size: 21px;

                }

            }

        `;

        document.head.appendChild(
            style
        );
    }


    /* =====================================================
       INITIALIZE
    ===================================================== */

    function initializeFinalFix() {

        injectBatterySidebarStyles();

        createBatteryOverlay();

        createBatteryMenuButton();

        /*
           Connect login after the existing HTML
           has loaded.
        */

        connectLoginForm();

        /*
           Reconnect if the application dynamically
           rebuilds the page.
        */

        setTimeout(
            function () {

                connectLoginForm();

                findBatterySidebar();

            },
            500
        );

        setTimeout(
            function () {

                connectLoginForm();

                findBatterySidebar();

            },
            1500
        );
    }


    /* =====================================================
       PUBLIC FUNCTIONS
    ===================================================== */

    window.login =
        finalLogin;

    window.openBatterySidebar =
        openBatterySidebar;

    window.closeBatterySidebar =
        closeBatterySidebar;


    /* =====================================================
       START
    ===================================================== */

    if (
        document.readyState ===
        "loading"
    ) {

        document.addEventListener(
            "DOMContentLoaded",
            initializeFinalFix
        );

    } else {

        initializeFinalFix();
    }

})();
/* =========================================================
   PERMANENT LOGIN ROLE FIX
   Connects User / Admin buttons in index.html
   to the FastAPI login system.
========================================================= */

function selectRole(role) {

    role = String(role || "user").toLowerCase();

    if (role !== "admin" && role !== "user") {
        role = "user";
    }

    currentRole = role;

    /* ---------------------------------------------
       Find login fields
    --------------------------------------------- */

    const emailInput =
        document.getElementById("loginEmail");

    const passwordInput =
        document.getElementById("loginPassword");

    const message =
        document.getElementById("loginMessage");

    /* ---------------------------------------------
       Find role buttons
    --------------------------------------------- */

    const userButton =
        document.getElementById("userRoleBtn");

    const adminButton =
        document.getElementById("adminRoleBtn");

    /* ---------------------------------------------
       Update active button
    --------------------------------------------- */

    if (userButton) {
        userButton.classList.toggle(
            "active",
            role === "user"
        );

        userButton.classList.toggle(
            "selected",
            role === "user"
        );
    }

    if (adminButton) {
        adminButton.classList.toggle(
            "active",
            role === "admin"
        );

        adminButton.classList.toggle(
            "selected",
            role === "admin"
        );
    }

    /* ---------------------------------------------
       Put the correct demo credentials into fields
    --------------------------------------------- */

    if (emailInput) {

        emailInput.value =
            role === "admin"
                ? "admin@evbattery.demo"
                : "user@evbattery.demo";

        emailInput.dispatchEvent(
            new Event("input", { bubbles: true })
        );

        emailInput.dispatchEvent(
            new Event("change", { bubbles: true })
        );
    }

    if (passwordInput) {

        passwordInput.value =
            role === "admin"
                ? "admin1234"
                : "user1234";

        passwordInput.dispatchEvent(
            new Event("input", { bubbles: true })
        );

        passwordInput.dispatchEvent(
            new Event("change", { bubbles: true })
        );
    }

    /* ---------------------------------------------
       Update demo-access text if it exists
    --------------------------------------------- */

    const demo =
        document.getElementById("demoCredentials");

    if (demo) {

        demo.textContent =
            role === "admin"
                ? "Admin: admin@evbattery.demo / admin1234"
                : "User: user@evbattery.demo / user1234";
    }

    /* ---------------------------------------------
       Clear previous login error
    --------------------------------------------- */

    if (message) {
        message.textContent = "";
    }

    console.log(
        "Login role selected:",
        role
    );
}


/* Make inline onclick="selectRole(...)" work */
window.selectRole = selectRole;


/* Make sure the default User role exists on page load */
document.addEventListener("DOMContentLoaded", function () {

    const emailInput =
        document.getElementById("loginEmail");

    const passwordInput =
        document.getElementById("loginPassword");

    /*
       Only initialize if the login screen exists
       and no authenticated session is currently active.
    */

    if (
        emailInput &&
        passwordInput &&
        !localStorage.getItem("access_token")
    ) {
        selectRole("user");
    }
});