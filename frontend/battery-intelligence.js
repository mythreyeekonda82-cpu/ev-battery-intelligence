/* VoltIQ Battery Intelligence modules.
   Fault simulator is software-only.
*/

const VOLTIQ_LAB = {
    events: [],
    active: null,
    signatures: {},
    frozen: {},
    protection: null,
    simulation: null
};

const labNum = (v, d = null) =>
    v !== null &&
    v !== undefined &&
    v !== '' &&
    Number.isFinite(Number(v))
        ? Number(v)
        : d;


/* 1. BATTERY RISK INDEX */

function calculateBatteryRisk(b) {

    const v = labNum(b.voltage);
    const c = labNum(b.current);
    const t = labNum(b.temperature);

    if (v === null || c === null || t === null) {
        return {
            score: null,
            level: "DATA INCOMPLETE",
            detail: "Voltage, current and temperature are required."
        };
    }

    // batteryLimits() in app.js picks 400 V pack or 12 V limits.
    const lim = typeof batteryLimits === "function"
        ? batteryLimits(v)
        : {
            vWarnLow: 11.8, vWarnHigh: 14.7,
            vLowSlope: 35, vHighSlope: 45,
            iNominal: 2.1, iMax: 5.67
        };

    const vr = v < lim.vWarnLow
        ? Math.min(100, (lim.vWarnLow - v) * lim.vLowSlope + 35)
        : v > lim.vWarnHigh
            ? Math.min(100, (v - lim.vWarnHigh) * lim.vHighSlope + 35)
            : 0;

    const cr = Math.max(
        0,
        Math.min(
            100,
            (Math.abs(c) - lim.iNominal) / (lim.iMax - lim.iNominal) * 100
        )
    );

    const tr = t <= 35
        ? 0
        : Math.min(100, (t - 35) * 6);

    const score = Math.round(
        vr * 0.4 +
        cr * 0.25 +
        tr * 0.35
    );

    return {
        score,
        level:
            score >= 65 ? "HIGH" :
            score >= 30 ? "MODERATE" :
            "LOW",

        detail:
            `Voltage ${Math.round(vr)} · Current ${Math.round(cr)} · Temperature ${Math.round(tr)}`
    };
}


/* 2. SENSOR RELIABILITY MONITORING */

function sensorCheck(b) {

    const missing = [
        "voltage",
        "current",
        "temperature"
    ].filter(k => labNum(b[k]) === null);

    const abnormal =
        (labNum(b.voltage) !== null &&
            (b.voltage < 7 || b.voltage > 17)) ||

        (labNum(b.current) !== null &&
            Math.abs(b.current) > 10) ||

        (labNum(b.temperature) !== null &&
            (b.temperature < -10 || b.temperature > 80));

    return {

        status:
            missing.length || abnormal
                ? "CHECK"
                : "OK",

        reason:
            missing.length
                ? `Missing: ${missing.join(", ")}`

                : abnormal
                    ? "Reading outside plausibility limits"

                    : "Readings present and plausible"
    };
}


/* 3. BATTERY STRESS ANALYSIS
   4. RECOVERY TIME TRACKING
*/

function updateStress(b) {

    const reasons = [];

    if (labNum(b.temperature, 25) >= 40)
        reasons.push("High temperature");

    if (Math.abs(labNum(b.current, 0)) >= 2.1)
        reasons.push("High current");

    if (labNum(b.voltage, 12.7) <= 11.8)
        reasons.push("Voltage drop");

    if (reasons.length && !VOLTIQ_LAB.active) {

        VOLTIQ_LAB.active = {
            started: Date.now(),
            reasons
        };

        VOLTIQ_LAB.events.unshift(
            VOLTIQ_LAB.active
        );
    }

    if (!reasons.length && VOLTIQ_LAB.active) {

        VOLTIQ_LAB.active.recovery =
            Math.round(
                (Date.now() - VOLTIQ_LAB.active.started) / 1000
            );

        VOLTIQ_LAB.active = null;
    }
}


/* 5. PROTECTION RESPONSE VERIFICATION
   6. BATTERY FAULT SIMULATOR
*/

function runLabFault(type) {

    const f = {

        overvoltage: [
            "Overvoltage",
            17.2,
            0.8,
            28,
            "Simulated charge-stop response"
        ],

        undervoltage: [
            "Undervoltage",
            10.8,
            0.6,
            27,
            "Simulated low-voltage warning"
        ],

        overcurrent: [
            "Overcurrent",
            12.1,
            4,
            30,
            "Simulated current-limit response"
        ],

        overheating: [
            "Overheating",
            12.3,
            0.7,
            48,
            "Simulated thermal warning"
        ]

    }[type];

    if (!f) return;

    VOLTIQ_LAB.simulation =
        `${f[0]} detected: ${f[1]}V, ${f[2]}A, ${f[3]}°C. ${f[4]}.`;

    VOLTIQ_LAB.protection = {

        before: `${f[1]}V / ${f[2]}A / ${f[3]}°C`,

        after: "Illustrative safe-state values",

        note: "Software simulation only"

    };

    renderPage("battery");
}