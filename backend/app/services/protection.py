from datetime import datetime

from sqlalchemy.orm import Session

from .. import models


SEVERITY = {

    "OVER_VOLTAGE": "CRITICAL",

    "UNDER_VOLTAGE": "CRITICAL",

    "OVER_TEMPERATURE": "CRITICAL",

    "OVER_CURRENT": "CRITICAL",

    "SENSOR_FAILURE": "WARNING",

    "CONNECTIVITY_LOST": "WARNING",

    "CELL_OVER_VOLTAGE": "CRITICAL",

    "CELL_UNDER_VOLTAGE": "CRITICAL",

    "CELL_OVER_TEMPERATURE": "CRITICAL",

    "CELL_IMBALANCE": "WARNING",
}


_active_codes = {}


def reconcile(
    db: Session,
    vehicle_id: str,
    snapshot: dict
):

    current_codes = (
        {
            event["fault"]
            for event in snapshot["protection"]
        }
        |
        {
            fault["code"]
            for fault in snapshot["cell_faults"]
        }
    )

    previous_codes = _active_codes.get(
        vehicle_id,
        set()
    )

    new_codes = current_codes - previous_codes

    cleared_codes = previous_codes - current_codes

    for code in new_codes:

        alert = models.Alert(

            vehicle_id=vehicle_id,

            code=code,

            severity=SEVERITY.get(
                code,
                "WARNING"
            ),

            message=(
                f"{code.replace('_', ' ').title()} "
                f"detected on {vehicle_id} (simulated)."
            ),

            status="ACTIVE",

            created_at=datetime.utcnow()
        )

        db.add(alert)

    for code in cleared_codes:

        alert = (
            db.query(models.Alert)
            .filter(
                models.Alert.vehicle_id == vehicle_id,
                models.Alert.code == code,
                models.Alert.status == "ACTIVE"
            )
            .order_by(
                models.Alert.created_at.desc()
            )
            .first()
        )

        if alert:

            alert.status = "RESOLVED"

            alert.resolved_at = datetime.utcnow()

    if current_codes != previous_codes:

        db.commit()

    _active_codes[vehicle_id] = current_codes