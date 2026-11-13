import os
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Vehicle
from ..security import get_current_user
from ..simulator.engine import get_simulation_engine


router = APIRouter(
    prefix="/api/telemetry",
    tags=["Telemetry"]
)


# ==========================================
# ESP32 DATA MODEL
# ==========================================

class ESP32Telemetry(BaseModel):
    device_id: str

    voltage: float = Field(ge=0, le=1000)
    current: float = Field(ge=0, le=1000)
    power: float = Field(ge=0, le=100000)

    soc: float = Field(ge=0, le=100)
    soh: float = Field(ge=0, le=100)

    temperature: Optional[float] = Field(
        default=None,
        ge=-50,
        le=150
    )

    fault: bool = False
    warning: bool = False


# ==========================================
# API KEY SECURITY
# ==========================================

ESP32_API_KEY = os.getenv("ESP32_API_KEY")

latest_esp32_data = {}


def verify_esp32_api_key(
    x_api_key: str = Header(default=None)
):
    if not ESP32_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ESP32 API key is not configured."
        )

    if (
        not x_api_key
        or not secrets.compare_digest(
            x_api_key,
            ESP32_API_KEY
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid ESP32 API key."
        )

    return True


# ==========================================
# VEHICLE ACCESS
# ==========================================

def get_user_vehicle_ids(
    current_user,
    db: Session
):
    if current_user.role == "admin":
        vehicles = db.query(Vehicle).all()
    else:
        vehicles = (
            db.query(Vehicle)
            .filter(
                Vehicle.owner_id == current_user.id
            )
            .all()
        )

    return [
        vehicle.vehicle_id
        for vehicle in vehicles
    ]


# ==========================================
# EXISTING SIMULATED BATTERY DATA
# ==========================================

@router.get("/batteries")
def get_all_battery_telemetry(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
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

        battery = engine.get_battery(battery_id)

        if battery is not None:
            batteries.append(battery)

    timestamp = None

    if batteries:
        timestamp = batteries[0].get("updated_at")

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
    battery_id = battery_id.upper()

    engine = get_simulation_engine()

    battery = engine.get_battery(battery_id)

    if battery is None:
        raise HTTPException(
            status_code=404,
            detail=f"Battery {battery_id} was not found."
        )

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

        battery = engine.get_battery(battery_id)

        if battery is not None:
            batteries.append(battery)

    healthy = 0
    warning = 0
    critical = 0

    total_soc = 0.0
    total_soh = 0.0

    for battery in batteries:
        soh = float(battery.get("soh", 0))
        temperature = float(
            battery.get("temperature", 0)
        )
        soc = float(battery.get("soc", 0))

        total_soc += soc
        total_soh += soh

        if soh >= 85 and temperature < 40:
            healthy += 1
        elif soh >= 70 and temperature < 45:
            warning += 1
        else:
            critical += 1

    total = len(batteries)

    return {
        "success": True,
        "role": current_user.role,
        "summary": {
            "total": total,
            "healthy": healthy,
            "warning": warning,
            "critical": critical,
            "average_soc": round(
                total_soc / total if total else 0,
                2
            ),
            "average_soh": round(
                total_soh / total if total else 0,
                2
            )
        }
    }


# ==========================================
# RECEIVE REAL ESP32 SENSOR DATA
# ==========================================

@router.post("/device")
def receive_esp32_telemetry(
    data: ESP32Telemetry,
    authorized: bool = Depends(
        verify_esp32_api_key
    )
):
    device_id = data.device_id.strip()

    if not device_id:
        raise HTTPException(
            status_code=400,
            detail="Device ID cannot be empty."
        )

    latest_esp32_data[device_id] = {
        **data.model_dump(),
        "device_id": device_id
    }

    return {
        "success": True,
        "message": "ESP32 data received successfully.",
        "device_id": device_id,
        "data": latest_esp32_data[device_id]
    }


# ==========================================
# READ REAL ESP32 SENSOR DATA
# ==========================================

@router.get("/device")
def get_esp32_telemetry(
    current_user=Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only administrators can access hardware telemetry."
        )

    return {
        "success": True,
        "count": len(latest_esp32_data),
        "devices": latest_esp32_data
    }