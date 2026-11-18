"""
VoltIQ Advanced Battery Intelligence Engine

Implements:
1. Predictive Battery Health
2. Remaining Useful Life (RUL)
3. AI Anomaly Detection
4. Smart Charging Optimization
5. Battery Degradation Forecasting
6. Intelligent Maintenance Prediction
7. Driving Range Prediction
8. Fleet Intelligence and Comparison

Predictions are estimates, not certified battery-life measurements.
"""

from datetime import datetime, timedelta, timezone
from statistics import mean, pstdev
from typing import Optional

from sqlalchemy.orm import Session

from ..models import Battery, Vehicle, Telemetry


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

TELEMETRY_FRESH_SECONDS = 120
MAX_HISTORY_RECORDS = 500

# Provisional EV pack-level thresholds.
# Replace with actual manufacturer/BMS limits when available.
VOLTAGE_WARNING_LOW = 350
VOLTAGE_CRITICAL_LOW = 330
VOLTAGE_WARNING_HIGH = 430
VOLTAGE_CRITICAL_HIGH = 450

CURRENT_WARNING = 130
CURRENT_CRITICAL = 145

TEMPERATURE_WARNING = 40
TEMPERATURE_CRITICAL = 45

# Generic assumption. Replace with actual vehicle efficiency.
DEFAULT_CAPACITY_KWH = 70.0
DEFAULT_EFFICIENCY_KWH_PER_KM = 0.18


# ---------------------------------------------------------
# GENERAL HELPERS
# ---------------------------------------------------------

def _utc_now():
    return datetime.now(timezone.utc)


def _normalise_datetime(value):
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _safe_float(value, default=None):
    try:
        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def _battery_identifier(value):
    """
    Accept either BAT-001 or EV-001 identifiers.
    """

    value = str(value).strip().upper()

    if value.startswith("EV-"):
        return value.replace("EV-", "BAT-", 1)

    return value


def _is_admin(user):
    return getattr(user, "role", "") == "admin"


# ---------------------------------------------------------
# ACCESS CONTROL
# ---------------------------------------------------------

def _get_authorised_battery(db: Session, battery_id: str, user):
    """
    Find a battery and verify that the requesting user
    has permission to access its vehicle.
    """

    battery_id = _battery_identifier(battery_id)

    query = (
        db.query(Battery, Vehicle)
        .join(Vehicle, Battery.vehicle_id == Vehicle.id)
        .filter(Battery.battery_id == battery_id)
    )

    result = query.first()

    if result is None:
        return None, None

    battery, vehicle = result

    if not _is_admin(user):
        if vehicle.owner_id != user.id:
            return None, None

    return battery, vehicle


# ---------------------------------------------------------
# TELEMETRY HISTORY
# ---------------------------------------------------------

def _get_history(db: Session, battery_id: str):
    """
    Retrieve stored telemetry for a battery.

    Newest readings are returned first.
    """

    battery_id = _battery_identifier(battery_id)

    records = (
        db.query(Telemetry)
        .filter(Telemetry.battery_id == battery_id)
        .order_by(Telemetry.timestamp.desc())
        .limit(MAX_HISTORY_RECORDS)
        .all()
    )

    return records


def _history_to_dict(records):
    result = []

    for record in records:
        timestamp = _normalise_datetime(record.timestamp)

        result.append({
            "timestamp": timestamp.isoformat() if timestamp else None,
            "voltage": _safe_float(record.voltage),
            "current": _safe_float(record.current),
            "temperature": _safe_float(record.temperature),
            "soc": _safe_float(record.soc),
            "soh": _safe_float(record.soh),
            "cycles": _safe_float(record.cycles),
            "power_kw": _safe_float(record.power_kw),
        })

    return result


def _latest_live_reading(records):
    """
    Return the newest telemetry reading only when it is recent.
    """

    if not records:
        return None

    latest = records[0]
    timestamp = _normalise_datetime(latest.timestamp)

    if timestamp is None:
        return None

    age = (_utc_now() - timestamp).total_seconds()

    if age < 0 or age > TELEMETRY_FRESH_SECONDS:
        return None

    return {
        "voltage": _safe_float(latest.voltage),
        "current": _safe_float(latest.current),
        "temperature": _safe_float(latest.temperature),
        "soc": _safe_float(latest.soc),
        "soh": _safe_float(latest.soh),
        "cycles": _safe_float(latest.cycles),
        "power_kw": _safe_float(latest.power_kw),
        "timestamp": timestamp.isoformat(),
    }


# ---------------------------------------------------------
# SIMULATOR FALLBACK
# ---------------------------------------------------------

def _get_simulated_reading(battery_id: str):
    """
    Use the existing simulation engine when live telemetry
    is unavailable.

    This does not mean that physical hardware is connected.
    """

    try:
        from ..simulator.engine import get_simulation_engine

        engine = get_simulation_engine()

        reading = engine.get_battery(battery_id)

        if not reading:
            return None

        return {
            "voltage": _safe_float(reading.get("voltage")),
            "current": _safe_float(reading.get("current")),
            "temperature": _safe_float(reading.get("temperature")),
            "soc": _safe_float(reading.get("soc")),
            "soh": _safe_float(reading.get("soh")),
            "cycles": _safe_float(
                reading.get("cycle_count", reading.get("cycles"))
            ),
            "power_kw": _safe_float(reading.get("power_kw")),
            "capacity_kwh": _safe_float(
                reading.get("capacity_kwh")
            ),
            "remaining_kwh": _safe_float(
                reading.get("remaining_kwh")
            ),
            "timestamp": _utc_now().isoformat(),
        }

    except Exception:
        return None


# ---------------------------------------------------------
# DATA SOURCE SELECTION
# ---------------------------------------------------------

def _get_battery_data(db, battery, battery_id):
    """
    Priority:
    1. Fresh ESP32 telemetry
    2. Existing simulator
    3. Latest historical telemetry

    The source is always returned explicitly.
    """

    history = _get_history(db, battery_id)

    live = _latest_live_reading(history)

    if live is not None:
        live["source"] = "hardware"
        live["connection_status"] = "connected"

        return live, history

    simulated = _get_simulated_reading(battery_id)

    if simulated is not None:
        simulated["source"] = "simulator"
        simulated["connection_status"] = "disconnected"

        return simulated, history

    if history:
        historical = _history_to_dict(history)[0]

        historical["source"] = "historical"
        historical["connection_status"] = "stale"

        return historical, history

    return None, history


# ---------------------------------------------------------
# BATTERY RISK INDEX
# ---------------------------------------------------------

def _calculate_risk(reading):
    """
    Calculate a provisional battery risk score from 0 to 100.
    Higher scores mean higher risk.
    """

    score = 0
    reasons = []

    voltage = reading.get("voltage")
    current = reading.get("current")
    temperature = reading.get("temperature")

    if voltage is not None:

        if voltage <= VOLTAGE_CRITICAL_LOW:
            score += 35
            reasons.append("Critical low voltage")

        elif voltage <= VOLTAGE_WARNING_LOW:
            score += 20
            reasons.append("Low voltage")

        elif voltage >= VOLTAGE_CRITICAL_HIGH:
            score += 35
            reasons.append("Critical high voltage")

        elif voltage >= VOLTAGE_WARNING_HIGH:
            score += 20
            reasons.append("High voltage")

    if current is not None:

        if current >= CURRENT_CRITICAL:
            score += 30
            reasons.append("Critical current")

        elif current >= CURRENT_WARNING:
            score += 15
            reasons.append("High current")

    if temperature is not None and temperature > 0:

        if temperature >= TEMPERATURE_CRITICAL:
            score += 35
            reasons.append("Critical temperature")

        elif temperature >= TEMPERATURE_WARNING:
            score += 20
            reasons.append("High temperature")

    score = min(score, 100)

    if score >= 70:
        level = "critical"

    elif score >= 35:
        level = "high"

    elif score >= 15:
        level = "moderate"

    else:
        level = "low"

    return {
        "score": score,
        "level": level,
        "reasons": reasons,
    }


# ---------------------------------------------------------
# HEALTH TREND ANALYSIS
# ---------------------------------------------------------

def _calculate_soh_trend(records):
    """
    Estimate SOH change per day using stored telemetry.

    Requires at least three readings spanning more than one day.
    """

    points = []

    for record in records:
        soh = _safe_float(record.soh)
        timestamp = _normalise_datetime(record.timestamp)

        if soh is not None and timestamp is not None:
            points.append((timestamp, soh))

    points.sort(key=lambda item: item[0])

    if len(points) < 3:
        return {
            "available": False,
            "reason": "At least three SOH readings are required.",
            "points": len(points),
        }

    start_time = points[0][0]

    x_values = [
        (timestamp - start_time).total_seconds() / 86400
        for timestamp, _ in points
    ]

    y_values = [soh for _, soh in points]

    x_mean = mean(x_values)
    y_mean = mean(y_values)

    denominator = sum(
        (x - x_mean) ** 2 for x in x_values
    )

    if denominator == 0:
        return {
            "available": False,
            "reason": "Readings do not span enough time.",
            "points": len(points),
        }

    slope = sum(
        (x - x_mean) * (y - y_mean)
        for x, y in zip(x_values, y_values)
    ) / denominator

    return {
        "available": True,
        "soh_change_per_day": round(slope, 6),
        "points": len(points),
        "days_observed": round(max(x_values), 2),
        "latest_soh": round(y_values[-1], 2),
    }


# ---------------------------------------------------------
# FEATURE 1: PREDICTIVE BATTERY HEALTH
# ---------------------------------------------------------

def _predictive_health(reading, trend):
    soh = reading.get("soh")

    if soh is None:
        return {
            "available": False,
            "message": "SOH data is unavailable.",
        }

    predictions = {}

    if trend["available"]:
        daily_change = trend["soh_change_per_day"]

        for days in [30, 90, 180, 365]:
            predictions[f"{days}_days"] = round(
                max(0, min(100, soh + daily_change * days)),
                2,
            )

        basis = "historical_trend"

    else:
        for days in [30, 90, 180, 365]:
            predictions[f"{days}_days"] = None

        basis = "insufficient_history"

    return {
        "available": True,
        "current_soh": round(soh, 2),
        "predictions": predictions,
        "basis": basis,
        "message": (
            "Forecast is based on historical SOH readings."
            if trend["available"]
            else "Collect more historical SOH readings to calculate a forecast."
        ),
    }


# ---------------------------------------------------------
# FEATURE 2: REMAINING USEFUL LIFE
# ---------------------------------------------------------

def _predict_rul(reading, trend):
    soh = reading.get("soh")

    if soh is None:
        return {
            "available": False,
            "message": "SOH data is unavailable.",
        }

    if not trend["available"]:
        return {
            "available": False,
            "estimated_days": None,
            "message": "More historical SOH data is required.",
        }

    daily_change = trend["soh_change_per_day"]

    if daily_change >= 0:
        return {
            "available": False,
            "estimated_days": None,
            "message": "No measurable degradation trend is available.",
        }

    # Provisional end-of-life reference.
    end_of_life_soh = 70.0

    if soh <= end_of_life_soh:
        return {
            "available": True,
            "estimated_days": 0,
            "message": "SOH has reached the provisional reference threshold.",
        }

    days_remaining = (soh - end_of_life_soh) / abs(daily_change)

    return {
        "available": True,
        "estimated_days": round(days_remaining, 1),
        "estimated_years": round(days_remaining / 365, 2),
        "reference_soh": end_of_life_soh,
        "message": "Estimated from historical SOH degradation.",
    }


# ---------------------------------------------------------
# FEATURE 3: AI ANOMALY DETECTION
# ---------------------------------------------------------

def _detect_anomalies(reading, records):
    anomalies = []

    fields = [
        ("voltage", 0.05),
        ("current", 0.05),
        ("temperature", 0.05),
        ("soc", 0.05),
        ("soh", 0.05),
    ]

    history = _history_to_dict(records)

    for field, minimum_deviation in fields:

        current_value = reading.get(field)

        values = [
            item[field]
            for item in history[1:]
            if item.get(field) is not None
        ]

        if current_value is None or len(values) < 5:
            continue

        avg = mean(values)
        deviation = pstdev(values)

        if deviation == 0:
            if current_value != avg:
                anomalies.append({
                    "parameter": field,
                    "value": current_value,
                    "reason": "Reading differs from stable historical values.",
                })

            continue

        z_score = abs(current_value - avg) / deviation

        if z_score >= 3:
            anomalies.append({
                "parameter": field,
                "value": current_value,
                "historical_average": round(avg, 2),
                "z_score": round(z_score, 2),
                "reason": "Reading is statistically unusual.",
            })

    return {
        "available": True,
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
        "method": "historical_statistical_detection",
    }


# ---------------------------------------------------------
# FEATURE 4: SMART CHARGING OPTIMIZATION
# ---------------------------------------------------------

def _smart_charging(reading, risk):
    soc = reading.get("soc")
    temperature = reading.get("temperature")

    recommendations = []

    if soc is None:
        return {
            "available": False,
            "message": "SOC data is unavailable.",
        }

    if risk["level"] == "critical":
        recommendations.append(
            "Inspect the battery before continuing normal charging."
        )

    if temperature is not None and temperature >= TEMPERATURE_WARNING:
        recommendations.append(
            "Avoid high-rate charging while battery temperature is elevated."
        )

    if soc < 20:
        recommendations.append(
            "Consider charging soon to avoid prolonged operation at very low SOC."
        )

    elif soc >= 90:
        recommendations.append(
            "Consider limiting routine charging to reduce time spent at high SOC, "
            "subject to manufacturer guidance."
        )

    else:
        recommendations.append(
            "Battery SOC is within a typical operating range."
        )

    return {
        "available": True,
        "current_soc": round(soc, 2),
        "recommendations": recommendations,
        "note": (
            "Advisory only. Actual charging limits must follow the BMS "
            "and vehicle manufacturer's instructions."
        ),
    }


# ---------------------------------------------------------
# FEATURE 5: BATTERY DEGRADATION FORECASTING
# ---------------------------------------------------------

def _degradation_forecast(reading, trend):
    soh = reading.get("soh")

    if soh is None:
        return {
            "available": False,
            "message": "SOH data is unavailable.",
        }

    if not trend["available"]:
        return {
            "available": False,
            "message": "More historical SOH data is required.",
        }

    daily_change = trend["soh_change_per_day"]

    monthly_change = daily_change * 30

    return {
        "available": True,
        "current_soh": round(soh, 2),
        "estimated_monthly_change": round(monthly_change, 4),
        "estimated_annual_change": round(daily_change * 365, 4),
        "trend": (
            "degrading" if daily_change < 0
            else "stable_or_improving"
        ),
        "basis": "historical_soh_trend",
    }


# ---------------------------------------------------------
# FEATURE 6: INTELLIGENT MAINTENANCE PREDICTION
# ---------------------------------------------------------

def _maintenance_prediction(reading, risk, records):
    recommendations = []

    temperature = reading.get("temperature")
    soh = reading.get("soh")
    current = reading.get("current")

    if risk["level"] == "critical":
        recommendations.append({
            "priority": "critical",
            "action": "Arrange immediate battery inspection.",
        })

    if temperature is not None and temperature >= TEMPERATURE_WARNING:
        recommendations.append({
            "priority": "high",
            "action": "Inspect battery cooling and thermal management.",
        })

    if soh is not None and soh < 80:
        recommendations.append({
            "priority": "medium",
            "action": "Schedule a battery health assessment.",
        })

    if current is not None and current >= CURRENT_WARNING:
        recommendations.append({
            "priority": "high",
            "action": "Review current load and electrical connections.",
        })

    if len(records) == 0:
        recommendations.append({
            "priority": "low",
            "action": "Start collecting telemetry for maintenance trend analysis.",
        })

    if not recommendations:
        recommendations.append({
            "priority": "low",
            "action": "No immediate maintenance concern detected by current rules.",
        })

    return {
        "available": True,
        "recommendations": recommendations,
        "method": "rule_based_maintenance_assessment",
    }


# ---------------------------------------------------------
# FEATURE 7: DRIVING RANGE PREDICTION
# ---------------------------------------------------------

def _range_prediction(reading, battery):
    soc = reading.get("soc")

    if soc is None:
        return {
            "available": False,
            "message": "SOC data is unavailable.",
        }

    capacity = reading.get("capacity_kwh")

    if capacity is None:
        capacity = DEFAULT_CAPACITY_KWH

    capacity = _safe_float(capacity, DEFAULT_CAPACITY_KWH)

    remaining_kwh = capacity * max(0, min(100, soc)) / 100

    estimated_range = (
        remaining_kwh / DEFAULT_EFFICIENCY_KWH_PER_KM
    )

    return {
        "available": True,
        "soc": round(soc, 2),
        "capacity_kwh": round(capacity, 2),
        "remaining_energy_kwh": round(remaining_kwh, 2),
        "estimated_range_km": round(estimated_range, 1),
        "assumed_efficiency_kwh_per_km": DEFAULT_EFFICIENCY_KWH_PER_KM,
        "note": (
            "Provisional estimate. Replace the generic efficiency "
            "assumption with measured vehicle consumption."
        ),
    }


# ---------------------------------------------------------
# FEATURE 8: FLEET INTELLIGENCE
# ---------------------------------------------------------

def _fleet_summary(db: Session, user):
    query = (
        db.query(Battery, Vehicle)
        .join(Vehicle, Battery.vehicle_id == Vehicle.id)
    )

    if not _is_admin(user):
        query = query.filter(Vehicle.owner_id == user.id)

    rows = query.all()

    batteries = []

    for battery, vehicle in rows:
        batteries.append({
            "battery_id": battery.battery_id,
            "vehicle_id": vehicle.vehicle_id,
            "vehicle_name": vehicle.name,
            "soc": _safe_float(battery.soc),
            "soh": _safe_float(battery.soh),
            "temperature": _safe_float(battery.temperature),
            "status": battery.status,
        })

    soh_values = [
        item["soh"]
        for item in batteries
        if item["soh"] is not None
    ]

    average_soh = round(mean(soh_values), 2) if soh_values else None

    return {
        "battery_count": len(batteries),
        "average_soh": average_soh,
        "batteries": batteries,
        "comparison_basis": "battery_database_values",
    }


# ---------------------------------------------------------
# COMPLETE ADVANCED INTELLIGENCE RESPONSE
# ---------------------------------------------------------

def get_battery_intelligence(
    db: Session,
    user,
    battery_id: str,
):
    """
    Generate all eight advanced intelligence features
    for one authorised battery.
    """

    battery, vehicle = _get_authorised_battery(
        db,
        battery_id,
        user,
    )

    if battery is None:
        return None

    reading, records = _get_battery_data(
        db,
        battery,
        battery_id,
    )

    if reading is None:
        return {
            "battery_id": battery.battery_id,
            "vehicle_id": vehicle.vehicle_id,
            "available": False,
            "message": "No telemetry or simulator data is available.",
        }

    trend = _calculate_soh_trend(records)

    risk = _calculate_risk(reading)

    return {
        "battery_id": battery.battery_id,
        "vehicle_id": vehicle.vehicle_id,
        "vehicle_name": vehicle.name,
        "available": True,
        "generated_at": _utc_now().isoformat(),

        "data_source": reading.get("source"),
        "connection_status": reading.get("connection_status"),

        "current_reading": {
            "voltage": reading.get("voltage"),
            "current": reading.get("current"),
            "temperature": reading.get("temperature"),
            "soc": reading.get("soc"),
            "soh": reading.get("soh"),
            "cycles": reading.get("cycles"),
            "power_kw": reading.get("power_kw"),
            "timestamp": reading.get("timestamp"),
        },

        "battery_risk_index": risk,

        "predictive_battery_health": _predictive_health(
            reading,
            trend,
        ),

        "remaining_useful_life": _predict_rul(
            reading,
            trend,
        ),

        "ai_anomaly_detection": _detect_anomalies(
            reading,
            records,
        ),

        "smart_charging_optimization": _smart_charging(
            reading,
            risk,
        ),

        "battery_degradation_forecast": _degradation_forecast(
            reading,
            trend,
        ),

        "intelligent_maintenance_prediction": _maintenance_prediction(
            reading,
            risk,
            records,
        ),

        "driving_range_prediction": _range_prediction(
            reading,
            battery,
        ),

        "fleet_intelligence": _fleet_summary(
            db,
            user,
        ),

        "historical_analysis": {
            "telemetry_records": len(records),
            "soh_trend": trend,
        },
    }


# ---------------------------------------------------------
# FLEET INTELLIGENCE ENDPOINT SERVICE
# ---------------------------------------------------------

def get_fleet_intelligence(db: Session, user):
    """
    Return a fleet-wide battery comparison.
    """

    return _fleet_summary(db, user)