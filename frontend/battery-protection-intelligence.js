(function () {
    "use strict";

    const API_BASE = "/api/battery-intelligence-plus";
    const REFRESH_INTERVAL = 15000;

    let loading = false;
    let refreshTimer = null;

    function getToken() {
        return (
            localStorage.getItem("voltiq_token") ||
            localStorage.getItem("access_token") ||
            ""
        );
    }

    function getBatteryId() {
        let id = "";

        if (
            typeof selectedVehicleId !== "undefined" &&
            selectedVehicleId
        ) {
            id = selectedVehicleId;
        }

        if (!id) {
            id =
                localStorage.getItem("selectedBatteryId") ||
                localStorage.getItem("selectedVehicleId") ||
                localStorage.getItem("selectedVehicle") ||
                "EV-001";
        }

        id = String(id).trim().toUpperCase();

        if (id.startsWith("EV-")) {
            id = id.replace("EV-", "BAT-");
        }

        if (!id.startsWith("BAT-")) {
            id = "BAT-" + id;
        }

        return id;
    }

    function escapeHTML(value) {
        return String(value ?? "").replace(/[&<>"']/g, char => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#039;"
        })[char]);
    }

    function card(title, body, description = "") {
        return `
            <article class="vi-advanced-card">
                <h3>${escapeHTML(title)}</h3>
                ${description
                    ? `<p class="vi-card-description">${escapeHTML(description)}</p>`
                    : ""}
                <div class="vi-card-content">${body}</div>
            </article>
        `;
    }

    function list(items) {
        if (!Array.isArray(items) || !items.length) {
            return "<p>No actions or conditions reported.</p>";
        }

        return `
            <ul class="vi-list">
                ${items.map(item =>
                    `<li>${escapeHTML(item)}</li>`
                ).join("")}
            </ul>
        `;
    }

    function value(v, suffix = "") {
        if (v === null || v === undefined || v === "") {
            return "Not available";
        }

        return escapeHTML(v) + suffix;
    }

    function severityTag(level, prefix = "") {
        const key = prefix + String(level || "UNKNOWN").toLowerCase().replace(/[\s_]+/g, "-");

        return `<span class="vi-sev vi-sev-${escapeHTML(key)}">${escapeHTML(level || "UNKNOWN")}</span>`;
    }

    function renderCombinations(combination) {
        const combos = combination.combinations || [];

        if (!combos.length) {
            return "<p>No dangerous parameter combinations right now.</p>";
        }

        return combos.map(c => `
            <div class="vi-combo">
                <div>${severityTag(c.severity)} <strong>${escapeHTML(c.name)}</strong></div>
                <p class="vi-muted">${Object.entries(c.parameters || {})
                    .map(([k, v]) => escapeHTML(k.replace(/_/g, " ")) + ": " + escapeHTML(v))
                    .join(" · ")}</p>
                <p>${escapeHTML(c.explanation)}</p>
            </div>
        `).join("");
    }

    function renderTrends(trends) {
        const t = trends || {};
        const fmt = (v, unit) =>
            v === null || v === undefined
                ? "n/a"
                : (v > 0 ? "+" : "") + v + " " + unit;

        return `
            <p class="vi-muted">
                Trend (last 2 h): temperature ${escapeHTML(fmt(t.temperature_per_hour, "°C/h"))},
                voltage ${escapeHTML(fmt(t.voltage_per_hour, "V/h"))},
                current ${escapeHTML(fmt(t.current_per_hour, "A/h"))}
            </p>
        `;
    }

    function renderParameterTable(parameters) {
        if (!Array.isArray(parameters) || !parameters.length) return "";

        return `
            <table class="vi-param-table">
                <thead>
                    <tr><th>Parameter</th><th>Value</th><th>Warn</th><th>State</th></tr>
                </thead>
                <tbody>
                    ${parameters.map(p => `
                        <tr>
                            <td>${escapeHTML(p.label)}</td>
                            <td>${value(p.value, " " + p.unit)}</td>
                            <td>${escapeHTML(p.warning_threshold)}</td>
                            <td>${severityTag(p.state)}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        `;
    }

    function renderFactors(factors) {
        if (!Array.isArray(factors) || !factors.length) return "";

        return factors.map(f => {
            const pct = f.max ? Math.round((f.score / f.max) * 100) : 0;

            return `
                <div class="vi-factor">
                    <div class="vi-factor-head">
                        <span>${escapeHTML(f.factor)}</span>
                        <span>${escapeHTML(f.score)} / ${escapeHTML(f.max)}</span>
                    </div>
                    <div class="vi-factor-bar"><span style="width:${pct}%"></span></div>
                    <p class="vi-muted">${escapeHTML(f.detail)}</p>
                </div>
            `;
        }).join("");
    }

    function renderBehaviour(behaviour) {
        const metrics = behaviour.metrics || [];

        if (!metrics.length) return "";

        const resistance = behaviour.internal_resistance;

        return `
            <table class="vi-param-table">
                <thead>
                    <tr><th>Metric</th><th>Baseline</th><th>Last hour</th><th>Shift</th></tr>
                </thead>
                <tbody>
                    ${metrics.map(m => `
                        <tr>
                            <td>${escapeHTML(m.metric)}</td>
                            <td>${value(m.baseline_mean, " " + m.unit)}</td>
                            <td>${value(m.recent_mean, " " + m.unit)}</td>
                            <td>${m.changed ? severityTag("CHANGED", "beh-") : ""}${escapeHTML((m.shift > 0 ? "+" : "") + m.shift)}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
            ${resistance
                ? `<p class="vi-muted">Internal resistance: ${value(resistance.baseline_mohm, " mΩ")} →
                   ${value(resistance.recent_mohm, " mΩ")}. ${escapeHTML(resistance.detail)}</p>`
                : `<p class="vi-muted">Internal resistance: not enough current variation to estimate.</p>`}
        `;
    }

    function renderProtections(protections) {
        if (!Array.isArray(protections) || !protections.length) return "";

        return `
            <table class="vi-param-table">
                <thead>
                    <tr><th>Protection</th><th>Breaches</th><th>Failures</th><th>Learned warning</th></tr>
                </thead>
                <tbody>
                    ${protections.map(p => `
                        <tr>
                            <td>${escapeHTML(p.label)}</td>
                            <td>${escapeHTML(p.episodes)}</td>
                            <td>${escapeHTML(p.sustained_breaches + p.quick_recurrences)}</td>
                            <td>${p.learned_early_warning === null
                                ? "—"
                                : escapeHTML(p.learned_early_warning)
                                  + (p.suggest_earlier_warning ? " " + severityTag("EARLIER", "learn-") : "")}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        `;
    }

    function renderNormalRanges(ranges) {
        const entries = Object.entries(ranges || {});

        if (!entries.length) return "";

        return `
            <p class="vi-muted">Learned normal range (5th–95th percentile):
                ${entries.map(([name, r]) =>
                    escapeHTML(name) + " " + escapeHTML(r.p5) + "–" + escapeHTML(r.p95) + " " + escapeHTML(r.unit)
                ).join(" · ")}
            </p>
        `;
    }

    function renderChecks(checks) {
        if (!Array.isArray(checks) || !checks.length) return "";

        return checks.map(c => `
            <div class="vi-check">
                ${severityTag(c.status, "chk-")}
                <strong>${escapeHTML(c.check)}</strong>
                <p class="vi-muted">${escapeHTML(c.detail)}</p>
            </div>
        `).join("");
    }

    function renderEvents(events) {
        if (!Array.isArray(events) || !events.length) {
            return "<p>No limit crossings expected at current trends.</p>";
        }

        return `
            <ol class="vi-list">
                ${events.map(e => `
                    <li>
                        ${severityTag(e.level)}
                        ${escapeHTML(e.event)} —
                        <strong>${e.status === "REACHED"
                            ? "already reached"
                            : "in ~" + escapeHTML(e.eta_minutes) + " min"}</strong>
                        ${e.status === "PREDICTED"
                            ? `<span class="vi-muted">(${escapeHTML(e.trend)}, ${escapeHTML(String(e.confidence).toLowerCase())} confidence)</span>`
                            : ""}
                    </li>
                `).join("")}
            </ol>
        `;
    }

    function renderFeatures(data) {
        const d = data || {};

        const combination = d.multi_parameter_fault_detection || {};
        const explanation = d.protection_decision_explanation || {};
        const behaviour = d.behaviour_change_detector || {};
        const learning = d.protection_failure_learning || {};
        const sensors = d.sensor_disagreement_detection || {};
        const sequence = d.fault_sequence_prediction || {};
        const confidence = d.safety_confidence_score || {};
        const strategy = d.personalised_protection_strategy || {};

        return `
            <div class="vi-advanced-grid">

                ${card(
                    "1. Multi-Parameter Fault Combination Detection",
                    `
                        <p><strong>Overall:</strong> ${severityTag(combination.severity)}
                        ${escapeHTML(combination.combination_count ?? 0)} combination(s) detected</p>
                        ${renderCombinations(combination)}
                        ${renderTrends(combination.trends)}
                        <p><strong>Recommendation:</strong> ${escapeHTML(combination.recommendation || "")}</p>
                    `,
                    "Flags failure modes that only appear when several parameters are stressed together."
                )}

                ${card(
                    "2. Battery Protection Decision Explanation",
                    `
                        <div class="vi-main-metric">${value(explanation.decision_label)}</div>
                        <p>${escapeHTML(explanation.summary || "")}</p>
                        <p><strong>Recommended action:</strong> ${escapeHTML(explanation.recommended_action || "Not available")}</p>
                        ${explanation.decision_path && explanation.decision_path.length
                            ? `<p><strong>Why:</strong></p>${list(explanation.decision_path.map(step => step.because))}`
                            : ""}
                        ${explanation.conditions_to_recover && explanation.conditions_to_recover.length
                            ? `<p><strong>To return to normal:</strong></p>${list(explanation.conditions_to_recover)}`
                            : ""}
                        ${renderParameterTable(explanation.parameters)}
                        <p class="vi-muted">${escapeHTML(explanation.note || "")}</p>
                    `,
                    "Shows which rules fired, the main cause, and what has to change to recover."
                )}

                ${card(
                    "3. Battery Behaviour Change Detector",
                    `
                        <p><strong>Status:</strong>
                        ${behaviour.available
                            ? severityTag(behaviour.changed ? "CHANGED" : "STABLE", "beh-")
                            : severityTag("INSUFFICIENT DATA", "beh-")}</p>
                        ${renderBehaviour(behaviour)}
                        <p>${escapeHTML(behaviour.message || "")}</p>
                    `,
                    "Compares the last hour with this battery's own baseline, including internal resistance."
                )}

                ${card(
                    "4. Protection Failure Learning System",
                    `
                        <p><strong>Status:</strong> ${severityTag(learning.learning_status, "learn-")}
                        ${escapeHTML(learning.readings_analysed ?? 0)} readings analysed (7 days)</p>
                        ${learning.conditions && learning.conditions.length
                            ? `<p><strong>Active now:</strong></p>${list(learning.conditions)}`
                            : ""}
                        ${learning.failures && learning.failures.length
                            ? `<p><strong>Protection failures found:</strong></p>${list(learning.failures)}`
                            : ""}
                        ${renderProtections(learning.protections)}
                        ${renderNormalRanges(learning.normal_ranges)}
                        <p>${escapeHTML(learning.message || "")}</p>
                    `,
                    "Learns from past breaches: ones that lasted too long, came back, and what preceded them."
                )}

                ${card(
                    "5. Battery Sensor Disagreement Detection",
                    `
                        <p><strong>Status:</strong>
                        ${severityTag(sensors.disagreement_detected ? "DISAGREE" : "AGREE", "chk-")}
                        ${escapeHTML(sensors.checks_passed ?? 0)} passed,
                        ${escapeHTML(sensors.checks_failed ?? 0)} failed</p>
                        ${renderChecks(sensors.checks)}
                        <p>${escapeHTML(sensors.message || "")}</p>
                    `,
                    "Cross-checks sensors against each other and against physics."
                )}

                ${card(
                    "6. Battery Fault Sequence Prediction",
                    `
                        <p><strong>Method:</strong> trend extrapolation over the next
                        ${escapeHTML(sequence.horizon_hours ?? 6)} h</p>
                        ${renderEvents(sequence.events)}
                        ${sequence.likely_progression && sequence.likely_progression.length
                            ? `<p><strong>Then likely:</strong></p>${list(sequence.likely_progression)}`
                            : ""}
                        <p>${escapeHTML(sequence.message || "")}</p>
                    `,
                    "Which limits will be crossed next, in what order, and roughly when."
                )}

                ${card(
                    "7. Battery Safety Confidence Score",
                    `
                        <div class="vi-metric-grid">
                            <div>Safety score<strong>${value(confidence.safety_score, "/100")}</strong>${severityTag(confidence.safety_status)}</div>
                            <div>Confidence<strong>${value(confidence.confidence_score, "/100")}</strong>${severityTag(confidence.confidence_level, "conf-")}</div>
                        </div>
                        <p><strong>Verdict:</strong> ${value(confidence.verdict)}</p>
                        ${renderFactors(confidence.factors)}
                        ${confidence.limitations && confidence.limitations.length
                            ? `<p><strong>Limitations:</strong></p>${list(confidence.limitations)}`
                            : ""}
                        <p>${escapeHTML(confidence.message || "")}</p>
                    `,
                    "How safe the battery looks, and how much the data behind that verdict can be trusted."
                )}

                ${card(
                    "8. Personalised Battery Protection Strategy",
                    `
                        <p><strong>${escapeHTML(strategy.immediate_count ?? 0)}</strong> immediate action(s)</p>
                        ${Array.isArray(strategy.actions) && strategy.actions.length
                            ? strategy.actions.map(a => `
                                <div class="vi-check">
                                    ${severityTag(a.priority, "pri-")}
                                    ${escapeHTML(a.action)}
                                    <p class="vi-muted">From: ${escapeHTML(a.source)}</p>
                                </div>
                            `).join("")
                            : list(strategy.strategy)}
                        <p class="vi-muted">
                            Generated: ${value(strategy.generated_at)}
                        </p>
                    `,
                    "One prioritised plan built from all seven analyses above."
                )}

            </div>
        `;
    }

    async function refresh() {
        const container = document.getElementById(
            "viBatteryProtectionIntelligence"
        );

        if (!container || loading) return;

        const token = getToken();

        if (!token) {
            container.textContent = "Please log in to view protection intelligence.";
            return;
        }

        loading = true;

        try {
            const batteryId = getBatteryId();

            const response = await fetch(
                API_BASE + "/" + encodeURIComponent(batteryId),
                {
                    method: "GET",
                    cache: "no-store",
                    headers: {
                        Authorization: "Bearer " + token,
                        "Content-Type": "application/json"
                    }
                }
            );

            const result = await response.json();

            if (!response.ok) {
                throw new Error(
                    result.detail || "Unable to load protection intelligence."
                );
            }

            container.innerHTML = renderFeatures(result.data);

        } catch (error) {
            container.innerHTML = `
                <div class="vi-advanced-error">
                    ${escapeHTML(error.message)}
                </div>
                <button type="button" id="viProtectionRetry">
                    Retry
                </button>
            `;

            document.getElementById("viProtectionRetry")
                ?.addEventListener("click", refresh);

        } finally {
            loading = false;
        }
    }

    function attach() {
        const page = document.getElementById("pageContent");

        if (!page) return;

        if (document.getElementById("viBatteryProtectionSection")) {
            return;
        }

        const section = document.createElement("section");

        section.id = "viBatteryProtectionSection";
        section.className = "vi-advanced-section";

        section.innerHTML = `
            <div class="vi-advanced-heading">
                <div>
                    <h2>Battery Protection Intelligence</h2>
                    <p>Eight additional battery protection and safety features</p>
                </div>

                <button type="button" id="viProtectionRefresh">
                    Refresh
                </button>
            </div>

            <div id="viBatteryProtectionIntelligence">
                Loading battery protection intelligence...
            </div>
        `;

        page.appendChild(section);

        document.getElementById("viProtectionRefresh")
            ?.addEventListener("click", refresh);

        refresh();
    }

    function installIntegration() {
        if (typeof window.renderPage !== "function") {
            return false;
        }

        if (window.renderPage.__viProtectionWrapped) {
            return true;
        }

        const original = window.renderPage;

        function wrapped(which) {
            const result = original.apply(this, arguments);

            if (String(which || "").toLowerCase() === "battery") {
                setTimeout(attach, 50);
            }

            return result;
        }

        wrapped.__viProtectionWrapped = true;
        window.renderPage = wrapped;

        return true;
    }

    window.VoltIQProtection = {
        attach,
        refresh
    };

    function initialise() {
        installIntegration();

        if (document.getElementById("pageContent")) {
            const crumb = document.getElementById("crumb");

            if (
                crumb &&
                crumb.textContent.toLowerCase().includes("battery")
            ) {
                attach();
            }
        }

        if (refreshTimer) {
            clearInterval(refreshTimer);
        }

        refreshTimer = setInterval(() => {
            if (document.getElementById("viBatteryProtectionSection")) {
                refresh();
            }
        }, REFRESH_INTERVAL);
    }

    document.addEventListener("DOMContentLoaded", initialise);
    window.addEventListener("load", initialise);

    let attempts = 0;

    const integrationTimer = setInterval(() => {
        attempts++;

        if (installIntegration() || attempts >= 20) {
            clearInterval(integrationTimer);
        }
    }, 250);

})();