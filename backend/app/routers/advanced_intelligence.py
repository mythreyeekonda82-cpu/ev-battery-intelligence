"""
VoltIQ Advanced Battery Intelligence API

Provides API access to all eight advanced intelligence features.
Uses the existing authentication and database infrastructure.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import get_current_user

from ..services.advanced_intelligence import (
    get_battery_intelligence,
    get_fleet_intelligence,
)


router = APIRouter(
    prefix="/api/advanced-intelligence",
    tags=["Advanced Battery Intelligence"],
)


# ---------------------------------------------------------
# FLEET INTELLIGENCE
# ---------------------------------------------------------

@router.get("/fleet")
def advanced_fleet_intelligence(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Fleet-wide battery comparison and health summary.
    """

    try:
        result = get_fleet_intelligence(db, user)

        return {
            "success": True,
            "data": result,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to generate fleet intelligence: {str(exc)}",
        )


# ---------------------------------------------------------
# INDIVIDUAL BATTERY INTELLIGENCE
# ---------------------------------------------------------

@router.get("/{battery_id}")
def advanced_battery_intelligence(
    battery_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Return all eight advanced intelligence features
    for the requested battery.
    """

    battery_id = battery_id.strip().upper()

    if battery_id.startswith("EV-"):
        battery_id = battery_id.replace(
            "EV-",
            "BAT-",
            1,
        )

    if not battery_id.startswith("BAT-"):
        raise HTTPException(
            status_code=400,
            detail="Invalid battery ID. Expected BAT-001 format.",
        )

    try:
        result = get_battery_intelligence(
            db=db,
            user=user,
            battery_id=battery_id,
        )

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Battery not found or access denied.",
            )

        return {
            "success": True,
            "data": result,
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to generate battery intelligence: {str(exc)}",
        )