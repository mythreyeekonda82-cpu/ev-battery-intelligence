import json
import requests

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import get_current_user
from ..models import Battery, Vehicle
from ..services.station_service import get_nearest_stations
from ..services.advanced_intelligence import get_battery_intelligence


router = APIRouter(
    prefix="/api/voltiq",
    tags=["VoltIQ Assistant and GPS"]
)

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODEL = "llama3.2:3b"


class ChatRequest(BaseModel):
    battery_id: str = "BAT-001"
    question: str = Field(min_length=2, max_length=1000)


def normalise_battery_id(value):
    value = value.strip().upper()

    if value.startswith("EV-"):
        value = value.replace("EV-", "BAT-", 1)

    return value


def authorised_battery(db, battery_id, user):
    result = (
        db.query(Battery, Vehicle)
        .join(Vehicle, Battery.vehicle_id == Vehicle.id)
        .filter(Battery.battery_id == battery_id)
        .first()
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Battery not found."
        )

    battery, vehicle = result

    user_role = str(getattr(user, "role", "")).lower()

    if user_role != "admin" and vehicle.owner_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="Access denied."
        )

    return battery


@router.post("/chat")
def battery_chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    battery_id = normalise_battery_id(request.battery_id)

    battery = authorised_battery(
        db,
        battery_id,
        user
    )

    try:
        intelligence = get_battery_intelligence(
            db=db,
            user=user,
            battery_id=battery_id
        )

    except Exception:
        intelligence = {}

    battery_data = {
        "battery_id": battery_id,
        "state_of_health": getattr(battery, "soh", None),
        "state_of_charge": getattr(battery, "soc", None),
        "temperature": getattr(battery, "temperature", None),
        "voltage": getattr(battery, "voltage", None),
        "health": getattr(battery, "health", None),
        "advanced_intelligence": intelligence
    }

    system_prompt = """
You are VoltIQ, an intelligent EV Battery Health
and Fleet Monitoring assistant.

Help users understand:
- Battery health and State of Health (SOH)
- State of Charge (SOC)
- Battery temperature and voltage
- Battery risks and anomalies
- Remaining Useful Life (RUL)
- Battery degradation
- Smart charging
- Predictive maintenance
- Driving range
- EV battery safety

Rules:
1. Use the supplied battery data when answering.
2. Never invent readings or predictions.
3. If data is missing, clearly say it is unavailable.
4. Explain technical concepts in simple language.
5. Give practical battery-care recommendations.
6. Treat predictions as estimates, not guarantees.
7. For potentially unsafe readings, recommend
   inspection by a qualified technician.
8. Keep answers clear and reasonably concise.
"""

    user_prompt = f"""
Selected battery information:

{json.dumps(battery_data, default=str, indent=2)}

User's question:

{request.question}
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                "stream": False
            },
            timeout=120
        )

        response.raise_for_status()

        result = response.json()
        answer = result.get("message", {}).get("content", "").strip()

        if not answer:
            raise HTTPException(
                status_code=502,
                detail="Ollama returned an empty response."
            )

        return {
            "success": True,
            "battery_id": battery_id,
            "answer": answer,
            "source": "ollama",
            "model": OLLAMA_MODEL,
            "disclaimer": (
                "Battery recommendations are estimates, "
                "not certified diagnostics."
            )
        }

    except requests.exceptions.ConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to Ollama. Make sure Ollama is running."
        )

    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=504,
            detail="Ollama took too long to respond. Please try again."
        )

    except requests.exceptions.RequestException:
        raise HTTPException(
            status_code=502,
            detail="Ollama could not generate a response."
        )


# GPS — existing charging station functionality

@router.get("/stations")
def nearest_charging_stations(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    limit: int = Query(5, ge=1, le=20),
    user=Depends(get_current_user)
):
    try:
        stations = get_nearest_stations(
            latitude=latitude,
            longitude=longitude,
            limit=limit
        )

        return {
            "success": True,
            "source": "demonstration_station_data",
            "stations": stations
        }

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve nearby charging stations."
        )