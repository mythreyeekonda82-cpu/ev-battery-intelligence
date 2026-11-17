import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    Vehicle,
    BatteryIntelligenceEvent,
    BatterySensorState,
)
from ..security import get_current_user
from ..simulator.engine import get_simulation_engine


router = APIRouter(
    prefix="/api/battery-intelligence",
    tags=["Battery Intelligence"],
)


# ============================================================
# EV BATTERY PACK THRESHOLDS
# ============================================================

# These are initial software-monitoring thresholds for this
# simulated 375–405 V battery pack. They are not BMS limits.
# Replace them with manufacturer/BMS limits before live use.

VOLTAGE_WARNING_LOW = 350.0
VOLTAGE_WARNING_HIGH = 430.0
VOLTAGE_CRITICAL_LOW = 330.0
VOLTAGE_CRITICAL_HIGH = 450.0

CURRENT_WARNING = 130.0
CURRENT_CRITICAL = 145.0

TEMP_WARNING = 40.0
TEMP_CRITICAL = 45.0

SENSOR_REPEAT_LIMIT = 8


# ============================================================
# COMMON HELPERS
# ============================================================

def get_allowed_vehicle_ids(db, user):
    query = db.query(Vehicle)

    if user.role != "admin":
        query = query.filter(Vehicle.owner_id == user.id)

    return {
        vehicle.vehicle_id
        for vehicle in query.all()
    }


def check_battery_access(db, user, battery_id):
    battery_id = battery_id.upper()

    if not battery_id.startswith("BAT-"):
        raise HTTPException(
            status_code=400,
            detail="Invalid battery ID",
        )

    vehicle_id = battery_id.replace("BAT-", "EV-", 1)

    allowed = get_allowed_vehicle_ids(db, user)

    if vehicle_id not in allowed:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this battery",
        )

    engine = get_simulation_engine()
    battery = engine.get_battery(battery_id)

    if battery is None:
        raise HTTPException(
            status_code=404,
            detail="Battery not found",
        )

    return battery


def record_event(
    db,
    battery_id,
    event_type,
    severity,
    message,
    vehicle_id=None,
    risk_score=None,
    start_value=None,
    end_value=None,
    duration_seconds=None,
    details=None,
):
    event = BatteryIntelligenceEvent(
        battery_id=battery_id,
        vehicle_id=vehicle_id,
        event_type=event_type,
        severity=severity,
        message=message,
        risk_score=risk_score,
        start_value=start_value,
        end_value=end_value,
        duration_seconds=duration_seconds,
        details=json.dumps(details or {}),
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return event


def event_to_dict(event):
    try:
        details = json.loads(event.details or "{}")
    except (TypeError, ValueError):
        details = {}

    return {
        "id": event.id,
        "battery_id": event.battery_id,
        "vehicle_id": event.vehicle_id,
        "event_type": event.event_type,
        "severity": event.severity,
        "message": event.message,
        "risk_score": event.risk_score,
        "start_value": event.start_value,
        "end_value": event.end_value,
        "duration_seconds": event.duration_seconds,
        "details": details,
        "resolved": event.resolved,
        "created_at": (
            event.created_at.isoformat()
            if event.created_at else None
        ),
        "resolved_at": (
            event.resolved_at.isoformat()
            if event.resolved_at else None
        ),
    }


def classify_voltage(voltage):
    if voltage <= VOLTAGE_CRITICAL_LOW:
        return "CRITICAL"

    if voltage >= VOLTAGE_CRITICAL_HIGH:
        return "CRITICAL"

    if voltage <= VOLTAGE_WARNING_LOW:
        return "WARNING"

    if voltage >= VOLTAGE_WARNING_HIGH:
        return "WARNING"

    return "NORMAL"


def classify_current(current):
    current = abs(current)

    if current >= CURRENT_CRITICAL:
        return "CRITICAL"

    if current >= CURRENT_WARNING:
        return "WARNING"

    return "NORMAL"


def classify_temperature(temperature):
    if temperature >= TEMP_CRITICAL:
        return "CRITICAL"

    if temperature >= TEMP_WARNING:
        return "WARNING"

    return "NORMAL"


# ============================================================
# FEATURE 1: BATTERY RISK INDEX
# ============================================================

def calculate_risk(battery):
    voltage = float(battery["voltage"])
    current = abs(float(battery["current"]))
    temperature = float(battery["temperature"])

    voltage_status = classify_voltage(voltage)
    current_status = classify_current(current)
    temperature_status = classify_temperature(temperature)

    voltage_risk = 0

    if voltage_status == "WARNING":
        voltage_risk = 55
    elif voltage_status == "CRITICAL":
        voltage_risk = 100

    current_risk = min(
        100,
        max(0, (current - 90) / 55 * 100),
    )

    temperature_risk = min(
        100,
        max(0, (temperature - 30) / 20 * 100),
    )

    # Weighted combined score.
    score = (
        voltage_risk * 0.40
        + current_risk * 0.25
        + temperature_risk * 0.35
    )

    score = round(min(100, max(0, score)), 2)

    if (
        voltage_status == "CRITICAL"
        or current_status == "CRITICAL"
        or temperature_status == "CRITICAL"
        or score >= 75
    ):
        level = "CRITICAL"

    elif (
        voltage_status == "WARNING"
        or current_status == "WARNING"
        or temperature_status == "WARNING"
        or score >= 40
    ):
        level = "WARNING"

    else:
        level = "LOW"

    return {
        "battery_id": battery["battery_id"],
        "vehicle_id": battery["vehicle_id"],
        "risk_score": score,
        "risk_level": level,
        "voltage_risk": round(voltage_risk, 2),
        "current_risk": round(current_risk, 2),
        "temperature_risk": round(temperature_risk, 2),
        "voltage_status": voltage_status,
        "current_status": current_status,
        "temperature_status": temperature_status,
        "recommendation": (
            "Immediate inspection recommended"
            if level == "CRITICAL"
            else "Monitor battery parameters"
            if level == "WARNING"
            else "Battery parameters within configured limits"
        ),
        "calculated_at": datetime.utcnow().isoformat(),
    }


@router.get("/risk/{battery_id}")
def battery_risk(
    battery_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    battery = check_battery_access(
        db, user, battery_id
    )

    result = calculate_risk(battery)

    record_event(
        db,
        battery_id=battery["battery_id"],
        vehicle_id=battery["vehicle_id"],
        event_type="RISK_ASSESSMENT",
        severity=result["risk_level"],
        message="Battery risk assessment performed",
        risk_score=result["risk_score"],
        details=result,
    )

    return {
        "success": True,
        "data": result,
    }


# ============================================================
# FEATURE 2: SENSOR RELIABILITY MONITORING
# ============================================================

@router.get("/sensor-reliability/{battery_id}")
def sensor_reliability(
    battery_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    battery = check_battery_access(
        db, user, battery_id
    )

    values = {
        "voltage": float(battery["voltage"]),
        "current": float(battery["current"]),
        "temperature": float(battery["temperature"]),
    }

    state = (
        db.query(BatterySensorState)
        .filter(
            BatterySensorState.battery_id
            == battery["battery_id"]
        )
        .first()
    )

    if state is None:
        state = BatterySensorState(
            battery_id=battery["battery_id"],
        )
        db.add(state)

    checks = {}

    for name, value in values.items():
        previous = getattr(state, f"last_{name}")
        count_field = f"{name}_repeat_count"

        repeat_count = getattr(state, count_field) or 0

        if previous is not None and abs(
            value - previous
        ) < 0.0001:
            repeat_count += 1
        else:
            repeat_count = 0

        setattr(state, count_field, repeat_count)
        setattr(state, f"last_{name}", value)

        if name == "voltage":
            plausible = 250 <= value <= 500
        elif name == "current":
            plausible = abs(value) <= 250
        else:
            plausible = -20 <= value <= 100

        if not plausible:
            status = "ABNORMAL"
        elif repeat_count >= SENSOR_REPEAT_LIMIT:
            status = "POSSIBLY_FROZEN"
        else:
            status = "NORMAL"

        checks[name] = {
            "value": value,
            "status": status,
            "repeat_count": repeat_count,
            "plausible": plausible,
        }

    statuses = [
        item["status"]
        for item in checks.values()
    ]

    if "ABNORMAL" in statuses:
        overall = "UNRELIABLE"
    elif "POSSIBLY_FROZEN" in statuses:
        overall = "CHECK_SENSOR"
    else:
        overall = "RELIABLE"

    state.reliability_status = overall
    state.last_seen = datetime.utcnow()
    state.updated_at = datetime.utcnow()

    db.commit()

    if overall != "RELIABLE":
        record_event(
            db,
            battery_id=battery["battery_id"],
            vehicle_id=battery["vehicle_id"],
            event_type="SENSOR_RELIABILITY",
            severity=(
                "CRITICAL"
                if overall == "UNRELIABLE"
                else "WARNING"
            ),
            message=f"Sensor reliability status: {overall}",
            details=checks,
        )

    return {
        "success": True,
        "battery_id": battery["battery_id"],
        "overall_status": overall,
        "sensors": checks,
        "checked_at": datetime.utcnow().isoformat(),
    }


# ============================================================
# FEATURE 3: BATTERY STRESS ANALYSIS
# ============================================================

def get_stress_conditions(battery):
    voltage = float(battery["voltage"])
    current = abs(float(battery["current"]))
    temperature = float(battery["temperature"])

    conditions = []

    if temperature >= TEMP_WARNING:
        conditions.append("HIGH_TEMPERATURE")

    if current >= CURRENT_WARNING:
        conditions.append("HIGH_CURRENT")

    if (
        voltage <= VOLTAGE_WARNING_LOW
        or voltage >= VOLTAGE_WARNING_HIGH
    ):
        conditions.append("VOLTAGE_DEVIATION")

    return conditions


@router.post("/stress/{battery_id}")
def analyze_stress(
    battery_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    battery = check_battery_access(
        db, user, battery_id
    )

    conditions = get_stress_conditions(battery)

    active_events = (
        db.query(BatteryIntelligenceEvent)
        .filter(
            BatteryIntelligenceEvent.battery_id
            == battery["battery_id"],
            BatteryIntelligenceEvent.event_type
            == "BATTERY_STRESS",
            BatteryIntelligenceEvent.resolved
            == False,
        )
        .all()
    )

    active = {
        event.message: event
        for event in active_events
    }

    current_keys = set(conditions)

    for condition in conditions:
        message = f"Battery stress detected: {condition}"

        if message not in active:
            record_event(
                db,
                battery_id=battery["battery_id"],
                vehicle_id=battery["vehicle_id"],
                event_type="BATTERY_STRESS",
                severity="WARNING",
                message=message,
                start_value=float(battery["temperature"]),
                details={
                    "condition": condition,
                    "voltage": battery["voltage"],
                    "current": battery["current"],
                    "temperature": battery["temperature"],
                },
            )

    for message, event in active.items():
        condition = message.replace(
            "Battery stress detected: ", ""
        )

        if condition not in current_keys:
            event.resolved = True
            event.resolved_at = datetime.utcnow()

            if event.created_at:
                event.duration_seconds = max(
                    0,
                    (
                        event.resolved_at
                        - event.created_at
                    ).total_seconds(),
                )

    db.commit()

    return {
        "success": True,
        "battery_id": battery["battery_id"],
        "stress_detected": bool(conditions),
        "active_stress_conditions": conditions,
        "voltage": battery["voltage"],
        "current": battery["current"],
        "temperature": battery["temperature"],
        "checked_at": datetime.utcnow().isoformat(),
    }


# ============================================================
# FEATURE 4: RECOVERY TIME TRACKING
# ============================================================

@router.get("/recovery/{battery_id}")
def recovery_tracking(
    battery_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    battery = check_battery_access(
        db, user, battery_id
    )

    active_events = (
        db.query(BatteryIntelligenceEvent)
        .filter(
            BatteryIntelligenceEvent.battery_id
            == battery["battery_id"],
            BatteryIntelligenceEvent.event_type
            == "BATTERY_STRESS",
            BatteryIntelligenceEvent.resolved
            == False,
        )
        .all()
    )

    completed_events = (
        db.query(BatteryIntelligenceEvent)
        .filter(
            BatteryIntelligenceEvent.battery_id
            == battery["battery_id"],
            BatteryIntelligenceEvent.event_type
            == "BATTERY_STRESS",
            BatteryIntelligenceEvent.resolved
            == True,
        )
        .order_by(
            BatteryIntelligenceEvent.resolved_at.desc()
        )
        .limit(20)
        .all()
    )

    now = datetime.utcnow()

    active = []

    for event in active_events:
        duration = (
            (now - event.created_at).total_seconds()
            if event.created_at else 0
        )

        active.append({
            "event_id": event.id,
            "message": event.message,
            "stress_duration_seconds": round(
                duration, 2
            ),
            "status": "RECOVERY_PENDING",
        })

    completed = [
        {
            "event_id": event.id,
            "message": event.message,
            "recovery_time_seconds": event.duration_seconds,
            "status": "RECOVERED",
            "resolved_at": (
                event.resolved_at.isoformat()
                if event.resolved_at else None
            ),
        }
        for event in completed_events
    ]

    return {
        "success": True,
        "battery_id": battery["battery_id"],
        "active_recovery_events": active,
        "completed_recoveries": completed,
        "active_count": len(active),
        "completed_count": len(completed),
    }


# ============================================================
# FEATURE 5: PROTECTION RESPONSE VERIFICATION
# ============================================================

class ProtectionVerificationRequest(BaseModel):
    action: str = Field(
        min_length=2,
        max_length=100
    )

    baseline_voltage: float
    baseline_current: float
    baseline_temperature: float

    after_voltage: float
    after_current: float
    after_temperature: float


@router.post("/protection/verify/{battery_id}")
def verify_protection_response(
    battery_id: str,
    payload: ProtectionVerificationRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    battery = check_battery_access(
        db, user, battery_id
    )

    before = {
        "voltage": payload.baseline_voltage,
        "current": abs(payload.baseline_current),
        "temperature": payload.baseline_temperature,
    }

    after = {
        "voltage": payload.after_voltage,
        "current": abs(payload.after_current),
        "temperature": payload.after_temperature,
    }

    def parameter_is_safe(name, value):
        if name == "voltage":
            return classify_voltage(value) == "NORMAL"

        if name == "current":
            return classify_current(value) == "NORMAL"

        return classify_temperature(value) == "NORMAL"

    before_issues = [
        name
        for name, value in before.items()
        if not parameter_is_safe(name, value)
    ]

    after_issues = [
        name
        for name, value in after.items()
        if not parameter_is_safe(name, value)
    ]

    improved = (
        len(after_issues) < len(before_issues)
    )

    if not after_issues:
        result = "SUCCESS"
    elif improved:
        result = "PARTIAL_IMPROVEMENT"
    else:
        result = "NOT_VERIFIED"

    details = {
        "action": payload.action,
        "before": before,
        "after": after,
        "before_issues": before_issues,
        "after_issues": after_issues,
        "result": result,
    }

    record_event(
        db,
        battery_id=battery["battery_id"],
        vehicle_id=battery["vehicle_id"],
        event_type="PROTECTION_VERIFICATION",
        severity=(
            "INFO"
            if result == "SUCCESS"
            else "WARNING"
        ),
        message=f"Protection response: {result}",
        details=details,
    )

    return {
        "success": True,
        "battery_id": battery["battery_id"],
        "protection_action": payload.action,
        "verification_result": result,
        "before_issues": before_issues,
        "after_issues": after_issues,
        "details": details,
        "note": (
            "This verifies the supplied before/after readings. "
            "It does not independently confirm that a physical "
            "protection device operated."
        ),
    }


# ============================================================
# FEATURE 6: BATTERY FAULT SIMULATOR
# ============================================================

FAULT_SCENARIOS = {
    "overvoltage": {
        "voltage": 460.0,
        "current": 70.0,
        "temperature": 30.0,
    },
    "undervoltage": {
        "voltage": 320.0,
        "current": 70.0,
        "temperature": 30.0,
    },
    "overcurrent": {
        "voltage": 390.0,
        "current": 165.0,
        "temperature": 34.0,
    },
    "overheating": {
        "voltage": 390.0,
        "current": 75.0,
        "temperature": 50.0,
    },
}


class FaultSimulationRequest(BaseModel):
    fault_type: str


@router.post("/simulate/{battery_id}")
def simulate_battery_fault(
    battery_id: str,
    payload: FaultSimulationRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    battery = check_battery_access(
        db, user, battery_id
    )

    fault_type = payload.fault_type.lower().strip()

    if fault_type not in FAULT_SCENARIOS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported fault. Choose overvoltage, "
                "undervoltage, overcurrent, or overheating."
            ),
        )

    baseline = {
        "voltage": float(battery["voltage"]),
        "current": float(battery["current"]),
        "temperature": float(battery["temperature"]),
    }

    simulated = FAULT_SCENARIOS[fault_type].copy()

    simulated_battery = {
        **battery,
        **simulated,
    }

    risk = calculate_risk(simulated_battery)

    simulated_statuses = {
        "voltage": classify_voltage(
            simulated["voltage"]
        ),
        "current": classify_current(
            simulated["current"]
        ),
        "temperature": classify_temperature(
            simulated["temperature"]
        ),
    }

    result = {
        "fault_type": fault_type,
        "baseline": baseline,
        "simulated_readings": simulated,
        "simulated_statuses": simulated_statuses,
        "risk_assessment": risk,
        "recommended_response": {
            "overvoltage": (
                "Stop charging and inspect voltage regulation."
            ),
            "undervoltage": (
                "Reduce load and inspect battery voltage and cells."
            ),
            "overcurrent": (
                "Reduce current demand and inspect the load path."
            ),
            "overheating": (
                "Reduce load and initiate the approved thermal response."
            ),
        }[fault_type],
        "simulation_only": True,
    }

    record_event(
        db,
        battery_id=battery["battery_id"],
        vehicle_id=battery["vehicle_id"],
        event_type="FAULT_SIMULATION",
        severity="WARNING",
        message=f"Simulated fault: {fault_type}",
        risk_score=risk["risk_score"],
        details=result,
    )

    return {
        "success": True,
        "data": result,
    }


# ============================================================
# EVENT HISTORY
# ============================================================

@router.get("/events")
def get_intelligence_events(
    battery_id: str = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    allowed = get_allowed_vehicle_ids(db, user)

    query = db.query(
        BatteryIntelligenceEvent
    )

    if battery_id:
        battery_id = battery_id.upper()

        vehicle_id = battery_id.replace(
            "BAT-", "EV-", 1
        )

        if vehicle_id not in allowed:
            raise HTTPException(
                status_code=403,
                detail="You do not have access to this battery",
            )

        query = query.filter(
            BatteryIntelligenceEvent.battery_id
            == battery_id
        )

    else:
        allowed_batteries = [
            vehicle_id.replace("EV-", "BAT-", 1)
            for vehicle_id in allowed
        ]

        query = query.filter(
            BatteryIntelligenceEvent.battery_id.in_(
                allowed_batteries
            )
        )

    events = (
        query.order_by(
            BatteryIntelligenceEvent.created_at.desc()
        )
        .limit(max(1, min(limit, 500)))
        .all()
    )

    return {
        "success": True,
        "count": len(events),
        "events": [
            event_to_dict(event)
            for event in events
        ],
    }


@router.get("/overview")
def intelligence_overview(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    allowed = get_allowed_vehicle_ids(db, user)

    allowed_batteries = [
        vehicle_id.replace("EV-", "BAT-", 1)
        for vehicle_id in allowed
    ]

    events = (
        db.query(BatteryIntelligenceEvent)
        .filter(
            BatteryIntelligenceEvent.battery_id.in_(
                allowed_batteries
            )
        )
        .all()
    )

    return {
        "success": True,
        "total_events": len(events),
        "active_stress_events": sum(
            1 for event in events
            if event.event_type == "BATTERY_STRESS"
            and not event.resolved
        ),
        "fault_simulations": sum(
            1 for event in events
            if event.event_type == "FAULT_SIMULATION"
        ),
        "sensor_warnings": sum(
            1 for event in events
            if event.event_type == "SENSOR_RELIABILITY"
        ),
        "protection_checks": sum(
            1 for event in events
            if event.event_type == "PROTECTION_VERIFICATION"
        ),
    }