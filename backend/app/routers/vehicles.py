from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Vehicle, Battery
from ..security import get_current_user
from ..simulator.engine import get_simulation_engine


router = APIRouter(
    prefix="/api/vehicles",
    tags=["vehicles"],
)


# ============================================================
# VEHICLE ACCESS CHECK
# ============================================================

def can_access_vehicle(vehicle, current_user):
    """
    Admin:
        Can access every vehicle.

    Normal user:
        Can access only the vehicle assigned to them.
    """

    if current_user.role == "admin":
        return True

    return vehicle.owner_id == current_user.id


# ============================================================
# LIST VEHICLES
# ============================================================

@router.get("")
def list_vehicles(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Admin:
        Returns all 56 vehicles.

    User:
        Returns only their assigned vehicle.
    """

    query = db.query(Vehicle)

    if current_user.role != "admin":
        query = query.filter(
            Vehicle.owner_id == current_user.id
        )

    vehicles = query.order_by(Vehicle.id.asc()).all()

    engine = get_simulation_engine()

    result = []

    for vehicle in vehicles:

        # Convert database vehicle ID to simulation ID.
        simulation_vehicle_id = vehicle.vehicle_id

        battery_id = simulation_vehicle_id.replace(
            "EV-",
            "BAT-",
        )

        battery = engine.get_battery(battery_id)

        result.append(
            {
                "id": vehicle.id,
                "vehicle_id": vehicle.vehicle_id,
                "name": vehicle.name,
                "model": vehicle.model,
                "battery_count": vehicle.battery_count,
                "status": vehicle.status,
                "owner_id": vehicle.owner_id,

                "battery": battery,
            }
        )

    return {
        "success": True,
        "role": current_user.role,
        "total": len(result),
        "vehicles": result,
    }


# ============================================================
# SINGLE VEHICLE
# ============================================================

@router.get("/{vehicle_id}")
def get_vehicle(
    vehicle_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return detailed information about one vehicle.
    """

    vehicle = (
        db.query(Vehicle)
        .filter(
            Vehicle.vehicle_id == vehicle_id.upper()
        )
        .first()
    )

    if vehicle is None:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found.",
        )

    if not can_access_vehicle(
        vehicle,
        current_user,
    ):
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this vehicle.",
        )

    engine = get_simulation_engine()

    battery_id = vehicle.vehicle_id.replace(
        "EV-",
        "BAT-",
    )

    battery = engine.get_battery(battery_id)

    return {
        "success": True,
        "vehicle": {
            "id": vehicle.id,
            "vehicle_id": vehicle.vehicle_id,
            "name": vehicle.name,
            "model": vehicle.model,
            "battery_count": vehicle.battery_count,
            "status": vehicle.status,
            "owner_id": vehicle.owner_id,
            "battery": battery,
        },
    }


# ============================================================
# VEHICLE BATTERY
# ============================================================

@router.get("/{vehicle_id}/battery")
def get_vehicle_battery(
    vehicle_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return live battery information for a vehicle.
    """

    vehicle = (
        db.query(Vehicle)
        .filter(
            Vehicle.vehicle_id == vehicle_id.upper()
        )
        .first()
    )

    if vehicle is None:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found.",
        )

    if not can_access_vehicle(
        vehicle,
        current_user,
    ):
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this vehicle.",
        )

    engine = get_simulation_engine()

    battery_id = vehicle.vehicle_id.replace(
        "EV-",
        "BAT-",
    )

    battery = engine.get_battery(battery_id)

    if battery is None:
        raise HTTPException(
            status_code=404,
            detail="Battery telemetry not found.",
        )

    return {
        "success": True,
        "vehicle_id": vehicle.vehicle_id,
        "battery": battery,
    }


# ============================================================
# VEHICLE STATUS
# ============================================================

@router.get("/{vehicle_id}/status")
def vehicle_status(
    vehicle_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return a simplified status for one vehicle.
    """

    vehicle = (
        db.query(Vehicle)
        .filter(
            Vehicle.vehicle_id == vehicle_id.upper()
        )
        .first()
    )

    if vehicle is None:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found.",
        )

    if not can_access_vehicle(
        vehicle,
        current_user,
    ):
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this vehicle.",
        )

    engine = get_simulation_engine()

    battery_id = vehicle.vehicle_id.replace(
        "EV-",
        "BAT-",
    )

    battery = engine.get_battery(battery_id)

    if battery is None:
        raise HTTPException(
            status_code=404,
            detail="Battery telemetry not found.",
        )

    if battery["soh"] >= 85:
        health_status = "HEALTHY"
    elif battery["soh"] >= 70:
        health_status = "WARNING"
    else:
        health_status = "CRITICAL"

    return {
        "success": True,
        "vehicle_id": vehicle.vehicle_id,
        "status": vehicle.status,
        "battery_health": health_status,
        "soc": battery["soc"],
        "soh": battery["soh"],
        "temperature": battery["temperature"],
    }