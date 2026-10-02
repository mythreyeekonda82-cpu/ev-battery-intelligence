"""
VoltIQ Battery Intelligence Engine

Responsible for:
- SOC estimation
- SOH estimation
- battery health classification
- temperature assessment
- cell imbalance detection
- protection events
- runtime estimation
- battery fault analysis
"""

from __future__ import annotations

from typing import Any


# ============================================================
# BATTERY LIMITS
# ============================================================

CELL_MAX_VOLTAGE = 4.20
CELL_MIN_VOLTAGE = 3.00

TEMPERATURE_WARNING = 40.0
TEMPERATURE_CRITICAL = 45.0

DEFAULT_MAX_CURRENT = 150.0

CELL_IMBALANCE_WARNING_MV = 25.0
CELL_IMBALANCE_CRITICAL_MV = 40.0


# ============================================================
# SOC
# ============================================================

def soc_from_cell_voltage(cell_voltage: float) -> float:
    """
    Estimate SOC from average cell voltage.

    This is a simplified demonstration model.
    """

    voltage = float(cell_voltage)

    soc = (
        (voltage - CELL_MIN_VOLTAGE)
        /
        (CELL_MAX_VOLTAGE - CELL_MIN_VOLTAGE)
    ) * 100.0

    return round(
        max(0.0, min(100.0, soc)),
        2
    )


# ============================================================
# TEMPERATURE STATUS
# ============================================================

def temperature_status(
    temperature_c: float
) -> str:

    temperature = float(temperature_c)

    if temperature >= TEMPERATURE_CRITICAL:
        return "CRITICAL"

    if temperature >= TEMPERATURE_WARNING:
        return "WARNING"

    return "NORMAL"


# ============================================================
# CELL IMBALANCE STATUS
# ============================================================

def cell_imbalance_status(
    delta_mv: float
) -> str:

    delta = float(delta_mv)

    if delta >= CELL_IMBALANCE_CRITICAL_MV:
        return "CRITICAL"

    if delta >= CELL_IMBALANCE_WARNING_MV:
        return "WARNING"

    return "NORMAL"


# ============================================================
# HEALTH CLASSIFICATION
# ============================================================

def classify_health(
    cell_voltage: float,
    temperature_c: float,
    current_a: float,
    capacity_pct: float,
    cell_delta_mv: float = 0.0,
    max_current: float = DEFAULT_MAX_CURRENT
) -> str:
    """
    Determine overall battery condition.
    """

    voltage = float(cell_voltage)
    temperature = float(temperature_c)
    current = abs(float(current_a))
    capacity = float(capacity_pct)
    delta = float(cell_delta_mv)

    # Critical conditions
    if temperature >= TEMPERATURE_CRITICAL:
        return "CRITICAL"

    if voltage >= CELL_MAX_VOLTAGE:
        return "CRITICAL"

    if voltage <= CELL_MIN_VOLTAGE:
        return "CRITICAL"

    if current > max_current:
        return "CRITICAL"

    if delta >= CELL_IMBALANCE_CRITICAL_MV:
        return "CRITICAL"

    # Weak / warning conditions
    if temperature >= TEMPERATURE_WARNING:
        return "WEAK"

    if capacity < 90.0:
        return "WEAK"

    if delta >= CELL_IMBALANCE_WARNING_MV:
        return "WEAK"

    return "HEALTHY"


# ============================================================
# RUNTIME ESTIMATION
# ============================================================

def runtime_hours(
    remaining_ah: float,
    current_a: float
) -> float:
    """
    Estimate remaining runtime in hours.
    """

    remaining = max(
        0.0,
        float(remaining_ah)
    )

    current = abs(
        float(current_a)
    )

    if current <= 0.01:
        return 0.0

    return round(
        remaining / current,
        2
    )


# ============================================================
# PROTECTION EVENTS
# ============================================================

def protection_events(
    cell_voltage: float,
    temperature_c: float,
    current_a: float,
    max_current: float = DEFAULT_MAX_CURRENT
) -> list[dict[str, Any]]:
    """
    Detect battery protection events.
    """

    events: list[dict[str, Any]] = []

    voltage = float(cell_voltage)
    temperature = float(temperature_c)
    current = abs(float(current_a))

    if voltage >= CELL_MAX_VOLTAGE:
        events.append({
            "type": "OVER_VOLTAGE",
            "severity": "CRITICAL",
            "message": "Cell voltage exceeded safe upper limit."
        })

    if voltage <= CELL_MIN_VOLTAGE:
        events.append({
            "type": "UNDER_VOLTAGE",
            "severity": "CRITICAL",
            "message": "Cell voltage dropped below safe lower limit."
        })

    if temperature >= TEMPERATURE_CRITICAL:
        events.append({
            "type": "OVER_TEMPERATURE",
            "severity": "CRITICAL",
            "message": "Battery temperature exceeded critical limit."
        })

    elif temperature >= TEMPERATURE_WARNING:
        events.append({
            "type": "HIGH_TEMPERATURE",
            "severity": "WARNING",
            "message": "Battery temperature is approaching the critical limit."
        })

    if current > max_current:
        events.append({
            "type": "OVER_CURRENT",
            "severity": "CRITICAL",
            "message": "Battery current exceeded configured limit."
        })

    return events


# ============================================================
# CELL FAULTS
# ============================================================

def cell_faults(
    min_cell_voltage: float,
    max_cell_voltage: float
) -> list[dict[str, Any]]:
    """
    Detect voltage-related cell faults.
    """

    faults: list[dict[str, Any]] = []

    minimum = float(min_cell_voltage)
    maximum = float(max_cell_voltage)

    delta_mv = (
        maximum - minimum
    ) * 1000.0

    if minimum <= CELL_MIN_VOLTAGE:
        faults.append({
            "type": "CELL_UNDERVOLTAGE",
            "severity": "CRITICAL",
            "message": "One or more cells are below the safe voltage range."
        })

    if maximum >= CELL_MAX_VOLTAGE:
        faults.append({
            "type": "CELL_OVERVOLTAGE",
            "severity": "CRITICAL",
            "message": "One or more cells are above the safe voltage range."
        })

    if delta_mv >= CELL_IMBALANCE_CRITICAL_MV:
        faults.append({
            "type": "CELL_IMBALANCE",
            "severity": "CRITICAL",
            "message": (
                f"Cell voltage difference is "
                f"{delta_mv:.1f} mV."
            )
        })

    elif delta_mv >= CELL_IMBALANCE_WARNING_MV:
        faults.append({
            "type": "CELL_IMBALANCE",
            "severity": "WARNING",
            "message": (
                f"Cell voltage difference is "
                f"{delta_mv:.1f} mV."
            )
        })

    return faults


# ============================================================
# COMPLETE BATTERY ANALYSIS
# ============================================================

def analyze_battery(
    cell_voltage: float,
    temperature_c: float,
    current_a: float,
    capacity_pct: float,
    remaining_ah: float = 0.0,
    cell_delta_mv: float = 0.0,
    min_cell_voltage: float | None = None,
    max_cell_voltage: float | None = None,
    max_current: float = DEFAULT_MAX_CURRENT
) -> dict[str, Any]:
    """
    Perform complete battery analysis.
    """

    average_voltage = float(
        cell_voltage
    )

    temperature = float(
        temperature_c
    )

    current = float(
        current_a
    )

    capacity = float(
        capacity_pct
    )

    delta = float(
        cell_delta_mv
    )

    # --------------------------------------------------------
    # SOC
    # --------------------------------------------------------

    soc = soc_from_cell_voltage(
        average_voltage
    )

    # --------------------------------------------------------
    # Health
    # --------------------------------------------------------

    health = classify_health(
        cell_voltage=average_voltage,
        temperature_c=temperature,
        current_a=current,
        capacity_pct=capacity,
        cell_delta_mv=delta,
        max_current=max_current
    )

    # --------------------------------------------------------
    # Runtime
    # --------------------------------------------------------

    runtime = runtime_hours(
        remaining_ah=remaining_ah,
        current_a=current
    )

    # --------------------------------------------------------
    # Protection
    # --------------------------------------------------------

    protection = protection_events(
        cell_voltage=average_voltage,
        temperature_c=temperature,
        current_a=current,
        max_current=max_current
    )

    # --------------------------------------------------------
    # Cell faults
    # --------------------------------------------------------

    cell_fault_list: list[dict[str, Any]] = []

    if (
        min_cell_voltage is not None
        and max_cell_voltage is not None
    ):
        cell_fault_list = cell_faults(
            min_cell_voltage=min_cell_voltage,
            max_cell_voltage=max_cell_voltage
        )

    # --------------------------------------------------------
    # Combine faults
    # --------------------------------------------------------

    faults = (
        protection
        +
        cell_fault_list
    )

    # --------------------------------------------------------
    # Human-readable explanation
    # --------------------------------------------------------

    reasons: list[str] = []

    if capacity < 90:
        reasons.append(
            f"SOH is reduced to {capacity:.1f}%."
        )

    if temperature >= TEMPERATURE_WARNING:
        reasons.append(
            f"Temperature is elevated at {temperature:.1f} °C."
        )

    if delta >= CELL_IMBALANCE_WARNING_MV:
        reasons.append(
            f"Cell imbalance is {delta:.1f} mV."
        )

    if abs(current) > max_current:
        reasons.append(
            f"Current exceeds the configured {max_current:.0f} A limit."
        )

    if not reasons:
        reasons.append(
            "Battery operating parameters are within normal limits."
        )

    return {
        "soc": round(soc, 2),

        "health": health,

        "temperature": {
            "value_c": round(temperature, 2),
            "status": temperature_status(temperature)
        },

        "cell_imbalance": {
            "delta_mv": round(delta, 2),
            "status": cell_imbalance_status(delta)
        },

        "runtime_hours": runtime,

        "protection_events": protection,

        "cell_faults": cell_fault_list,

        "faults": faults,

        "reasons": reasons,

        "safe": health == "HEALTHY"
    }