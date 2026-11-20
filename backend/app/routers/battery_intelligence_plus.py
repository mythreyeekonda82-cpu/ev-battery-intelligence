from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import get_current_user
from ..models import Vehicle, Telemetry
from ..simulator.engine import get_simulation_engine
from ..services.protection_intelligence import analyse_battery


router = APIRouter(
    prefix="/api/battery-intelligence-plus",
    tags=["Additional Battery Intelligence"],
)


# ---------------------------------------------------------
# ACCESS CONTROL
# ---------------------------------------------------------

def get_battery(db, user, battery_id):

    battery_id = battery_id.strip().upper()

    if battery_id.startswith("EV-"):
        battery_id = battery_id.replace("EV-", "BAT-", 1)

    if not battery_id.startswith("BAT-"):
        raise HTTPException(
            status_code=400,
            detail="Invalid battery ID."
        )

    vehicle_id = battery_id.replace("BAT-", "EV-", 1)

    query = db.query(Vehicle).filter(
        Vehicle.vehicle_id == vehicle_id
    )

    if user.role != "admin":
        query = query.filter(
            Vehicle.owner_id == user.id
        )

    vehicle = query.first()

    if vehicle is None:
        raise HTTPException(
            status_code=404,
            detail="Battery not found or access denied."
        )

    engine = get_simulation_engine()
    battery = engine.get_battery(battery_id)

    if battery is None:
        raise HTTPException(
            status_code=404,
            detail="Battery telemetry unavailable."
        )

    return battery


# ---------------------------------------------------------
# HISTORICAL DATA
# ---------------------------------------------------------

def get_history(db, battery_id, hours=24):

    since = datetime.utcnow() - timedelta(hours=hours)

    return (
        db.query(Telemetry)
        .filter(
            Telemetry.battery_id == battery_id,
            Telemetry.timestamp >= since
        )
        .order_by(Telemetry.timestamp.asc())
        .all()
    )


# ---------------------------------------------------------
# MAIN ENDPOINT
# RETURNS ALL EIGHT FEATURES
# ---------------------------------------------------------

@router.get("/{battery_id}")
def get_additional_battery_intelligence(
    battery_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    battery = get_battery(
        db,
        user,
        battery_id
    )

    canonical_id = battery.get(
        "battery_id",
        battery_id.upper()
    )

    history = get_history(
        db,
        canonical_id
    )

    # The learning system looks back further than the live analyses.
    learning_history = get_history(
        db,
        canonical_id,
        hours=24 * 7
    )

    return {
        "success": True,
        "battery_id": canonical_id,
        "data": analyse_battery(battery, history, learning_history),
    }
