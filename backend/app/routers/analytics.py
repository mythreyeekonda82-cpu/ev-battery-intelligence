from fastapi import APIRouter, Depends

from ..security import get_current_user
from ..simulator.engine import get_simulation_engine


router = APIRouter(
    prefix="/api/analytics",
    tags=["Analytics"],
)


@router.get("/overview")
def analytics_overview(
    current_user=Depends(get_current_user),
):
    """
    Return analytics data for the complete battery fleet.
    """

    engine = get_simulation_engine()

    batteries = engine.get_all_batteries()

    healthy = 0
    warning = 0
    critical = 0

    for battery in batteries:
        if battery["soh"] >= 85 and battery["temperature"] < 40:
            healthy += 1
        elif battery["soh"] >= 70 and battery["temperature"] < 45:
            warning += 1
        else:
            critical += 1

    return {
        "success": True,
        "fleet": {
            "total": len(batteries),
            "healthy": healthy,
            "warning": warning,
            "critical": critical,
        },
        "batteries": batteries,
    }


@router.get("/battery/{battery_id}")
def battery_analytics(
    battery_id: str,
    current_user=Depends(get_current_user),
):
    """
    Return detailed analytics for one battery.
    """

    engine = get_simulation_engine()

    battery = engine.get_battery(battery_id.upper())

    if battery is None:
        return {
            "success": False,
            "message": f"Battery {battery_id} was not found.",
        }

    return {
        "success": True,
        "battery": battery,
    }