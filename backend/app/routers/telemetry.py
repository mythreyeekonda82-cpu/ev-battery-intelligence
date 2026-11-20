import os
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Vehicle, Telemetry
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
    ),
    db: Session = Depends(get_db)
):
    device_id = data.device_id.strip()

    if not device_id:
        raise HTTPException(
            status_code=400,
            detail="Device ID cannot be empty."
        )

    # Prepare the latest hardware reading
    reading = {
        **data.model_dump(),
        "device_id": device_id
    }

    # Save reading in SQLite
    telemetry_record = Telemetry(
        battery_id=device_id,
        voltage=data.voltage,
        current=data.current,
        temperature=(
            data.temperature
            if data.temperature is not None
            else 0.0
        ),
        soc=data.soc,
        soh=data.soh,
        cycles=0,
        power_kw=data.power / 1000
    )

    try:
        db.add(telemetry_record)
        db.commit()
        db.refresh(telemetry_record)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to save telemetry data."
        )

    # Keep latest reading available in memory
    latest_esp32_data[device_id] = reading

    return {
        "success": True,
        "message": "ESP32 data received and saved successfully.",
        "device_id": device_id,
        "data": reading,
        "timestamp": telemetry_record.timestamp.isoformat()
    }


# ==========================================
# READ REAL ESP32 SENSOR DATA FROM DATABASE
# ==========================================

@router.get("/device")
def get_esp32_telemetry(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only administrators can access hardware telemetry."
        )

    # Get all saved readings, newest first
    records = (
        db.query(Telemetry)
        .order_by(
            Telemetry.timestamp.desc(),
            Telemetry.id.desc()
        )
        .all()
    )

    devices = {}

    # Keep only the latest reading for each device
    for record in records:

        device_id = record.battery_id

        if device_id not in devices:

            devices[device_id] = {
                "device_id": device_id,
                "voltage": record.voltage,
                "current": record.current,
                "power": round(
                    (record.power_kw or 0) * 1000,
                    3
                ),
                "soc": record.soc,
                "soh": record.soh,
                "temperature": record.temperature,
                "timestamp": (
                    record.timestamp.isoformat()
                    if record.timestamp
                    else None
                )
            }

    return {
        "success": True,
        "count": len(devices),
        "devices": devices
    }


# ==========================================
# LATEST READING FOR ONE ESP32 DEVICE
# Polled by the dashboard in ESP32 mode. The browser cannot reach the
# ESP32 directly (it sits on a local network, and an HTTPS page may not
# fetch plain HTTP), so the ESP32 posts to /device and the dashboard
# reads the stored reading back from here.
# ==========================================

@router.get("/device/latest")
def get_latest_esp32_reading(
    device_id: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only administrators can access hardware telemetry."
        )

    query = db.query(Telemetry)

    if device_id and device_id.strip():
        query = query.filter(
            Telemetry.battery_id == device_id.strip()
        )
    else:
        # Without a device ID, use the most recent hardware device.
        # Simulator batteries are stored as BAT-xxx.
        query = query.filter(
            ~Telemetry.battery_id.like("BAT-%")
        )

    record = (
        query
        .order_by(
            Telemetry.timestamp.desc(),
            Telemetry.id.desc()
        )
        .first()
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No readings received from device '{device_id.strip()}' yet."
                if device_id and device_id.strip()
                else "No readings received from any ESP32 device yet."
            )
        )

    return {
        "success": True,
        "device_id": record.battery_id,
        "voltage": record.voltage,
        "current": record.current,
        "power": round((record.power_kw or 0) * 1000, 3),
        "soc": record.soc,
        "soh": record.soh,
        "temperature": record.temperature,
        "timestamp": (
            record.timestamp.isoformat()
            if record.timestamp
            else None
        )
    }
