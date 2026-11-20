"""
Battery protection intelligence.

Connected analyses built on the live battery snapshot and stored
telemetry:

1. Multi-parameter fault combination detection
2. Battery protection decision explanation
3. Battery safety confidence score
4. Battery behaviour change detection
5. Protection failure learning system
6. Battery sensor disagreement detection
7. Battery fault sequence prediction
8. Personalised battery protection strategy

All thresholds are initial software values. Calibrate them to the
battery manufacturer's limits before relying on them.
"""

from datetime import datetime, timedelta


# ---------------------------------------------------------
# THRESHOLDS
# ---------------------------------------------------------

TEMP_WARNING = 40.0
TEMP_CRITICAL = 45.0

CURRENT_WARNING = 130.0
CURRENT_CRITICAL = 145.0

VOLTAGE_LOW_WARNING = 350.0
VOLTAGE_LOW_CRITICAL = 330.0

VOLTAGE_HIGH_WARNING = 430.0
VOLTAGE_HIGH_CRITICAL = 450.0

SOC_LOW_WARNING = 20.0
SOC_LOW_CRITICAL = 10.0

SOH_WARNING = 85.0
SOH_CRITICAL = 70.0

CELL_DELTA_WARNING = 25.0
CELL_DELTA_CRITICAL = 40.0

# Trend limits (per hour) used for combination rules.
TEMP_RISE_RATE_WARNING = 2.0
VOLTAGE_DROP_RATE_WARNING = 5.0
CURRENT_RISE_RATE_WARNING = 10.0

# Physical plausibility ranges for sensor readings.
PLAUSIBLE_RANGES = {
    "voltage": (200.0, 500.0),
    "current": (-500.0, 500.0),
    "temperature": (-40.0, 90.0),
    "soc": (0.0, 100.0),
    "soh": (0.0, 100.0),
}

REQUIRED_FIELDS = ("voltage", "current", "temperature", "soc", "soh")

SEVERITY_RANK = {
    "NORMAL": 0,
    "WARNING": 1,
    "HIGH": 2,
    "CRITICAL": 3,
}


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _number(value):

    try:
        return float(value)

    except (TypeError, ValueError):
        return None


def _max_severity(levels):

    levels = list(levels) or ["NORMAL"]

    return max(levels, key=lambda level: SEVERITY_RANK[level])


def _parse_time(value):

    if isinstance(value, datetime):
        return value.replace(tzinfo=None)

    if not value:
        return None

    try:
        return (
            datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            .replace(tzinfo=None)
        )

    except ValueError:
        return None


def _slope_per_hour(history, field, window_hours=2):
    """Least-squares slope of a telemetry field over the recent window."""

    fit = _fit_trend(history, field, window_hours)

    return fit["slope"] if fit else None


def _fit_trend(history, field, window_hours=2):
    """
    Least-squares fit of a telemetry field over the recent window.

    Returns slope (units per hour), r_squared and point count, or None
    when there are fewer than 3 usable points.
    """

    if not history:
        return None

    cutoff = history[-1].timestamp - timedelta(hours=window_hours)

    points = [
        (row.timestamp, _number(getattr(row, field, None)))
        for row in history
        if row.timestamp and row.timestamp >= cutoff
    ]

    points = [(t, v) for t, v in points if v is not None]

    if len(points) < 3:
        return None

    origin = points[0][0]

    xs = [(t - origin).total_seconds() / 3600.0 for t, _ in points]
    ys = [v for _, v in points]

    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)

    denominator = sum((x - mean_x) ** 2 for x in xs)

    if denominator == 0:
        return None

    numerator = sum(
        (x - mean_x) * (y - mean_y)
        for x, y in zip(xs, ys)
    )

    slope = numerator / denominator
    intercept = mean_y - slope * mean_x

    total = sum((y - mean_y) ** 2 for y in ys)
    residual = sum(
        (y - (intercept + slope * x)) ** 2
        for x, y in zip(xs, ys)
    )

    r_squared = 1.0 - residual / total if total > 0 else 0.0

    return {
        "slope": slope,
        "r_squared": max(0.0, r_squared),
        "points": len(points),
    }


def _readings(battery):

    return {
        "voltage": _number(battery.get("voltage")),
        "current": _number(battery.get("current")),
        "temperature": _number(battery.get("temperature")),
        "soc": _number(battery.get("soc")),
        "soh": _number(battery.get("soh")),
        "cell_delta_mv": _number(battery.get("cell_delta_mv")),
    }


def _trends(history):

    return {
        "temperature_per_hour": _slope_per_hour(history, "temperature"),
        "voltage_per_hour": _slope_per_hour(history, "voltage"),
        "current_per_hour": _slope_per_hour(history, "current"),
    }


# ---------------------------------------------------------
# PARAMETER ASSESSMENT
# Shared by all three features.
# ---------------------------------------------------------

def assess_parameters(battery):
    """
    Grade each parameter against its thresholds.

    Returns one entry per parameter with its value, limits, state,
    the margin to the next limit and a plain-language reason.
    """

    r = _readings(battery)

    current_abs = abs(r["current"]) if r["current"] is not None else None

    specs = [
        # name, label, unit, value, warning, critical, direction
        ("temperature", "Temperature", "°C",
         r["temperature"], TEMP_WARNING, TEMP_CRITICAL, "high"),

        ("current", "Current", "A",
         current_abs, CURRENT_WARNING, CURRENT_CRITICAL, "high"),

        ("voltage_low", "Voltage (low)", "V",
         r["voltage"], VOLTAGE_LOW_WARNING, VOLTAGE_LOW_CRITICAL, "low"),

        ("voltage_high", "Voltage (high)", "V",
         r["voltage"], VOLTAGE_HIGH_WARNING, VOLTAGE_HIGH_CRITICAL, "high"),

        ("soc", "State of charge", "%",
         r["soc"], SOC_LOW_WARNING, SOC_LOW_CRITICAL, "low"),

        ("soh", "State of health", "%",
         r["soh"], SOH_WARNING, SOH_CRITICAL, "low"),

        ("cell_delta", "Cell voltage spread", "mV",
         r["cell_delta_mv"], CELL_DELTA_WARNING, CELL_DELTA_CRITICAL, "high"),
    ]

    # Risk points each parameter adds when it is out of range.
    weights = {
        "temperature": 30,
        "current": 20,
        "voltage_low": 20,
        "voltage_high": 25,
        "soc": 10,
        "soh": 15,
        "cell_delta": 15,
    }

    assessed = []

    for name, label, unit, value, warning, critical, direction in specs:

        if value is None:
            assessed.append({
                "parameter": name,
                "label": label,
                "unit": unit,
                "value": None,
                "state": "UNKNOWN",
                "warning_threshold": warning,
                "critical_threshold": critical,
                "margin_to_warning": None,
                "risk_points": 0,
                "reason": f"{label} reading is not available.",
            })
            continue

        if direction == "high":
            margin = warning - value
            is_critical = value >= critical
            is_warning = value >= warning
            word = "above"
        else:
            margin = value - warning
            is_critical = value <= critical
            is_warning = value <= warning
            word = "below"

        if is_critical:
            state = "CRITICAL"
            points = weights[name]
            reason = (
                f"{label} is {value:.1f} {unit}, {word} the critical "
                f"limit of {critical:.1f} {unit}."
            )
        elif is_warning:
            state = "WARNING"
            points = round(weights[name] / 2)
            reason = (
                f"{label} is {value:.1f} {unit}, {word} the warning "
                f"limit of {warning:.1f} {unit}."
            )
        else:
            state = "NORMAL"
            points = 0
            reason = (
                f"{label} is {value:.1f} {unit}, within limits "
                f"({abs(margin):.1f} {unit} from the warning limit)."
            )

        assessed.append({
            "parameter": name,
            "label": label,
            "unit": unit,
            "value": round(value, 2),
            "state": state,
            "warning_threshold": warning,
            "critical_threshold": critical,
            "margin_to_warning": round(margin, 2),
            "risk_points": points,
            "reason": reason,
        })

    return assessed


def _state_map(assessed):

    return {item["parameter"]: item["state"] for item in assessed}


def _at_least(state, level):

    return SEVERITY_RANK.get(state, -1) >= SEVERITY_RANK[level]


# ---------------------------------------------------------
# FEATURE 1
# MULTI-PARAMETER FAULT COMBINATION DETECTION
# ---------------------------------------------------------

def detect_fault_combinations(battery, history):
    """
    Look for dangerous combinations of parameters.

    A single reading near a limit is often harmless. The same reading
    paired with another stressed parameter, or with a worsening trend,
    points to a specific failure mode. Each rule names that mode.
    """

    r = _readings(battery)
    assessed = assess_parameters(battery)
    states = _state_map(assessed)
    trends = _trends(history)

    temp_rate = trends["temperature_per_hour"]
    volt_rate = trends["voltage_per_hour"]
    curr_rate = trends["current_per_hour"]

    temp_rising = temp_rate is not None and temp_rate >= TEMP_RISE_RATE_WARNING
    volt_falling = volt_rate is not None and volt_rate <= -VOLTAGE_DROP_RATE_WARNING
    curr_rising = curr_rate is not None and curr_rate >= CURRENT_RISE_RATE_WARNING

    def is_(name, level="WARNING"):
        return _at_least(states.get(name), level)

    def fmt(value, unit):
        return "n/a" if value is None else f"{value:.1f} {unit}"

    combinations = []

    def add(code, name, severity, involved, explanation, recommendation):
        combinations.append({
            "code": code,
            "name": name,
            "severity": severity,
            "parameters": involved,
            "explanation": explanation,
            "recommendation": recommendation,
        })

    # Thermal runaway precursor: hot, heating up, and voltage sagging
    # or cells drifting apart.
    if is_("temperature") and temp_rising and (volt_falling or is_("cell_delta")):
        add(
            "THERMAL_RUNAWAY_PRECURSOR",
            "Thermal runaway precursor",
            "CRITICAL",
            {
                "temperature": fmt(r["temperature"], "°C"),
                "temperature_trend": f"+{temp_rate:.1f} °C/h",
                "voltage_trend": fmt(volt_rate, "V/h"),
                "cell_delta": fmt(r["cell_delta_mv"], "mV"),
            },
            "Temperature is high and still rising while voltage falls or "
            "cells diverge. This pattern can precede thermal runaway.",
            "Stop the vehicle safely, remove all load and charging, and "
            "keep people away from the pack until it is inspected.",
        )

    if is_("temperature") and is_("current"):
        add(
            "HIGH_TEMP_HIGH_CURRENT",
            "High temperature under high current",
            "CRITICAL" if (is_("temperature", "CRITICAL")
                           or is_("current", "CRITICAL")) else "HIGH",
            {
                "temperature": fmt(r["temperature"], "°C"),
                "current": fmt(abs(r["current"]), "A"),
            },
            "Heavy current is adding heat to a pack that is already hot, "
            "so temperature is likely to keep climbing.",
            "Reduce power demand immediately and allow the pack to cool.",
        )

    if is_("temperature") and is_("voltage_low"):
        add(
            "HOT_UNDERVOLTAGE",
            "High temperature with low voltage",
            "CRITICAL" if is_("voltage_low", "CRITICAL") else "HIGH",
            {
                "temperature": fmt(r["temperature"], "°C"),
                "voltage": fmt(r["voltage"], "V"),
            },
            "Low voltage on a hot pack can indicate an internal short or "
            "a failing cell group rather than normal discharge.",
            "Stop discharging and arrange an internal resistance and "
            "cell-level inspection.",
        )

    if is_("voltage_high") and is_("temperature"):
        add(
            "OVERCHARGE_HEATING",
            "Overcharge with heating",
            "CRITICAL",
            {
                "voltage": fmt(r["voltage"], "V"),
                "temperature": fmt(r["temperature"], "°C"),
            },
            "Voltage is above the charge limit and the pack is heating. "
            "Overcharging damages cells and raises fire risk.",
            "Stop charging now and inspect the charger and BMS charge "
            "termination.",
        )

    if is_("soc") and is_("current") and is_("voltage_low"):
        add(
            "DEEP_DISCHARGE_UNDER_LOAD",
            "Deep discharge under heavy load",
            "HIGH",
            {
                "soc": fmt(r["soc"], "%"),
                "current": fmt(abs(r["current"]), "A"),
                "voltage": fmt(r["voltage"], "V"),
            },
            "The pack is nearly empty and still delivering high current, "
            "which pulls voltage down and stresses the weakest cells.",
            "Reduce load and recharge as soon as possible.",
        )

    if is_("cell_delta") and (is_("current") or is_("temperature")):
        add(
            "IMBALANCE_UNDER_STRESS",
            "Cell imbalance under stress",
            "CRITICAL" if is_("cell_delta", "CRITICAL") else "HIGH",
            {
                "cell_delta": fmt(r["cell_delta_mv"], "mV"),
                "current": fmt(abs(r["current"]) if r["current"] is not None else None, "A"),
                "temperature": fmt(r["temperature"], "°C"),
            },
            "Cells are already out of balance, and high current or heat "
            "pushes the weakest cells past their limits first.",
            "Limit power and run a balancing charge before heavy use.",
        )

    if is_("soh") and (is_("temperature") or is_("current")):
        add(
            "AGED_PACK_UNDER_STRESS",
            "Degraded pack under stress",
            "HIGH" if is_("soh", "CRITICAL") else "WARNING",
            {
                "soh": fmt(r["soh"], "%"),
                "temperature": fmt(r["temperature"], "°C"),
                "current": fmt(abs(r["current"]) if r["current"] is not None else None, "A"),
            },
            "A degraded pack has higher internal resistance, so the same "
            "load produces more heat and voltage sag than in a new pack.",
            "Derate power for this pack and schedule a health inspection.",
        )

    if temp_rising and curr_rising and volt_falling:
        add(
            "DIVERGING_TREND",
            "Temperature and current rising while voltage falls",
            "WARNING",
            {
                "temperature_trend": f"+{temp_rate:.1f} °C/h",
                "current_trend": f"+{curr_rate:.1f} A/h",
                "voltage_trend": f"{volt_rate:.1f} V/h",
            },
            "All three trends are moving in the unsafe direction "
            "together, even if no single value has crossed a limit yet.",
            "Watch closely and reduce load if the trend continues.",
        )

    severity = _max_severity(c["severity"] for c in combinations)

    # Several simultaneous combinations escalate a warning.
    if len(combinations) >= 2 and severity == "WARNING":
        severity = "HIGH"

    if combinations:
        worst = max(combinations, key=lambda c: SEVERITY_RANK[c["severity"]])
        recommendation = worst["recommendation"]
    else:
        recommendation = "No combined fault pattern detected."

    return {
        "detected": bool(combinations),
        "severity": severity,
        "combination_count": len(combinations),
        "combinations": combinations,
        "patterns": [c["name"] for c in combinations],
        "parameter_states": {
            item["parameter"]: item["state"] for item in assessed
        },
        "trends": {
            key: (round(value, 2) if value is not None else None)
            for key, value in trends.items()
        },
        "trend_window_hours": 2,
        "recommendation": recommendation,
    }


# ---------------------------------------------------------
# FEATURE 2
# BATTERY PROTECTION DECISION EXPLANATION
# ---------------------------------------------------------

DECISIONS = {
    "NORMAL_OPERATION": {
        "label": "Normal operation",
        "action": "Continue normal operation and monitoring.",
    },
    "MONITOR": {
        "label": "Monitor closely",
        "action": "Keep operating but watch the flagged parameters.",
    },
    "LIMIT_POWER": {
        "label": "Limit power",
        "action": "Reduce charge and discharge power until readings recover.",
    },
    "STOP_CHARGING": {
        "label": "Stop charging",
        "action": "Stop charging and inspect the charger and BMS.",
    },
    "ISOLATE_BATTERY": {
        "label": "Isolate battery",
        "action": (
            "Bring the vehicle to a safe stop, disconnect load and charging, "
            "and arrange an immediate inspection."
        ),
    },
}


def explain_protection_decision(battery, history, combinations=None):
    """
    Decide the recommended protection action and explain why.

    The explanation lists every rule that fired, the parameter that
    drove the decision, and what would need to change for the battery
    to return to normal operation.
    """

    assessed = assess_parameters(battery)
    states = _state_map(assessed)

    if combinations is None:
        combinations = detect_fault_combinations(battery, history)

    decision_path = []
    decision = "NORMAL_OPERATION"

    def escalate(to, why):
        nonlocal decision
        order = list(DECISIONS)
        if order.index(to) > order.index(decision):
            decision = to
        decision_path.append({"decision": to, "because": why})

    critical = [a for a in assessed if a["state"] == "CRITICAL"]
    warnings = [a for a in assessed if a["state"] == "WARNING"]

    for item in critical:
        if item["parameter"] in ("temperature", "voltage_high", "voltage_low"):
            escalate("ISOLATE_BATTERY", item["reason"])
        elif item["parameter"] in ("current", "cell_delta"):
            escalate("LIMIT_POWER", item["reason"])
        else:
            escalate("MONITOR", item["reason"])

    for item in warnings:
        if item["parameter"] == "voltage_high":
            escalate("STOP_CHARGING", item["reason"])
        elif item["parameter"] in ("temperature", "current", "voltage_low", "cell_delta"):
            escalate("LIMIT_POWER", item["reason"])
        else:
            escalate("MONITOR", item["reason"])

    for combo in combinations.get("combinations", []):
        why = f"Fault combination detected: {combo['name']}."
        if combo["severity"] == "CRITICAL":
            escalate("ISOLATE_BATTERY", why)
        elif combo["severity"] == "HIGH":
            escalate("LIMIT_POWER", why)
        else:
            escalate("MONITOR", why)

    contributors = sorted(
        (a for a in assessed if a["risk_points"] > 0),
        key=lambda a: a["risk_points"],
        reverse=True,
    )

    primary = contributors[0] if contributors else None

    # What would need to change for each flagged parameter to recover.
    to_recover = []

    for item in contributors:
        direction = "below" if item["parameter"] in (
            "temperature", "current", "voltage_high", "cell_delta"
        ) else "above"

        to_recover.append(
            f"{item['label']} must be {direction} "
            f"{item['warning_threshold']:.1f} {item['unit']} "
            f"(currently {item['value']:.1f} {item['unit']})."
        )

    if combinations.get("detected"):
        to_recover.append(
            "The fault combinations listed above must clear."
        )

    if decision == "NORMAL_OPERATION":
        summary = "All monitored parameters are within limits."
    else:
        cause = (
            primary["label"].lower() if primary
            else "a combination of parameters"
        )
        summary = (
            f"{DECISIONS[decision]['label']} recommended, driven mainly "
            f"by {cause}."
        )

    return {
        "decision": decision,
        "decision_label": DECISIONS[decision]["label"],
        "summary": summary,
        "warning_generated": decision != "NORMAL_OPERATION",
        "primary_cause": primary["label"] if primary else None,
        "decision_path": decision_path,
        "parameters": assessed,
        "contributing_parameters": [a["reason"] for a in contributors],
        "fault_combinations": [
            c["name"] for c in combinations.get("combinations", [])
        ],
        "conditions_to_recover": to_recover,
        "recommended_action": DECISIONS[decision]["action"],
        "note": (
            "This is a recommendation from monitoring software. The "
            "battery's own BMS remains responsible for hard protection."
        ),
    }


# ---------------------------------------------------------
# FEATURE 3
# BATTERY SAFETY CONFIDENCE SCORE
# ---------------------------------------------------------

def calculate_safety_confidence(battery, history, now=None):
    """
    Score how safe the battery is and how far that verdict can be
    trusted.

    safety_score      0-100, higher is safer. Based on parameter risk
                      and fault combinations.
    confidence_score  0-100, how reliable the safety score is. Based on
                      data completeness, freshness, sensor plausibility,
                      history depth and reading stability.
    """

    now = now or datetime.utcnow()

    assessed = assess_parameters(battery)
    combinations = detect_fault_combinations(battery, history)

    # ----- Safety score -----

    risk = sum(a["risk_points"] for a in assessed)

    combo_penalty = {"CRITICAL": 25, "HIGH": 15, "WARNING": 5}
    risk += sum(
        combo_penalty.get(c["severity"], 0)
        for c in combinations["combinations"]
    )

    safety_score = max(0, 100 - risk)

    if safety_score >= 80:
        safety_status = "SAFE"
    elif safety_score >= 50:
        safety_status = "CAUTION"
    else:
        safety_status = "UNSAFE"

    # ----- Confidence factors -----

    factors = []
    limitations = []

    # 1. Completeness (25)
    missing = [
        field for field in REQUIRED_FIELDS
        if _number(battery.get(field)) is None
    ]
    completeness = 25 * (len(REQUIRED_FIELDS) - len(missing)) / len(REQUIRED_FIELDS)

    if missing:
        limitations.append(
            "Missing readings: " + ", ".join(missing) + "."
        )

    factors.append({
        "factor": "Data completeness",
        "score": round(completeness, 1),
        "max": 25,
        "detail": (
            f"{len(REQUIRED_FIELDS) - len(missing)} of "
            f"{len(REQUIRED_FIELDS)} required readings present."
        ),
    })

    # 2. Freshness (20): full marks under 30 s, zero at 10 minutes.
    updated_at = _parse_time(battery.get("updated_at"))

    if updated_at is None:
        freshness = 0.0
        age_seconds = None
        freshness_detail = "Reading time is unknown."
        limitations.append("Reading timestamp is missing.")
    else:
        age_seconds = max(0.0, (now - updated_at).total_seconds())
        if age_seconds <= 30:
            freshness = 20.0
        else:
            freshness = max(0.0, 20.0 * (1 - (age_seconds - 30) / 570))
        freshness_detail = f"Latest reading is {age_seconds:.0f} s old."
        if age_seconds > 120:
            limitations.append(
                "Latest reading is more than 2 minutes old."
            )

    factors.append({
        "factor": "Data freshness",
        "score": round(freshness, 1),
        "max": 20,
        "detail": freshness_detail,
    })

    # 3. Sensor plausibility (20)
    implausible = []

    for field, (low, high) in PLAUSIBLE_RANGES.items():
        value = _number(battery.get(field))
        if value is not None and not (low <= value <= high):
            implausible.append(
                f"{field} = {value} is outside {low} to {high}."
            )

    voltage = _number(battery.get("voltage"))
    current = _number(battery.get("current"))
    power = _number(battery.get("power_kw"))

    if None not in (voltage, current, power):
        expected = voltage * current / 1000.0
        if abs(expected - power) > max(1.0, abs(expected) * 0.1):
            implausible.append(
                f"Reported power {power:.1f} kW does not match "
                f"voltage × current ({expected:.1f} kW)."
            )

    plausibility = max(0.0, 20.0 - 7.0 * len(implausible))
    limitations.extend(implausible)

    factors.append({
        "factor": "Sensor plausibility",
        "score": round(plausibility, 1),
        "max": 20,
        "detail": (
            "All readings are physically plausible and consistent."
            if not implausible else
            f"{len(implausible)} implausible or inconsistent reading(s)."
        ),
    })

    # 4. History depth (20): full marks at 12 readings (one hour of
    #    five-minute snapshots).
    count = len(history)
    depth = 20.0 * min(count, 12) / 12

    if count < 3:
        limitations.append(
            "Fewer than 3 stored readings, so trends cannot be checked."
        )

    factors.append({
        "factor": "History depth",
        "score": round(depth, 1),
        "max": 20,
        "detail": f"{count} stored reading(s) in the last 24 hours.",
    })

    # 5. Reading stability (15): sudden jumps between consecutive
    #    readings suggest a noisy or faulty sensor.
    jumps = 0

    for previous, current_row in zip(history, history[1:]):
        if abs((current_row.temperature or 0) - (previous.temperature or 0)) > 5:
            jumps += 1
        if abs((current_row.voltage or 0) - (previous.voltage or 0)) > 25:
            jumps += 1

    if count >= 2:
        stability = max(0.0, 15.0 - 3.0 * jumps)
        stability_detail = (
            "No sudden jumps between readings."
            if jumps == 0 else
            f"{jumps} sudden jump(s) between consecutive readings."
        )
        if jumps:
            limitations.append(
                "Sudden reading jumps suggest sensor noise or a fault."
            )
    else:
        stability = 0.0
        stability_detail = "Not enough readings to check stability."

    factors.append({
        "factor": "Reading stability",
        "score": round(stability, 1),
        "max": 15,
        "detail": stability_detail,
    })

    confidence_score = round(sum(f["score"] for f in factors))
    confidence_score = max(0, min(100, confidence_score))

    if confidence_score >= 80:
        level = "HIGH"
    elif confidence_score >= 50:
        level = "MEDIUM"
    else:
        level = "LOW"

    verdict = f"{safety_status} ({level.lower()} confidence)"

    if level == "LOW":
        message = (
            "The safety verdict is unreliable. Resolve the data "
            "limitations before relying on it."
        )
    elif safety_status == "SAFE":
        message = "The battery appears safe and the data supports this."
    else:
        message = (
            "The battery shows safety concerns and the data is "
            "reliable enough to act on."
        )

    return {
        "safety_score": safety_score,
        "safety_status": safety_status,
        "confidence_score": confidence_score,
        "confidence_level": level,
        "verdict": verdict,
        "factors": factors,
        "limitations": limitations,
        "missing_parameters": missing,
        "historical_readings": count,
        "reading_age_seconds": (
            round(age_seconds) if age_seconds is not None else None
        ),
        "message": message,
    }


# ---------------------------------------------------------
# SHARED STATISTICS
# ---------------------------------------------------------

def _mean(values):

    return sum(values) / len(values) if values else None


def _std(values):

    if len(values) < 2:
        return 0.0

    m = _mean(values)

    return (sum((v - m) ** 2 for v in values) / (len(values) - 1)) ** 0.5


def _percentile(values, pct):

    if not values:
        return None

    ordered = sorted(values)
    index = (len(ordered) - 1) * pct / 100.0
    low = int(index)
    high = min(low + 1, len(ordered) - 1)

    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def _regress(xs, ys):
    """Simple linear regression. Returns (slope, r_squared) or None."""

    if len(xs) < 3 or len(xs) != len(ys):
        return None

    mx, my = _mean(xs), _mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)

    if sxx == 0 or syy == 0:
        return None

    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))

    return sxy / sxx, (sxy * sxy) / (sxx * syy)


def _column(rows, field, absolute=False):

    values = []

    for row in rows:
        value = _number(getattr(row, field, None))
        if value is not None:
            values.append(abs(value) if absolute else value)

    return values


# ---------------------------------------------------------
# FEATURE 4
# BATTERY BEHAVIOUR CHANGE DETECTION
# ---------------------------------------------------------

BEHAVIOUR_METRICS = (
    # field, label, unit, smallest shift worth reporting
    ("temperature", "Temperature", "°C", 2.0),
    ("voltage", "Voltage", "V", 5.0),
    ("current", "Current", "A", 10.0),
    ("power_kw", "Power", "kW", 3.0),
)


def detect_behaviour_change(history, recent_hours=1):
    """
    Compare the last hour of readings with the battery's own baseline
    from earlier in the day.

    A shift is reported when the recent average moves at least two
    baseline standard deviations and by a practically meaningful
    amount. The voltage-versus-current slope is also compared, because
    a rising slope means internal resistance is increasing, which is an
    early sign of degradation.
    """

    if not history:
        return {
            "available": False,
            "changed": False,
            "message": "No stored readings yet.",
        }

    cutoff = history[-1].timestamp - timedelta(hours=recent_hours)

    baseline = [row for row in history if row.timestamp < cutoff]
    recent = [row for row in history if row.timestamp >= cutoff]

    if len(baseline) < 6 or len(recent) < 3:
        return {
            "available": False,
            "changed": False,
            "baseline_readings": len(baseline),
            "recent_readings": len(recent),
            "message": (
                "At least 6 baseline and 3 recent readings are needed "
                f"(have {len(baseline)} and {len(recent)})."
            ),
        }

    metrics = []
    changes = {}

    for field, label, unit, min_shift in BEHAVIOUR_METRICS:

        base_values = _column(baseline, field)
        recent_values = _column(recent, field)

        if len(base_values) < 3 or not recent_values:
            continue

        base_mean = _mean(base_values)
        base_std = _std(base_values)
        recent_mean = _mean(recent_values)
        shift = recent_mean - base_mean

        # Floor the spread so a very steady baseline does not turn
        # tiny noise into a huge z-score.
        z_score = shift / max(base_std, min_shift / 4)

        flagged = abs(z_score) >= 2 and abs(shift) >= min_shift

        changes[f"{field}_change"] = round(shift, 2)

        metrics.append({
            "metric": label,
            "unit": unit,
            "baseline_mean": round(base_mean, 2),
            "baseline_std": round(base_std, 2),
            "recent_mean": round(recent_mean, 2),
            "shift": round(shift, 2),
            "z_score": round(z_score, 2),
            "changed": flagged,
            "detail": (
                f"{label} averaged {recent_mean:.1f} {unit} in the last "
                f"{recent_hours} h against a baseline of "
                f"{base_mean:.1f} {unit} ({shift:+.1f} {unit})."
            ),
        })

    # Internal resistance proxy: how far voltage sags per amp.
    resistance = None

    def current_voltage_pairs(rows):
        pairs = [
            (_number(r.current), _number(r.voltage))
            for r in rows
        ]
        pairs = [(i, v) for i, v in pairs if i is not None and v is not None]
        return [i for i, _ in pairs], [v for _, v in pairs]

    base_fit = _regress(*current_voltage_pairs(baseline))
    recent_fit = _regress(*current_voltage_pairs(recent))

    if base_fit and recent_fit and base_fit[1] >= 0.3 and recent_fit[1] >= 0.3:

        base_r = -base_fit[0] * 1000
        recent_r = -recent_fit[0] * 1000

        increased = base_r > 0 and recent_r > base_r * 1.25

        resistance = {
            "baseline_mohm": round(base_r, 1),
            "recent_mohm": round(recent_r, 1),
            "changed": increased,
            "detail": (
                "Voltage sag per amp has risen by more than 25%, which "
                "suggests rising internal resistance."
                if increased else
                "Voltage sag per amp is consistent with the baseline."
            ),
        }

    flagged_metrics = [m for m in metrics if m["changed"]]
    changed = bool(flagged_metrics) or bool(resistance and resistance["changed"])

    if changed:
        names = [m["metric"].lower() for m in flagged_metrics]
        if resistance and resistance["changed"]:
            names.append("internal resistance")
        message = (
            "Battery behaviour has changed: " + ", ".join(names) + "."
        )
    else:
        message = "Battery behaviour matches its own baseline."

    return {
        "available": True,
        "changed": changed,
        "baseline_readings": len(baseline),
        "recent_readings": len(recent),
        "recent_window_hours": recent_hours,
        "metrics": metrics,
        "internal_resistance": resistance,
        "changes": changes,
        "message": message,
    }


# ---------------------------------------------------------
# FEATURE 5
# PROTECTION FAILURE LEARNING SYSTEM
# ---------------------------------------------------------

PROTECTION_CHECKS = (
    # code, label, field, direction, critical limit, warning limit, live parameter
    ("OVER_TEMPERATURE", "Over-temperature", "temperature", "high",
     TEMP_CRITICAL, TEMP_WARNING, "temperature"),
    ("OVER_CURRENT", "Over-current", "current", "high",
     CURRENT_CRITICAL, CURRENT_WARNING, "current"),
    ("UNDER_VOLTAGE", "Under-voltage", "voltage", "low",
     VOLTAGE_LOW_CRITICAL, VOLTAGE_LOW_WARNING, "voltage_low"),
    ("OVER_VOLTAGE", "Over-voltage", "voltage", "high",
     VOLTAGE_HIGH_CRITICAL, VOLTAGE_HIGH_WARNING, "voltage_high"),
)

# A breach is a protection failure when it lasts this long, or
# returns this soon after clearing.
SUSTAINED_BREACH_MINUTES = 15
RECURRENCE_WINDOW_MINUTES = 60
PRECURSOR_WINDOW_MINUTES = 30
EPISODE_GAP_MINUTES = 15


def _breached(value, direction, limit):

    if value is None:
        return False

    return value >= limit if direction == "high" else value <= limit


def _field_value(row, field):

    value = _number(getattr(row, field, None))

    if field == "current" and value is not None:
        value = abs(value)

    return value


def _episodes(history, field, direction, limit):
    """Group consecutive breaching readings into episodes."""

    episodes = []
    current = None

    for row in history:

        value = _field_value(row, field)

        if not _breached(value, direction, limit):
            current = None
            continue

        if current and (
            (row.timestamp - current["end"]).total_seconds() / 60
            <= EPISODE_GAP_MINUTES
        ):
            current["end"] = row.timestamp
            current["readings"] += 1
            current["peak"] = (
                max(current["peak"], value) if direction == "high"
                else min(current["peak"], value)
            )
        else:
            current = {
                "start": row.timestamp,
                "end": row.timestamp,
                "readings": 1,
                "peak": value,
            }
            episodes.append(current)

    return episodes


def learn_protection_failures(battery, history):
    """
    Learn from this battery's own breach history.

    For each protection limit it finds past breach episodes and treats
    two outcomes as protection failures: a breach that lasted too long
    (protection did not bring the value back) and a breach that came
    back soon after clearing (the root cause was not fixed). It also
    learns the values seen shortly before each breach, giving a
    battery-specific early-warning level, and the normal operating
    range of the battery.
    """

    assessed = {a["parameter"]: a for a in assess_parameters(battery)}

    conditions = [
        f"{label} protection condition active now."
        for _, label, _, _, _, _, live in PROTECTION_CHECKS
        if assessed[live]["state"] == "CRITICAL"
    ]

    if len(history) < 12:
        return {
            "protection_condition_detected": bool(conditions),
            "conditions": conditions,
            "failures": [],
            "learning_status": "INSUFFICIENT_DATA",
            "readings_analysed": len(history),
            "protections": [],
            "normal_ranges": {},
            "message": (
                "At least 12 stored readings are needed before the "
                f"system can learn (have {len(history)})."
            ),
        }

    protections = []
    failures = []

    for code, label, field, direction, critical, warning, _ in PROTECTION_CHECKS:

        episodes = _episodes(history, field, direction, critical)

        sustained = 0
        recurred = 0
        precursors = []

        for index, episode in enumerate(episodes):

            duration = (episode["end"] - episode["start"]).total_seconds() / 60

            if duration >= SUSTAINED_BREACH_MINUTES:
                sustained += 1

            if index > 0:
                since_last = (
                    episode["start"] - episodes[index - 1]["end"]
                ).total_seconds() / 60
                if since_last <= RECURRENCE_WINDOW_MINUTES:
                    recurred += 1

            # The last reading before the breach, if it is recent
            # enough to count as the run-up.
            window_start = episode["start"] - timedelta(minutes=PRECURSOR_WINDOW_MINUTES)

            before = [
                row for row in history
                if window_start <= row.timestamp < episode["start"]
            ]

            if before:
                value = _field_value(before[-1], field)
                if value is not None:
                    precursors.append(value)

        learned_warning = None

        if precursors:
            # The least extreme pre-breach reading: the earliest point
            # at which this battery has been seen heading into a breach.
            learned_warning = (
                min(precursors) if direction == "high" else max(precursors)
            )

        earlier_than_fixed = (
            learned_warning is not None
            and (
                learned_warning < warning if direction == "high"
                else learned_warning > warning
            )
        )

        if sustained:
            failures.append(
                f"{label}: {sustained} breach(es) lasted "
                f"{SUSTAINED_BREACH_MINUTES}+ minutes before clearing."
            )

        if recurred:
            failures.append(
                f"{label}: returned {recurred} time(s) within "
                f"{RECURRENCE_WINDOW_MINUTES} minutes of clearing."
            )

        worst = None

        if episodes:
            peaks = [e["peak"] for e in episodes]
            worst = round(max(peaks) if direction == "high" else min(peaks), 2)

        protections.append({
            "code": code,
            "label": label,
            "critical_limit": critical,
            "episodes": len(episodes),
            "sustained_breaches": sustained,
            "quick_recurrences": recurred,
            "worst_value": worst,
            "fixed_warning_limit": warning,
            "learned_early_warning": (
                round(learned_warning, 2) if learned_warning is not None else None
            ),
            "suggest_earlier_warning": earlier_than_fixed,
        })

    normal_ranges = {}

    for field, unit in (("temperature", "°C"), ("voltage", "V"), ("current", "A")):
        values = _column(history, field, absolute=(field == "current"))
        if values:
            normal_ranges[field] = {
                "p5": round(_percentile(values, 5), 2),
                "p95": round(_percentile(values, 95), 2),
                "unit": unit,
            }

    any_episodes = any(p["episodes"] for p in protections)
    learning_status = "LEARNED" if any_episodes else "LEARNING"

    if failures:
        message = (
            "Protection did not fully contain past breaches. Investigate "
            "the root cause rather than relying on the cutoff."
        )
    elif any_episodes:
        message = "Past breaches were contained quickly and did not recur."
    else:
        message = (
            "No protection breaches in the analysed history. Normal "
            "operating ranges have been learned."
        )

    return {
        "protection_condition_detected": bool(conditions or failures),
        "conditions": conditions,
        "failures": failures,
        "learning_status": learning_status,
        "readings_analysed": len(history),
        "protections": protections,
        "normal_ranges": normal_ranges,
        "message": message,
    }


# ---------------------------------------------------------
# FEATURE 6
# BATTERY SENSOR DISAGREEMENT DETECTION
# ---------------------------------------------------------

def detect_sensor_disagreement(battery, history, now=None):
    """
    Cross-check sensors against each other and against physics.

    Each check compares signals that should agree: reported power with
    voltage times current, pack voltage with the cell voltages, the
    live reading with the latest stored one, and temperature changes
    with the current that would cause them. It also looks for stuck
    sensors and changes too fast to be physical.
    """

    now = now or datetime.utcnow()

    checks = []
    suspects = set()

    def add(name, status, detail, sensors=()):
        checks.append({"check": name, "status": status, "detail": detail})
        if status == "DISAGREE":
            suspects.update(sensors)

    voltage = _number(battery.get("voltage"))
    current = _number(battery.get("current"))
    temperature = _number(battery.get("temperature"))
    power = _number(battery.get("power_kw"))

    # 1. Power against voltage x current.
    name = "Power vs voltage × current"

    if None not in (voltage, current, power):
        expected = voltage * current / 1000.0
        if abs(expected - power) > max(1.0, abs(expected) * 0.1):
            add(name, "DISAGREE",
                f"Reported {power:.1f} kW, expected {expected:.1f} kW.",
                ("voltage", "current"))
        else:
            add(name, "AGREE",
                f"Reported {power:.1f} kW matches {expected:.1f} kW.")
    else:
        add(name, "UNAVAILABLE", "Power, voltage or current is missing.")

    # 2. Pack voltage against cell voltages.
    name = "Pack voltage vs cell voltages"
    min_cell = _number(battery.get("min_cell_voltage"))
    max_cell = _number(battery.get("max_cell_voltage"))
    cell_count = _number(battery.get("cell_count"))

    if None not in (voltage, min_cell, max_cell, cell_count) and cell_count > 0:
        low = min_cell * cell_count * 0.98
        high = max_cell * cell_count * 1.02
        if low <= voltage <= high:
            add(name, "AGREE",
                f"Pack {voltage:.1f} V is within the cell range "
                f"({low:.1f} to {high:.1f} V).")
        else:
            add(name, "DISAGREE",
                f"Pack {voltage:.1f} V is outside the range implied by "
                f"the cells ({low:.1f} to {high:.1f} V).",
                ("voltage",))
    else:
        add(name, "UNAVAILABLE", "Cell voltages are not reported.")

    # 3. Live reading against the latest stored reading.
    name = "Live vs stored reading"
    last = history[-1] if history else None
    age = (now - last.timestamp).total_seconds() / 60 if last else None

    if last and age is not None and age <= 10 and None not in (voltage, temperature):
        temp_gap = abs(temperature - (last.temperature or 0))
        volt_gap = abs(voltage - (last.voltage or 0))
        if temp_gap > 5 or volt_gap > 25:
            sensors = []
            if temp_gap > 5:
                sensors.append("temperature")
            if volt_gap > 25:
                sensors.append("voltage")
            add(name, "DISAGREE",
                f"Live differs from the reading {age:.0f} min ago by "
                f"{temp_gap:.1f} °C and {volt_gap:.1f} V.",
                sensors)
        else:
            add(name, "AGREE",
                f"Live reading is consistent with the one {age:.0f} min ago.")
    else:
        add(name, "UNAVAILABLE", "No stored reading from the last 10 minutes.")

    # 4. Stuck sensors: a value that never changes while others do.
    name = "Stuck sensor"
    window = history[-6:]

    if len(window) == 6:
        spreads = {}
        for field in ("voltage", "current", "temperature"):
            values = _column(window, field)
            if values:
                spreads[field] = max(values) - min(values)
        # A steady 0 A while parked is normal, not a stuck sensor.
        idle = all(abs(v) < 1.0 for v in _column(window, "current"))
        stuck = [
            f for f, s in spreads.items()
            if s == 0 and not (f == "current" and idle)
        ]
        others_moving = any(s > 0 for s in spreads.values())
        if stuck and others_moving:
            add(name, "DISAGREE",
                "Unchanged over the last 6 readings: " + ", ".join(stuck) + ".",
                stuck)
        else:
            add(name, "AGREE", "All sensors have varied over the last 6 readings.")
    else:
        add(name, "UNAVAILABLE", "Fewer than 6 stored readings.")

    # 5 and 6. Physically implausible changes between readings.
    # A single jump is often a restart or reconnection glitch, so at
    # least JUMPS_TO_FLAG are needed before blaming a sensor.
    JUMPS_TO_FLAG = 2

    impossible = 0
    jump_sensors = set()
    last_jump = None
    heating_without_load = 0

    for index, (previous, row) in enumerate(zip(history, history[1:])):

        minutes = (row.timestamp - previous.timestamp).total_seconds() / 60

        if minutes <= 0 or minutes > EPISODE_GAP_MINUTES:
            continue

        d_temp = (row.temperature or 0) - (previous.temperature or 0)
        d_volt = abs((row.voltage or 0) - (previous.voltage or 0))
        d_curr = abs((row.current or 0) - (previous.current or 0))

        if (abs(d_temp) > 5 or d_volt > 25) and d_curr < 20:
            # A spike and its return are one glitch, not two.
            if last_jump is None or index - last_jump > 1:
                impossible += 1
            last_jump = index
            if abs(d_temp) > 5:
                jump_sensors.add("temperature")
            if d_volt > 25:
                jump_sensors.add("voltage")

        if (
            d_temp > 3
            and abs(row.current or 0) < 30
            and abs(previous.current or 0) < 30
        ):
            heating_without_load += 1

    if len(history) >= 2:
        if impossible >= JUMPS_TO_FLAG:
            add("Rate of change", "DISAGREE",
                f"{impossible} jump(s) in " + " and ".join(sorted(jump_sensors))
                + " with no matching change in current.",
                sorted(jump_sensors))
        elif impossible:
            add("Rate of change", "AGREE",
                "One isolated jump, treated as a restart or "
                "reconnection glitch.")
        else:
            add("Rate of change", "AGREE",
                "All changes between readings are physically plausible.")

        if heating_without_load >= JUMPS_TO_FLAG:
            add("Temperature vs current", "DISAGREE",
                f"Temperature rose sharply {heating_without_load} time(s) "
                "while current was low.",
                ("temperature",))
        else:
            add("Temperature vs current", "AGREE",
                "Temperature changes are consistent with current.")
    else:
        add("Rate of change", "UNAVAILABLE", "Fewer than 2 stored readings.")
        add("Temperature vs current", "UNAVAILABLE", "Fewer than 2 stored readings.")

    disagreements = [c for c in checks if c["status"] == "DISAGREE"]
    available = any(c["status"] != "UNAVAILABLE" for c in checks)

    def spread(values):
        return round(max(values) - min(values), 2) if values else None

    return {
        "available": available,
        "disagreement_detected": bool(disagreements),
        "checks": checks,
        "checks_passed": sum(c["status"] == "AGREE" for c in checks),
        "checks_failed": len(disagreements),
        "suspect_sensors": sorted(suspects),
        "voltage_range": spread(_column(history, "voltage")),
        "current_range": spread(_column(history, "current")),
        "temperature_range": spread(_column(history, "temperature")),
        "message": (
            "Sensors disagree. Suspect: " + ", ".join(sorted(suspects)) + "."
            if disagreements else
            "All available sensor cross-checks agree."
        ),
    }


# ---------------------------------------------------------
# FEATURE 7
# BATTERY FAULT SEQUENCE PREDICTION
# ---------------------------------------------------------

# What typically follows once a parameter goes out of range.
FAULT_CHAINS = {
    "current": [
        "Temperature rise from resistive heating",
        "Voltage sag under load",
        "BMS power derating",
    ],
    "temperature": [
        "BMS thermal derating",
        "Accelerated cell ageing",
        "Over-temperature cutoff",
    ],
    "voltage_low": [
        "Weakest cells reach their minimum voltage",
        "Low-voltage cutoff",
    ],
    "voltage_high": [
        "Cell heating from overcharge",
        "Charge termination or overvoltage cutoff",
    ],
    "soc": [
        "Voltage sag under load",
        "Low-voltage cutoff",
    ],
}

PREDICTION_TARGETS = (
    # parameter, label, history field, direction, warning, critical, unit
    ("temperature", "Temperature", "temperature", "high",
     TEMP_WARNING, TEMP_CRITICAL, "°C"),
    ("current", "Current", "current", "high",
     CURRENT_WARNING, CURRENT_CRITICAL, "A"),
    ("voltage_low", "Low voltage", "voltage", "low",
     VOLTAGE_LOW_WARNING, VOLTAGE_LOW_CRITICAL, "V"),
    ("voltage_high", "High voltage", "voltage", "high",
     VOLTAGE_HIGH_WARNING, VOLTAGE_HIGH_CRITICAL, "V"),
    ("soc", "Low state of charge", "soc", "low",
     SOC_LOW_WARNING, SOC_LOW_CRITICAL, "%"),
)


def predict_fault_sequence(battery, history, horizon_hours=6):
    """
    Predict which limits will be crossed next, in what order and when.

    Each parameter's recent trend is extrapolated to its warning and
    critical limits. Crossings inside the horizon are ordered by
    arrival time, and the first one is followed by the fault chain that
    usually comes after it. Confidence reflects how well the trend fits
    and how many readings support it.
    """

    readings = _readings(battery)

    events = []

    for parameter, label, field, direction, warning, critical, unit in PREDICTION_TARGETS:

        value = readings.get(field)

        if value is None:
            continue

        fit = _fit_trend(history, field)
        slope = fit["slope"] if fit else None

        if field == "current":
            # Trend of the magnitude, so charging and discharging
            # current are treated alike.
            if slope is not None and value < 0:
                slope = -slope
            value = abs(value)

        if fit:
            quality = fit["r_squared"] * min(fit["points"], 12) / 12
            confidence = (
                "HIGH" if quality >= 0.6 else
                "MEDIUM" if quality >= 0.3 else
                "LOW"
            )
        else:
            confidence = None

        for level, limit in (("WARNING", warning), ("CRITICAL", critical)):

            name = f"{label} {level.lower()} limit ({limit:g} {unit})"

            if _breached(value, direction, limit):
                events.append({
                    "parameter": parameter,
                    "event": name,
                    "level": level,
                    "eta_minutes": 0,
                    "confidence": "HIGH",
                    "status": "REACHED",
                })
                continue

            if slope is None:
                continue

            heading_there = slope > 0 if direction == "high" else slope < 0

            if not heading_there:
                continue

            eta_hours = abs(limit - value) / abs(slope)

            if eta_hours <= horizon_hours:
                events.append({
                    "parameter": parameter,
                    "event": name,
                    "level": level,
                    "eta_minutes": round(eta_hours * 60),
                    "confidence": confidence,
                    "status": "PREDICTED",
                    "trend": f"{slope:+.2f} {unit}/h",
                })

    events.sort(key=lambda e: (e["eta_minutes"], e["level"] != "WARNING"))

    likely_progression = (
        FAULT_CHAINS.get(events[0]["parameter"], []) if events else []
    )

    def describe(event):
        if event["status"] == "REACHED":
            return f"{event['event']}: already reached"
        return (
            f"{event['event']}: in about {event['eta_minutes']} min "
            f"({event['confidence'].lower()} confidence)"
        )

    predicted_sequence = [describe(e) for e in events] + [
        f"Then likely: {step}" for step in likely_progression
    ]

    if len(history) < 3:
        message = (
            "Fewer than 3 stored readings, so only limits already "
            "reached can be shown."
        )
    elif events:
        first = events[0]
        message = f"Next expected: {first['event']}" + (
            " (already reached)." if first["status"] == "REACHED"
            else f" in about {first['eta_minutes']} min."
        )
    else:
        message = (
            f"No limit is expected to be crossed in the next "
            f"{horizon_hours} hours at current trends."
        )

    return {
        "prediction_available": bool(events),
        "prediction_type": "TREND_EXTRAPOLATION",
        "horizon_hours": horizon_hours,
        "events": events,
        "likely_progression": likely_progression,
        "predicted_sequence": predicted_sequence,
        "message": message,
    }


# ---------------------------------------------------------
# FEATURE 8
# PERSONALISED BATTERY PROTECTION STRATEGY
# ---------------------------------------------------------

PRIORITY_ORDER = ("IMMEDIATE", "SOON", "PLANNED")


def build_protection_strategy(battery, analyses):
    """
    Turn the other seven analyses into one prioritised action plan.

    analyses is a dict with the results of the other features, keyed
    as in the API response. Every action records which analysis it
    came from, so the plan is traceable.
    """

    actions = []
    seen = set()

    def add(priority, action, source):
        if action in seen:
            return
        seen.add(action)
        actions.append({
            "priority": priority,
            "action": action,
            "source": source,
        })

    decision = analyses.get("protection_decision_explanation", {})
    combos = analyses.get("multi_parameter_fault_detection", {})
    sequence = analyses.get("fault_sequence_prediction", {})
    sensors = analyses.get("sensor_disagreement_detection", {})
    behaviour = analyses.get("behaviour_change_detector", {})
    learning = analyses.get("protection_failure_learning", {})
    confidence = analyses.get("safety_confidence_score", {})

    # Current protection decision.
    code = decision.get("decision")

    if code in ("ISOLATE_BATTERY", "STOP_CHARGING", "LIMIT_POWER"):
        add("IMMEDIATE", decision.get("recommended_action"), "Protection decision")
    elif code == "MONITOR":
        add("SOON", decision.get("recommended_action"), "Protection decision")

    for combo in combos.get("combinations", []):
        priority = "IMMEDIATE" if combo["severity"] in ("CRITICAL", "HIGH") else "SOON"
        add(priority, combo["recommendation"], f"Fault combination: {combo['name']}")

    # Predicted crossings: act before they arrive.
    for event in sequence.get("events", []):
        if event["status"] != "PREDICTED":
            continue
        priority = "IMMEDIATE" if event["eta_minutes"] <= 30 else "SOON"
        add(
            priority,
            f"Act before the {event['event']} is reached in about "
            f"{event['eta_minutes']} min.",
            "Fault sequence prediction",
        )

    # Sensor problems undermine every other result.
    suspects = sensors.get("suspect_sensors") or []

    if suspects:
        add(
            "SOON",
            "Inspect the " + ", ".join(suspects) + " sensor wiring and "
            "calibration; readings from it may be wrong.",
            "Sensor disagreement",
        )

    if behaviour.get("changed"):
        resistance = behaviour.get("internal_resistance") or {}
        if resistance.get("changed"):
            add(
                "PLANNED",
                "Book an internal resistance test; voltage sag per amp "
                "has risen noticeably.",
                "Behaviour change",
            )
        add(
            "PLANNED",
            "Review recent usage for the cause of the behaviour change.",
            "Behaviour change",
        )

    for failure in learning.get("failures", []):
        add(
            "SOON",
            f"Find the root cause: {failure}",
            "Protection failure learning",
        )

    for protection in learning.get("protections", []):
        if protection.get("suggest_earlier_warning"):
            add(
                "PLANNED",
                f"Lower the {protection['label'].lower()} warning to "
                f"{protection['learned_early_warning']} for this battery; "
                "past breaches started from there.",
                "Protection failure learning",
            )

    if confidence.get("confidence_level") == "LOW":
        add(
            "SOON",
            "Restore reliable telemetry before trusting the safety "
            "verdict.",
            "Safety confidence",
        )

    # Long-term care from the pack's own state.
    soh = _number(battery.get("soh"))
    soc = _number(battery.get("soc"))

    if soh is not None and soh < SOH_WARNING:
        add(
            "PLANNED",
            f"Schedule a health inspection (state of health {soh:.0f}%) "
            "and avoid fast charging.",
            "Battery state",
        )

    if soc is not None and soc <= SOC_LOW_WARNING:
        add(
            "SOON",
            f"Recharge soon (state of charge {soc:.0f}%).",
            "Battery state",
        )

    if not actions:
        add(
            "PLANNED",
            "Continue normal operation and routine monitoring.",
            "All analyses",
        )

    actions.sort(key=lambda a: PRIORITY_ORDER.index(a["priority"]))

    return {
        "battery_id": battery.get("battery_id"),
        "actions": actions,
        "strategy": [a["action"] for a in actions],
        "immediate_count": sum(a["priority"] == "IMMEDIATE" for a in actions),
        "strategy_type": "COMBINED_ANALYSIS",
        "generated_at": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------
# ALL FEATURES TOGETHER
# ---------------------------------------------------------

def analyse_battery(battery, history, learning_history=None):
    """Run every analysis and return them keyed as in the API."""

    combinations = detect_fault_combinations(battery, history)

    analyses = {
        "multi_parameter_fault_detection": combinations,
        "protection_decision_explanation":
            explain_protection_decision(battery, history, combinations),
        "behaviour_change_detector": detect_behaviour_change(history),
        "protection_failure_learning": learn_protection_failures(
            battery,
            learning_history if learning_history is not None else history,
        ),
        "sensor_disagreement_detection":
            detect_sensor_disagreement(battery, history),
        "fault_sequence_prediction": predict_fault_sequence(battery, history),
        "safety_confidence_score":
            calculate_safety_confidence(battery, history),
    }

    analyses["personalised_protection_strategy"] = (
        build_protection_strategy(battery, analyses)
    )

    return analyses
