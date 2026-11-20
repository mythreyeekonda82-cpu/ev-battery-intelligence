"""
Save protection intelligence findings as alerts.

Runs after each simulator telemetry snapshot. A finding becomes an
alert only when it needs action, and the same finding for the same
battery is not repeated while an unread copy from the last
ALERT_REPEAT_MINUTES exists.
"""

from datetime import datetime, timedelta

from .. import models
from .protection_intelligence import (
    detect_fault_combinations,
    explain_protection_decision,
    detect_sensor_disagreement,
)


ALERT_REPEAT_MINUTES = 30

DECISION_SEVERITY = {
    "ISOLATE_BATTERY": "CRITICAL",
    "STOP_CHARGING": "WARNING",
    "LIMIT_POWER": "WARNING",
}

COMBINATION_SEVERITY = {
    "CRITICAL": "CRITICAL",
    "HIGH": "WARNING",
}


def protection_findings(battery, history):
    """Return (alert_type, severity, message) for each actionable finding."""

    battery_id = battery.get("battery_id")
    findings = []

    combinations = detect_fault_combinations(battery, history)
    decision = explain_protection_decision(battery, history, combinations)

    severity = DECISION_SEVERITY.get(decision["decision"])

    if severity:
        findings.append((
            f"PROTECTION_{decision['decision']}",
            severity,
            f"{battery_id}: {decision['summary']} "
            f"{decision['recommended_action']}",
        ))

    for combo in combinations["combinations"]:
        severity = COMBINATION_SEVERITY.get(combo["severity"])
        if severity:
            findings.append((
                f"FAULT_{combo['code']}",
                severity,
                f"{battery_id}: {combo['name']}. {combo['explanation']}",
            ))

    sensors = detect_sensor_disagreement(battery, history)

    if sensors["disagreement_detected"]:
        findings.append((
            "SENSOR_DISAGREEMENT",
            "WARNING",
            f"{battery_id}: {sensors['message']}",
        ))

    return findings


def record_protection_alerts(db, battery, history, now=None):
    """Save new alerts for a battery. Returns how many were added."""

    now = now or datetime.utcnow()
    battery_id = battery.get("battery_id")
    since = now - timedelta(minutes=ALERT_REPEAT_MINUTES)

    added = 0

    for alert_type, severity, message in protection_findings(battery, history):

        recent = (
            db.query(models.Alert.id)
            .filter(
                models.Alert.battery_id == battery_id,
                models.Alert.alert_type == alert_type,
                models.Alert.is_read.is_(False),
                models.Alert.created_at >= since,
            )
            .first()
        )

        if recent:
            continue

        db.add(models.Alert(
            battery_id=battery_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            created_at=now,
        ))

        added += 1

    return added
