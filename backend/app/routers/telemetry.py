from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Vehicle
from ..security import get_current_user
from ..simulator.engine import get_simulation_engine


router = APIRouter(
    prefix="/api/telemetry",
    tags=["Telemetry"]
)


def get_user_vehicle_ids(
    current_user,
    db: Session
):
    """
    Return the simulation vehicle IDs the current user
    is allowed to access.

    Admin:
        Can access all 56 vehicles.

    Normal user:
        Can access only vehicles assigned to that user.
    """

    if current_user.role == "admin":
        vehicles = db.query(Vehicle).all()
    else:
        vehicles = (
            db.query(Vehicle)
            .filter(Vehicle.owner_id == current_user.id)
            .all()
        )

    return [vehicle.vehicle_id for vehicle in vehicles]


@router.get("/batteries")
def get_all_battery_telemetry(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Return battery telemetry.

    Admin:
        Returns all 56 batteries.

    Normal user:
        Returns only batteries belonging to assigned vehicles.
    """

    engine = get_simulation_engine()

    allowed_vehicle_ids = get_user_vehicle_ids(
        current_user,
        db
    )

    batteries = []

    for vehicle_id in allowed_vehicle_ids:

        battery_id = vehicle_id.replace(
            "EV-",
            "BAT-"
        )

        battery = engine.get_battery(
            battery_id
        )

        if battery is not None:
            batteries.append(battery)

    timestamp = None

    if batteries:
        timestamp = batteries[0].get(
            "updated_at"
        )

    return {
        "success": True,
        "role": current_user.role,
        "timestamp": timestamp,
        "count": len(batteries),
        "batteries": batteries
    }


@router.get("/batteries/{battery_id}")
def get_battery_telemetry(
    battery_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Return telemetry for one battery.

    Users can only access batteries belonging
    to their assigned vehicle.
    """

    battery_id = battery_id.upper()

    engine = get_simulation_engine()

    battery = engine.get_battery(
        battery_id
    )

    if battery is None:
        raise HTTPException(
            status_code=404,
            detail=f"Battery {battery_id} was not found."
        )

    # Convert BAT-001 -> EV-001
    vehicle_id = battery_id.replace(
        "BAT-",
        "EV-"
    )

    allowed_vehicle_ids = get_user_vehicle_ids(
        current_user,
        db
    )

    if (
        current_user.role != "admin"
        and vehicle_id not in allowed_vehicle_ids
    ):
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this battery."
        )

    return {
        "success": True,
        "role": current_user.role,
        "battery": battery
    }


@router.get("/summary")
def get_battery_summary(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Return battery fleet summary.

    Admin:
        Summary of all 56 vehicles.

    Normal user:
        Summary of assigned vehicles only.
    """

    engine = get_simulation_engine()

    allowed_vehicle_ids = get_user_vehicle_ids(
        current_user,
        db
    )

    batteries = []

    for vehicle_id in allowed_vehicle_ids:

        battery_id = vehicle_id.replace(
            "EV-",
            "BAT-"
        )

        battery = engine.get_battery(
            battery_id
        )

        if battery is not None:
            batteries.append(battery)

    healthy = 0
    warning = 0
    critical = 0

    total_soc = 0.0
    total_soh = 0.0

    for battery in batteries:

        soh = float(
            battery.get("soh", 0)
        )

        temperature = float(
            battery.get("temperature", 0)
        )

        soc = float(
            battery.get("soc", 0)
        )

        total_soc += soc
        total_soh += soh

        if (
            soh >= 85
            and temperature < 40
        ):
            healthy += 1

        elif (
            soh >= 70
            and temperature < 45
        ):
            warning += 1

        else:
            critical += 1

    total = len(batteries)

    average_soc = (
        total_soc / total
        if total > 0
        else 0
    )

    average_soh = (
        total_soh / total
        if total > 0
        else 0
    )

    return {
        "success": True,
        "role": current_user.role,
        "summary": {
            "total": total,
            "healthy": healthy,
            "warning": warning,
            "critical": critical,
            "average_soc": round(
                average_soc,
                2
            ),
            "average_soh": round(
                average_soh,
                2
            )
        }
    }